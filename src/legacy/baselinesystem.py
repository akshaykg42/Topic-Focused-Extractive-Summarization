from utils import *
import os
import argparse

TYPES = [0, 1, 3]
keywords_courtlistener = [["petition", "appeals", "relief", "denial", "pleaded", "guilty"], ["argues", "claims", "contends", "filed"], ["conclude", "failed", "review", "abuse", "determined"], ["review", "affirmed", "affirm", "reverse", "reversed"]]
keywords = [["magnitude", "earthquake", "quake", "earthquakes", "quakes", "strike", "struck", "aftershock", "aftershocks", "depth", "tsunami", "tremor", "tremors", "hit"],["epicenter", "north", "south", "east", "west", "northeast", "northwest", "southeast", "southwest", "located", "miles", "km", "kilometers", "felt", "centered"],["destroyed", "collapse", "collapses", "collapsed", "building", "buildings", "road", "roads", "power", "devastated", "devastation", "flattened", "disrupted", "rubble", "fire"],["dead", "injured", "injuries", "death", "killed", "fatalities", "loss", "toll", "casualties", "buried", "trapped", "outbreak", "missing"],["a.m.", "p.m.", "gmt", "et", "pt", "hours", "time", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"],["planes", "aid", "help", "helping", "warning", "warnings", "response", "rescue", "evacuate", "evacuation", "team", "teams", "supplies", "emergency", "reach", "reached", "reaching", "donation", "donate", "search", "searching", "affected", "disaster", "recover", "recovery", "survivors", "charity", "$", "hospital", "responders", "relief"]]
keywords = [set(x) for x in keywords]

def get_type_score(sentence, t):
	sentence = set([word.lower() for word in nltk.word_tokenize(sentence)])
	score = len(sentence.intersection(keywords[t]))
	return score

def predict(document, TYPE):
	scores = [get_type_score(sentence, TYPE) for sentence in document]
	highscore = max(scores)
	if(highscore == 0):
		winner = random.choice(range(len(document)))
	else:
		winner = [i for i in range(len(scores)) if scores[i] == highscore][0]
	return winner


if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument('-d', '--datadir', default='pcr_data')

	args = parser.parse_args()

	DATA_DIR = args.datadir

	print('Loading data...')
	documents, summaries, oracles, types = load(DATA_DIR)
	#test_indices = [6, 7, 9, 13, 14, 17, 18, 37, 47, 54, 59, 62, 63, 68, 73, 89, 91, 108, 114, 127, 128, 132, 138, 145, 152, 157, 158, 160, 167, 170, 172, 173, 175, 185, 188, 191, 193, 199, 202, 207, 208, 212, 214, 217, 238, 239, 249, 259, 260, 262, 264, 268, 272, 278, 279, 280, 287, 289, 297, 306, 307, 311, 313, 321, 323, 325, 326, 340, 342, 345, 347, 350, 358, 359, 361, 374, 378, 391, 394, 395, 398, 409, 410, 415, 423, 424, 428, 429, 439, 442, 443, 444, 447, 449, 451, 459, 465, 467, 469, 471, 474, 477, 478, 481, 488, 497, 507, 509, 514, 523, 535, 558, 560, 572, 576, 577]
	test_files = os.listdir(DATA_DIR + '/bert_processed/test/')
	test_indices = [int(file[:-4]) for file in test_files if file.endswith('.npy')]
	print(test_indices)
	#test_indices = sorted(test_indices)
	documents = [documents[i] for i in test_indices]
	summaries = [summaries[i] for i in test_indices]
	oracles = [oracles[i] for i in test_indices]
	types = [types[i] for i in test_indices]

	rouge1_avg = 0.0
	rouge2_avg = 0.0
	rougel_avg = 0.0

	for abc in range(10):

		model_summary_indices = []
		for i, d in enumerate(documents):
			tmp = []
			for t_ in TYPES:
				tmp.append(predict(d, t_))
			model_summary_indices.append(sorted(list(set(tmp))))

		model_summaries = [' '.join([documents[i][k] for k in model_summary_indices[i]]) for i in range(len(test_indices))]
		# for i in range(len(test_indices)):
		# 	print(model_summaries[i])
		# 	print('\n--------------------------------------------------\n')
		with open('baseline_preds_old.txt', 'w') as f:
			for i in range(len(test_indices)):
				f.write(model_summaries[i] + '\n')

		rouge1 = [rouge.get_scores(model_summaries[i], ' '.join(summaries[i]))[0]['rouge-1']['f'] for i in range(len(test_indices))]
		rouge2 = [rouge.get_scores(model_summaries[i], ' '.join(summaries[i]))[0]['rouge-2']['f'] for i in range(len(test_indices))]
		rougel = [rouge.get_scores(model_summaries[i], ' '.join(summaries[i]))[0]['rouge-l']['f'] for i in range(len(test_indices))]
		rouge1_avg += (np.mean(rouge1))
		rouge2_avg += (np.mean(rouge2))
		rougel_avg += (np.mean(rougel))
	print(rouge1_avg/10)
	print(rouge2_avg/10)
	print(rougel_avg/10)


