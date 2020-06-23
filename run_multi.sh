#!/bin/bash
#
time python3 runTests.py -i ./tests/multi_client_$1.json -o ./quarantine/ -n $(($1+1)) --sync