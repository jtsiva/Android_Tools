#!/usr/bin/python3
import matplotlib.pyplot as plt
import sys
import numpy as np
import os

def preview(data):
	"""
		Show a plot of the data collected in the last run
	"""
	#from: http://stackoverflow.com/questions/5328556/histogram-matplotlib
	hist, bins = np.histogram(data, bins=50)
	width = 0.7 * (bins[1] - bins[0])
	center = (bins[:-1] + bins[1:]) / 2
	plt.bar(center, hist, align='center', width=width)
	#plt.yscale('log', nonposy='clip')
	plt.show()

def main():
	directory = sys.argv[1]
	for filename in os.scandir(directory):
		with open(filename, "r") as f:
			data = []
			avg = 0
			print(str(filename) + ":")
			first = True;
			for line in f:
				if first:
					first = False
				else:
					data.append(int(line.split()[0]))
					avg = line.split()[1]

			print("avg: " + str(avg) + "--- stdev: " + str(np.std(np.array(data))))
			preview(data)

if __name__ == "__main__":
	main()