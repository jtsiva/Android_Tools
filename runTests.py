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

def prepRun(devices, num_devs, full_batt):
	go = False
	readyDev = None
	while not go:
		num_running = 0
		for dev, val in devices.items():
			devices[dev]['battery'] = getBatteryLevel(dev)
			if not val['running']:
				if (full_batt and 100 == devices[dev]['battery']) or not full_batt:
					readyDev = dev
			elif val['running']:
				num_running += 1

		if num_running <= num_devs and readyDev is not None:
			go = True
			devices[readyDev]['running'] = True
		elif readyDev is None and full_batt:
			print("Waiting for a dev to charge to full...")
			time.sleep(300)

	proc = subprocess.Popen("adb -s " + readyDev + " shell dumpsys batterystats --reset" , shell=True, stdin=subprocess.PIPE,
	                     stdout=subprocess.PIPE,
	                     stderr=subprocess.PIPE)
	proc.wait()

	return readyDev

def collect(name):
	timestr = time.strftime("%Y%m%d-%H%M%S")
	proc = subprocess.Popen("adb bugreport  > ./" + name + "-battery-" + timestr + ".zip" , 
						 shell=True, 
						 stdin=subprocess.PIPE,
	                     stdout=subprocess.PIPE,
	                     stderr=subprocess.PIPE)

	proc.wait()

	proc = subprocess.Popen("adb pull sdcard/btsnoop_hci.log ./" + name + "-bt_log-" + timestr + ".log" , 
						 shell=True, 
						 stdin=subprocess.PIPE,
	                     stdout=subprocess.PIPE,
	                     stderr=subprocess.PIPE)
	proc.wait()

def getScreenState():
	proc = subprocess.Popen("adb shell dumpsys power | grep 'mHoldingDisplaySuspendBlocker'", 
						 shell=True, 
						 stdin=subprocess.PIPE,
	                     stdout=subprocess.PIPE,
	                     stderr=subprocess.PIPE)

	out = proc.stdout.read()
	# print (out)
	# print (out.split("=")[1].strip())
	state =  out.split("=")[1].strip() == 'true'
		
	return state

def toggleScreen(state):
	# print ("Change screen state to " + str(state))
	# print ("Current screen state is " + str(getScreenState()))
	if state != getScreenState():
		proc = subprocess.Popen("adb shell input keyevent KEYCODE_POWER", 
						 shell=True, 
						 stdin=subprocess.PIPE,
	                     stdout=subprocess.PIPE,
	                     stderr=subprocess.PIPE)
		proc.wait()

		while state != getScreenState():
			time.sleep(.5)

#From: https://stackoverflow.com/questions/18924968/using-adb-to-access-a-particular-ui-control-on-the-screen
def pressButton(name):
	proc = subprocess.Popen("adb shell -x uiautomator dump  /dev/fd/1 | perl -ne 'printf \"%d %d\n\", ($1+$2)/2, ($3+$4)/2 if /text=\"" + name + "\" [^>]*bounds=\"\[(\d+),(\d+)\]\[(\d+),(\d+)\]\"/' -", 
									shell=True, stdin=subprocess.PIPE,
	                     			stdout=subprocess.PIPE,
	                     			stderr=subprocess.PIPE)
	coords = proc.stdout.read()

	proc = subprocess.Popen("adb shell input tap " + coords, 
									shell=True, stdin=subprocess.PIPE,
	                     			stdout=subprocess.PIPE,
	                     			stderr=subprocess.PIPE)
	proc.wait()

def runJobs(name, jobs, devices, num_devs, require_full, output = None):
	for job in jobs:
		dev = prepRun(devices, num_devs, require_full)
		proc = subprocess.Popen("adb -s " + dev + " shell am start -n " + job['app'] , shell=True, stdin=subprocess.PIPE,
	                     stdout=subprocess.PIPE,
	                     stderr=subprocess.PIPE)
		proc.wait()
		collectData = False
		for action in job['actions']:
			if 'button' in action:
				pressButton(action['button'])
			elif 'text' in action:
				proc = subprocess.Popen("adb -s " + dev + " shell input text " 
									+ str(action['text']), 
									shell=True, stdin=subprocess.PIPE,
	                     			stdout=subprocess.PIPE,
	                     			stderr=subprocess.PIPE)
				proc.wait()
			elif 'collect' in action:
				collectData = True
			elif 'screenOn' in action:
				toggleScreen(action['screenOn'])
			elif 'pluggedIn' in action:
				if action['pluggedIn']:
					reconnectUSB()
				else:
					disconnectUSB()
			elif 'sleep' in action:
				time.sleep(int(action['sleep']))

		proc = subprocess.Popen("adb -s " + dev + " shell am force-stop " + job['app'].split('/')[0], 
									shell=True, stdin=subprocess.PIPE,
	                     			stdout=subprocess.PIPE,
	                     			stderr=subprocess.PIPE)
		proc.wait()
		if output is None and collectData:
			collect(name)

		devices[dev]['running'] = False


def main():
	parser = argparse.ArgumentParser()
	parser.add_argument ("-i", "--input", required = True, help="path to jobs file")
	parser.add_argument ("-o", "--output", required = False, help="path to output directory")
	parser.add_argument ("-n", "--num_devs", default=1, help="number of devices to use")
	parser.add_argument('--full_batt', help='Require devices to have a full battery to run', action='store_true')
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

	#print(devices)

	for devName,val in devices.items():
		proc = subprocess.Popen("adb -s " + devName + " shell dumpsys battery | grep -m 1 level", shell=True, stdin=subprocess.PIPE,
	                         stdout=subprocess.PIPE,
	                         stderr=subprocess.PIPE)
		devices[devName]['battery'] = int(proc.stdout.readlines()[0].split(':')[1].strip())
	
	print("running job: " + jobs['job_name'])
	runJobs(jobs["job_name"], jobs['jobs'], devices, args.num_devs, args.full_batt, args.output)

if __name__ == '__main__':
    main()
