import json
import argparse
import subprocess
import os
import time
import re
import concurrent.futures
import threading


def checkUserIsRoot():
	return 0 == os.getuid()

# from https://ubuntuforums.org/showthread.php?t=2218791
# ID from lspci and "ll /sys/bus/usb/drivers/usb/" 
def disconnectUSB(dev):
	proc = subprocess.Popen("uhubctl | grep " + dev, shell=True, stdin=subprocess.PIPE,
	                     stdout=subprocess.PIPE,
	                     stderr=subprocess.PIPE)
	out = proc.stdout.readlines()
	port = re.search(r'\d+', out[0]).group()

	proc = subprocess.Popen("uhubctl -a 0 -p " + port, shell=True, stdin=subprocess.PIPE,
	                     stdout=subprocess.PIPE,
	                     stderr=subprocess.PIPE)
	proc.wait()

	return port
	
def reconnectUSB(port):
	proc = subprocess.Popen("uhubctl -a 1 -p " + port, shell=True, stdin=subprocess.PIPE,
	                     stdout=subprocess.PIPE,
	                     stderr=subprocess.PIPE)
	proc.wait()
	time.sleep(5)

def writeToFile(job):
	timestr = time.strftime("%Y%m%d-%H%M%S")

def getBatteryLevel(dev):
	proc = subprocess.Popen("adb -s " + dev + " shell dumpsys battery | grep -m 1 level", shell=True, stdin=subprocess.PIPE,
	                         stdout=subprocess.PIPE,
	                         stderr=subprocess.PIPE)
	return int(proc.stdout.readlines()[0].split(':')[1].strip())

def prepRun(devices, name, full_batt):
	go = False
	readyDev = None
	while not go:
		for dev, val in devices.items():
			devices[dev]['battery'] = getBatteryLevel(dev)
			with deviceLock:
				if not val['running']:
					if (full_batt and 100 == devices[dev]['battery']) or not full_batt:
						readyDev = dev

		if readyDev is not None:
			go = True
			print (readyDev + " is ready!")
			with deviceLock:
				devices[readyDev]['running'] = True
		elif readyDev is None and full_batt:
			print("Waiting for a dev to charge to full...")
			time.sleep(300)

	#Reset battery stats
	print("resetting battery stats..."), 
	proc = subprocess.Popen("adb -s " + readyDev + " shell dumpsys batterystats --reset" , shell=True, stdin=subprocess.PIPE,
	                     stdout=subprocess.PIPE,
	                     stderr=subprocess.PIPE)
	proc.wait()
	print ("done!")

	#Reset logcat logs
	print ("resetting logcat logs..."), 
	proc = subprocess.Popen("adb -s " + readyDev + " logcat -c" , shell=True, stdin=subprocess.PIPE,
	                     stdout=subprocess.PIPE,
	                     stderr=subprocess.PIPE)
	proc.wait()
	print("done!")

	#Get state of the bt logs before starting
	print ("getting current state of btsnoop_hci.log..."), 
	timestr = time.strftime("%Y%m%d-%H%M%S")
	proc = subprocess.Popen("adb -s " + readyDev + " pull sdcard/btsnoop_hci.log ./btsnoop_start_" + name+ "_" + timestr + ".log"  , shell=True, stdin=subprocess.PIPE,
	                     stdout=subprocess.PIPE,
	                     stderr=subprocess.PIPE)
	proc.wait()
	print("done!")

	return readyDev

def collect(dev, name, output):
	timestr = time.strftime("%Y%m%d-%H%M%S")
	proc = subprocess.Popen("adb -s "  + dev + " bugreport  > " + output + name + "-battery-" + timestr + ".zip" , 
						 shell=True, 
						 stdin=subprocess.PIPE,
	                     stdout=subprocess.PIPE,
	                     stderr=subprocess.PIPE)

	proc.wait()

	proc = subprocess.Popen("adb -s " + dev + " pull sdcard/btsnoop_hci.log " + output + name + "-bt_log-" + timestr + ".log" , 
						 shell=True, 
						 stdin=subprocess.PIPE,
	                     stdout=subprocess.PIPE,
	                     stderr=subprocess.PIPE)
	proc.wait()

