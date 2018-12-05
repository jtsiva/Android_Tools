import json
import argparse
import subprocess
import os
import time
import re
import threading


def checkUserIsRoot():
	return 0 == os.getuid()

def runCmd(cmd, output = False):
	out = None
	with opLock:
		proc = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE,
		                     stdout=subprocess.PIPE,
		                     stderr=subprocess.PIPE)
		
		if output:
			out = proc.stdout.read()
		else:
		proc.wait()

	return out
	

def disconnectUSB(dev):
	out = runCmd("uhubctl | grep " + dev, output=True).split('\n')
	port = re.search(r'\d+', out[0]).group()

	runCmd("uhubctl -a 0 -p " + port)

	return port
	
def reconnectUSB(port):
	runCmd("uhubctl -a 1 -p " + port)
	time.sleep(5)

def getBatteryLevel(dev):
	all = runCmd("adb -s " + dev + " shell dumpsys battery | grep -m 1 level", output=True)
	try:
		out = all.split('\n')
		print ('cmdOutput: ' + str(out))
		batt = out[0].split(':')[1].strip()
		#print ('getBatteryLevel: ' +batt)
		return int(batt)
	except Exception as e:
		print(e)

def prepRun(devices, name, full_batt):
	go = False
	readyDev = None
	while not go:
		for dev, val in devices.items():
			if not val['running']:
				devices[dev]['battery'] = getBatteryLevel(dev)
				if (full_batt and 100 == devices[dev]['battery']) or not full_batt:
					readyDev = dev
					go = True
					print (readyDev + " is ready!")
					devices[readyDev]['running'] = True
					break

		if readyDev is None and full_batt:
			print("Waiting for a dev to charge to full...")
			time.sleep(300)

	#Reset battery stats
	print("resetting battery stats..."), 
	runCmd("adb -s " + readyDev + " shell dumpsys batterystats --reset")
	print ("done!")

	#Reset logcat logs
	print ("resetting logcat logs..."), 
	runCmd("adb -s " + readyDev + " logcat -c")
	print("done!")

	#Get state of the bt logs before starting
	print ("getting current state of btsnoop_hci.log..."), 
	timestr = time.strftime("%Y%m%d-%H%M%S")
	runCmd("adb -s " + readyDev + " pull sdcard/btsnoop_hci.log ./btsnoop_start_" + name+ "_" + timestr + ".log")
	print("done!")

	return readyDev

def collect(dev, name, output):
	timestr = time.strftime("%Y%m%d-%H%M%S")

	runCmd("adb -s "  + dev + " bugreport  > " + output + name + "-battery-" + timestr + ".zip")
	runCmd("adb -s " + dev + " pull sdcard/btsnoop_hci.log " + output + name + "-bt_log-" + timestr + ".log")

def getScreenState(dev):
	out = runCmd("adb -s " + dev + " shell dumpsys power | grep 'mHoldingDisplaySuspendBlocker'", output=True)
	
	# print (out)
	# print (out.split("=")[1].strip())
	state =  out.split("=")[1].strip() == 'true'
		
	return state

def toggleScreen(dev, state):
	# print ("Change screen state to " + str(state))
	# print ("Current screen state is " + str(getScreenState()))
	if state != getScreenState(dev):
		runCmd("adb -s " + dev + " shell input keyevent KEYCODE_POWER")

		while state != getScreenState(dev):
			time.sleep(.5)

#From: https://stackoverflow.com/questions/18924968/using-adb-to-access-a-particular-ui-control-on-the-screen
def pressButton(dev, name):
	coords = runCmd("adb -s " + dev + " shell -x uiautomator dump  /dev/fd/1 | perl -ne 'printf \"%d %d\n\", ($1+$2)/2, ($3+$4)/2 if /text=\"" + name + "\" [^>]*bounds=\"\[(\d+),(\d+)\]\[(\d+),(\d+)\]\"/' -",
			output=True)

	runCmd("adb -s " + dev + " shell input tap " + coords)
	

def runJob(job, dev, output):
	name = job['name']
	if not os.path.isdir(output):
		output = './'

	print ("running + " + name + " on " + dev)

	if 'None' not in job['app']:
		runCmd("adb -s " + dev + " shell am start -n " + job['app'])
	
	
	collectData = False
	port = None
	for action in job['actions']:
		if 'button' in action:
			pressButton(dev, action['button'])
		elif 'text' in action:
			runCmd("adb -s " + dev + " shell input text " + str(action['text']))
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

	runCmd("adb -s " + dev + " shell am force-stop " + job['app'].split('/')[0])

	if collectData:
		collect(dev, name, output)


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
	
	print("running job batch: " + jobs['name'])

	totalDevs = len(devices)
	maxConcurrent = min(totalDevs, args.num_devs)
	runningDevs = 0
	threads = []
	for job in jobs:
		dev = prepRun(devices, job['name'], args.full_batt)
		threads.append(Thread(target = runJob, args = (job, dev, args.output, )))
		thread[-1].start()
		
		runningDevs += 1

		if runningDevs == maxConcurrent:
    			thread[0].join()
			thread.pop(0)
			runningDevs -= 1
		
		 
			

if __name__ == '__main__':
	opLock = threading.Lock()
	main()
