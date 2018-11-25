import json
import argparse
import subprocess
import os
import time

def checkUserIsRoot():
	return 0 == os.getuid()

# from https://ubuntuforums.org/showthread.php?t=2218791
# ID from lspci and "ll /sys/bus/usb/drivers/usb/" 
def disconnectUSB():
	proc = subprocess.Popen("echo -n '0000:00:14.0' > /sys/bus/pci/drivers/xhci_hcd/unbind" , shell=True, stdin=subprocess.PIPE,
	                     stdout=subprocess.PIPE,
	                     stderr=subprocess.PIPE)
	proc.wait()

def reconnectUSB():
	proc = subprocess.Popen("echo -n '0000:00:14.0' > /sys/bus/pci/drivers/xhci_hcd/bind" , shell=True, stdin=subprocess.PIPE,
	                     stdout=subprocess.PIPE,
	                     stderr=subprocess.PIPE)
	proc.wait()
	time.sleep(5)

def writeToFile(job):
	timestr = time.strftime("%Y%m%d-%H%M%S")

def getBatteryLevel(devName):
	proc = subprocess.Popen("adb -s " + devName + " shell dumpsys battery | grep -m 1 level", shell=True, stdin=subprocess.PIPE,
	                         stdout=subprocess.PIPE,
	                         stderr=subprocess.PIPE)
	return int(proc.stdout.readlines()[0].split(':')[1].strip())

def prepRun(devices, num_devs):
	go = False
	readyDev = None
	while not go:
		num_running = 0
		for dev, val in devices.items():
			devices[dev]['battery'] = getBatteryLevel(dev)
			if not val['running'] and 100 == devices[dev]['battery']:
				readyDev = dev
			elif val['running']:
				num_running += 1

		if num_running <= num_devs:
			go = True
			devices[readyDev]['running'] = True

	return readyDev

	proc = subprocess.Popen("adb shell dumpsys batterystats --reset" , shell=True, stdin=subprocess.PIPE,
	                     stdout=subprocess.PIPE,
	                     stderr=subprocess.PIPE)
	proc.wait()

def collect(name):
	timestr = time.strftime("%Y%m%d-%H%M%S")
	proc = subprocess.Popen("adb bugreport  > ./" + name + "-battery-" + timestr + ".zip" , shell=True, stdin=subprocess.PIPE,
	                     stdout=subprocess.PIPE,
	                     stderr=subprocess.PIPE)

	proc.wait()

def runJobs(name, jobs, devices, num_devs, output = None):
	for job in jobs:
		dev = prepRun(devices, num_devs)
		proc = subprocess.Popen("adb -s " + dev + " shell am start -n " + job['app'] , shell=True, stdin=subprocess.PIPE,
	                     stdout=subprocess.PIPE,
	                     stderr=subprocess.PIPE)
		proc.wait()
		for action in job['actions']:
			if 'button' in action:
				proc = subprocess.Popen("adb -s " + dev + " shell input tap " 
									+ str(action['button'][0]) 
									+ " " + str(action['button'][1]), 
									shell=True, stdin=subprocess.PIPE,
	                     			stdout=subprocess.PIPE,
	                     			stderr=subprocess.PIPE)
				proc.wait()
			elif 'sleep' in action:
				disconnectUSB()
				time.sleep(int(action['sleep']))
				reconnectUSB()
		print ("adb -s " + dev + " shell am force-stop " + job['app'].split('/')[0])
		proc = subprocess.Popen("adb -s " + dev + " shell am force-stop " + job['app'].split('/')[0], 
									shell=True, stdin=subprocess.PIPE,
	                     			stdout=subprocess.PIPE,
	                     			stderr=subprocess.PIPE)
		proc.wait()
		if output is None:
			collect(name)


def main():
	parser = argparse.ArgumentParser()
	parser.add_argument ("-i", "--input", required = True, help="path to jobs file")
	parser.add_argument ("-o", "--output", required = False, help="path to output directory")
	parser.add_argument ("-n", "--num_devs", default=1, help="number of devices to use")
	args =  parser.parse_args()

	if not checkUserIsRoot():
		print ("Need root permissions (for enabling/disabling USB port)")
		exit(1)

	with open(args.input, "r") as f:
	    jobs = json.loads(f.read())

	proc = subprocess.Popen("adb devices | grep -w 'device'", shell=True, stdin=subprocess.PIPE,
	                     stdout=subprocess.PIPE,
	                     stderr=subprocess.PIPE)
	devices = {}
	for line in proc.stdout.readlines():
		devices[line.split('\t')[0]] = {"running" : False}

	print(devices)

	for devName,val in devices.items():
		proc = subprocess.Popen("adb -s " + devName + " shell dumpsys battery | grep -m 1 level", shell=True, stdin=subprocess.PIPE,
	                         stdout=subprocess.PIPE,
	                         stderr=subprocess.PIPE)
		devices[devName]['battery'] = int(proc.stdout.readlines()[0].split(':')[1].strip())
	
	print("running job: " + jobs['job_name'])
	runJobs(jobs["job_name"], jobs['jobs'], devices, args.num_devs, args.output)

if __name__ == '__main__':
    main()
