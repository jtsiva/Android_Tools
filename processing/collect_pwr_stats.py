#!/usr/bin/python
import sys
import os
import re

folder = sys.argv[1]

import glob

stats = {"time" : [],
		 "charge_loss" : [],
		 "bt_charge_loss" : []}

for filepath in glob.iglob(folder + '*pwr.txt'):
    print(filepath)
    with open (filepath) as f:
    	for line in f:
    		if "Time on battery:" in line:
    			time = [int(s) for s in re.findall(r'\d+', line)]
    			time = time[:3]
    			stats["time"].append(time[2] + time[1]*1000 + time[0]*60000)

    		if "Discharge:" in line:
    			chargeLoss = line.split()[1]
    			stats["charge_loss"].append(float(chargeLoss))

    		if "Bluetooth Power drain:" in line:
    			line =line.split(':')
    			line = re.sub('mAh', '', line[1])
    			stats['bt_charge_loss'].append(float(line))

folderName = os.path.basename(os.path.normpath(folder))
with open ("./output/" + folderName + "_pwr.txt", "w") as f:
		for key, value in stats.iteritems():
			f.write(key + "\t")
			for entry in value:
				f.write(str(entry))
				f.write("\t")
			f.write("\n")