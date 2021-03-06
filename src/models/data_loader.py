import os
import json
import torch
import random
import numpy as np
from torch.utils import data
from itertools import accumulate, permutations
from torch.utils.data import Dataset, DataLoader, Sampler, SubsetRandomSampler
from sklearn.model_selection import train_test_split

# From a batch (list of items returned by dataloader), generate padded inputs and attention masks and return all
def collate_batch_linear(batch):
	batch_inputs = [item[0] for item in batch]
	batch_labels = torch.from_numpy(np.array([item[1] for item in batch])).unsqueeze(1).cuda()
	batch_size = len(batch_inputs)
	lengths = np.array([len(example) for example in batch_inputs])
	max_len = max(lengths)
	num_features = batch_inputs[0].shape[1]
	padded_inputs = np.zeros((batch_size, max_len, num_features))
	for i, example in enumerate(batch_inputs):
		for j, sentence in enumerate(example):
			padded_inputs[i][j] = sentence
	mask = torch.arange(max_len) >= torch.from_numpy(lengths)[:, None]
	padded_inputs = torch.from_numpy(padded_inputs).float().cuda()
	mask = mask.type(torch.uint8).to(torch.bool).cuda()
	return padded_inputs, mask, batch_labels

# From a batch (list of items returned by dataloader), generate padded inputs and attention masks and return all
def collate_batch_bert(batch):
	batch_inputs = [item[0] for item in batch]
	batch_labels = [item[1] for item in batch]
	batch_size = len(batch_inputs)
	sent_lens = np.array([np.array([len(sent) for sent in example]) for example in batch_inputs])
	max_sent_len = min(512, max(np.array([max(lens) for lens in sent_lens])))
	doc_lens = np.array([len(example) for example in batch_inputs])
	max_doc_len = max(doc_lens)
	padded_inputs = np.zeros((batch_size, max_doc_len, max_sent_len))
	mask = np.zeros((batch_size, max_doc_len, max_sent_len))
	for i, example in enumerate(batch_inputs):
		for j, sentence in enumerate(example):
			for k, token in enumerate(sentence):
				if(k < max_sent_len):
					padded_inputs[i][j][k] = token
					mask[i][j][k] = 1
	padded_inputs = np.vstack(padded_inputs)
	mask = np.vstack(mask)
	batch_labels = torch.from_numpy(np.array(batch_labels)).unsqueeze(1)
	padded_inputs = torch.from_numpy(padded_inputs).long()
	mask = torch.from_numpy(mask).long()
	doc_lens = torch.from_numpy(doc_lens)
	return padded_inputs, mask, batch_labels, doc_lens

# "Reduce" document from old_len to new_len, preserving the sentence at index label
def get_mini_indices(old_len, new_len, label):
	if(new_len >= old_len):
		options = list(range(old_len))
		random.shuffle(options)
		new_label = options.index(label)
		return options, new_label
	else:
		options = list(range(old_len))
		options.pop(label)
		random.shuffle(options)
		indices = options[:new_len]
		new_label = random.randint(0, new_len - 1)
		indices[new_label] = label
		return indices, new_label

# Sampler that always iterates in the same order
class SubsetSequentialSampler(Sampler):
    def __init__(self, indices):
        self.indices = indices

    def __iter__(self):
        return (index for index in self.indices)

    def __len__(self):
        return len(self.indices)

# Main Dataset class
class RegularDataset(Dataset):
	def __init__(self, dataset_name, indices, labels, dataset_type, model_type):
		self.dataset_name = dataset_name
		self.labels = {indices[i] : labels[i] for i in range(len(labels))}
		self.dataset_type = dataset_type
		self.model_type = model_type

	def __len__(self):
		return len(self.labels)

	def __getitem__(self, index):
		path = '../data/{}/{}/{}/{}.pt'.format(self.dataset_name, self.model_type, self.dataset_type, str(index))
		features = torch.load(path)
		label = self.labels[index]
		return features, label

# Mini means we keep K sentences from the original document, including the oracle (K=10)
class MiniDataset(Dataset):
	def __init__(self, dataset_name, indices, labels, dataset_type, model_type, minidoc_size=10):
		self.dataset_name = dataset_name
		self.minidoc_size = minidoc_size
		self.labels = {indices[i] : labels[i] for i in range(len(labels))}
		self.dataset_type = dataset_type
		self.model_type = model_type

	def __len__(self):
		return len(self.labels)

	def __getitem__(self, index):
		path = '../data/{}/{}/{}/{}.pt'.format(self.dataset_name, self.model_type, self.dataset_type, str(index))
		features = torch.load(path)
		label = self.labels[index]
		# "Reduce" document to minidoc_size sentences
		indices, label = get_mini_indices(len(features), self.minidoc_size, label)
		features = torch.tensor([features[i] for i in indices])
		return features, label

# Get indices for dataset and model type train/test/val data
def get_indices(dataset_name, model_type, dataset_type):
	path = '../data/{}/{}/{}/'.format(dataset_name, model_type, dataset_type)
	files = os.listdir(path)
	indices = [int(file[:-3]) for file in files if file.endswith('.pt')]
	return indices

# Create loader that returns examples from some dataset (features of model_type), train/test/val set and a specific topic
def create_loader(dataset_name, model_type, dataset_type, topic, batch_size, mini=False):
	print('Creating {} {} dataloader for {} dataset...'.format(model_type, dataset_type, dataset_name))
	json_path = '../data/' + dataset_name + '/raw/'
	with open(json_path + 'oracles.json') as json_file:
		oracles = json.load(json_file)
	with open(json_path + 'topics.json') as json_file:
		topic_representations = json.load(json_file)

	# Get indices for dataset and model type train/test/val data
	indices = get_indices(dataset_name, model_type, dataset_type)

	# Set all labels to 0 if topic is None (done for for test mode only) since we don't use the labels in any of our evaluation schemes
	# If topic is None, we don't filter by topic and return all test data since none of our evaluation schemes require a target
	# Otherwise keep examples where summary has at least 1 sentence of topic for which we're making dataloader
	if(topic is None):
		labels = [0] * len(indices)
	else:
		labels = []
		indices = [i for i in indices if any([topic in representation for representation in topic_representations[i]])]
		for i in indices:
			representation, oracle = topic_representations[i], oracles[i]
			for j in range(len(representation)):
				if(topic in representation[j]):
					labels.append(oracle[j])
					break

	# Mini means we keep K sentences from the original document, including the oracle (K=10)
	DatasetType = MiniDataset if mini else RegularDataset

	# Initialize dataset
	data = DatasetType(dataset_name, indices, labels, dataset_type, model_type)
	
	# Define samplers, for test always use same order and for train/val randomize
	if(dataset_type == 'test'):
		sampler = SubsetSequentialSampler(indices)
	else:
		sampler = SubsetRandomSampler(indices)

	# Batch collation function is different for different model types
	if(model_type == 'linear'):
		collate_fn = collate_batch_linear
	elif(model_type == 'bert'):
		collate_fn = collate_batch_bert
	
	# Load training data, collated and in batches
	loader = torch.utils.data.DataLoader(data,
											batch_size=batch_size,
											sampler=sampler,
											collate_fn=collate_fn)
	
	return loader
