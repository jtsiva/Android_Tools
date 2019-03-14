#!/usr/bin/python
import sys
import os
import re

folder = sys.argv[1]

import glob

advStats = {"time" : [],
		 "charge_loss" : [],
		 "bt_charge_loss" : []}

scStats = {"time" : [],
		 "charge_loss" : [],
		 "bt_charge_loss" : []}


for filepath in glob.iglob(folder + '*pwr.txt'):
	idle = False
	with open (filepath) as f:
		filename = os.path.basename(filepath)
		if 'idle' in filename:
			idle = True

		for line in f:
			if "Time on battery:" in line:
				time = [int(s) for s in re.findall(r'\d+', line)]
				time = time[:3]
				if 'adv' in filename or idle:
					advStats["time"].append(time[2] + time[1]*1000 + time[0]*60000)
				elif 'sc' in filename:
					scStats["time"].append(time[2] + time[1]*1000 + time[0]*60000)
				
			if "Discharge:" in line:
				chargeLoss = line.split()[1]
				if 'adv' in filename or idle:
					advStats["charge_loss"].append(float(chargeLoss))
				elif 'sc' in filename:
					scStats["charge_loss"].append(float(chargeLoss))

			if "Bluetooth Power drain:" in line:
				line =line.split(':')
				line = re.sub('mAh', '', line[1])
				if 'adv' in filename or idle:
					advStats['bt_charge_loss'].append(float(line))
				elif 'sc' in filename:
					scStats['bt_charge_loss'].append(float(line))

folderName = os.path.basename(os.path.normpath(folder))

if len(advStats['time']) > 0:
	if idle:
		outfile = "./output/" + folderName + "_pwr.txt"
	else:
		outfile = "./output/" + folderName + "_adv_pwr.txt"
	 
	with open (outfile, "w") as f:
		for key, value in advStats.iteritems():
			f.write(key + "\t")
			for entry in value:
				f.write(str(entry))
				f.write("\t")
			f.write("\n")

if len(scStats['time']) > 0:
	with open ("./output/" + folderName + "_sc_pwr.txt", "w") as f:
		for key, value in scStats.iteritems():
			f.write(key + "\t")
			for entry in value:
				f.write(str(entry))
				f.write("\t")
			f.write("\n")
