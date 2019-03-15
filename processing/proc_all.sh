#!/bin/bash

dataDir=$1

for entry in $dataDir*; do 
	
	if [[ -d $entry ]]; then
		echo -n "processing $entry..."

		echo -n "."
		#get all pwr-related field extracted to intermediates
		./extract_pwr.sh $entry/

		echo -n "."
		#get the folder name name and process all the pwr data in intermediates
		folder=$(basename "$entry")
		./collect_pwr_stats.py intermediates/$folder/
		
		#get all adv-sc communication data
		
		echo -n "."
		./collect_adv_sc_comm.py $entry/
		echo "done!"
	fi

done