def getScreenState(dev):
	proc = subprocess.Popen("adb -s " + dev + " shell dumpsys power | grep 'mHoldingDisplaySuspendBlocker'", 
						 shell=True, 
						 stdin=subprocess.PIPE,
	                     stdout=subprocess.PIPE,
	                     stderr=subprocess.PIPE)

	out = proc.stdout.read()
	# print (out)
	# print (out.split("=")[1].strip())
	state =  out.split("=")[1].strip() == 'true'
		
	return state

def toggleScreen(dev, state):
	# print ("Change screen state to " + str(state))
	# print ("Current screen state is " + str(getScreenState()))
	if state != getScreenState(dev):
		proc = subprocess.Popen("adb -s " + dev + " shell input keyevent KEYCODE_POWER", 
						 shell=True, 
						 stdin=subprocess.PIPE,
	                     stdout=subprocess.PIPE,
	                     stderr=subprocess.PIPE)
		proc.wait()

		while state != getScreenState(dev):
			time.sleep(.5)

#From: https://stackoverflow.com/questions/18924968/using-adb-to-access-a-particular-ui-control-on-the-screen
def pressButton(dev, name):
	proc = subprocess.Popen("adb -s " + dev + " shell -x uiautomator dump  /dev/fd/1 | perl -ne 'printf \"%d %d\n\", ($1+$2)/2, ($3+$4)/2 if /text=\"" + name + "\" [^>]*bounds=\"\[(\d+),(\d+)\]\[(\d+),(\d+)\]\"/' -", 
									shell=True, stdin=subprocess.PIPE,
	                     			stdout=subprocess.PIPE,
	                     			stderr=subprocess.PIPE)
	coords = proc.stdout.read()

	proc = subprocess.Popen("adb -s " + dev + " shell input tap " + coords, 
									shell=True, stdin=subprocess.PIPE,
	                     			stdout=subprocess.PIPE,
	                     			stderr=subprocess.PIPE)
	proc.wait()

def runJob(job, devices, require_full, output):
	name = job['name']
	if not os.path.isdir(output):
		output = './'

	dev = prepRun(devices, name, require_full)
	print ("running on " + dev)

	if 'None' not in job['app']:
		proc = subprocess.Popen("adb -s " + dev + " shell am start -n " + job['app'] , shell=True, stdin=subprocess.PIPE,
		                	stdout=subprocess.PIPE,
	                     		stderr=subprocess.PIPE)
		proc.wait()
	
	collectData = False
	port = None
	for action in job['actions']:
		if 'button' in action:
			pressButton(dev, action['button'])
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
			toggleScreen(dev, action['screenOn'])
		elif 'pluggedIn' in action:
			if action['pluggedIn']:
				reconnectUSB(port)
			else:
				port = disconnectUSB(dev)
		elif 'sleep' in action:
			time.sleep(int(action['sleep']))

	proc = subprocess.Popen("adb -s " + dev + " shell am force-stop " + job['app'].split('/')[0], 
								shell=True, stdin=subprocess.PIPE,
                     			stdout=subprocess.PIPE,
                     			stderr=subprocess.PIPE)
	proc.wait()
	if collectData:
		collect(dev, name, output)

	with deviceLock:
		devices[dev]['running'] = False


def main():
	parser = argparse.ArgumentParser()
	parser.add_argument ("-i", "--input", required = True, help="path to jobs file")
	parser.add_argument ("-o", "--output", required = False, default='./', help="path to output directory")
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
	
	print("running job: " + jobs['name'])

	with concurrent.futures.ThreadPoolExecutor(max_workers=int(args.num_devs)) as executor:
		# Start the load operations and mark each future with its URL
		future_to_job = {executor.submit(runJob, job, devices, args.full_batt, args.output): job for job in jobs['jobs']}
		for future in concurrent.futures.as_completed(future_to_job):
		    res = future.result()
	

if __name__ == '__main__':
	deviceLock = threading.Lock()
	main()
