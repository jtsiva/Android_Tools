import json
import argparse
import subprocess
import os

def checkUserIsRoot():
	return 0 == os.getuid()

def disconnectUSB():
	proc = subprocess.Popen("echo -n '0000:00:14.0' > /sys/bus/pci/drivers/xhci_hcd/unbind")

def reconnectUSB():
	proc = subprocess.Popen("echo -n '0000:00:14.0' > /sys/bus/pci/drivers/xhci_hcd/bind")

def main():
	parser = argparse.ArgumentParser()
	# parser.add_argument ("-f", "--file", required = True, help="path to jobs file")
	parser.add_argument ("-n", "--num_devs", default=1, help="number of devices to use")
	args =  parser.parse_args()

	if not checkUserIsRoot():
		print ("Need root permissions (for enabling/disabling USB port)")
		exit(1)

	# with open(args.file, "r") as f:
	#     jobs = json.loads(f.read())

	proc = subprocess.Popen("adb devices | grep -w 'device'", shell=True, stdin=subprocess.PIPE,
	                     stdout=subprocess.PIPE,
	                     stderr=subprocess.PIPE)
	devices = {}
	for line in proc.stdout.readlines():
		devices[line.split('\t')[0]] = {}

	print(devices)

	for devName,val in devices.items():
		proc = subprocess.Popen("adb -s " + devName + " shell dumpsys battery | grep -m 1 level", shell=True, stdin=subprocess.PIPE,
	                         stdout=subprocess.PIPE,
	                         stderr=subprocess.PIPE)
		devices[devName]['battery'] = int(proc.stdout.readlines()[0].split(':')[1].strip())
	print(devices)

if __name__ == '__main__':
    main()
