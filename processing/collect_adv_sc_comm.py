#!/usr/bin/python

import glob
import sys
import os

folder = sys.argv[1]

import glob

stats = []

index = 0
for filepath in glob.iglob(folder + '*scan_log*'):
   
    with open (filepath) as f:
    	print(filepath)
    	first = True
    	for line in f:
    		if first:
    			first = False
    			stats.append([])
    		else:
    			stats[index].append(int(line.strip()))
    		#
    	#
    	# print ("number of records: "),
    	# print (len(stats[index]))
    #
    index += 1
if len(stats) == 0:
	#some files were captured with this name
	for filepath in glob.iglob(folder + '*scan_cap*'):
		#print(filepath)
		with open (filepath) as f:
			first = True
			for line in f:
				if first:
					first = False
					stats.append([])
				else:
					stats[index].append(int(line.strip()))
				#
			#
			# print ("number of records: "),
			# print (len(stats[index]))
		#
		index += 1

if len(stats) > 0:
	folderName = os.path.basename(os.path.normpath(folder))
	with open ("./output/" + folderName + "_comm_times.txt", "w") as f:
			for run in stats:
				for value in run:
					f.write(str(value) + "\t")
				#
				f.write('\n')
