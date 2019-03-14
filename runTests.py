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
	#with opLock:
	proc = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE,
	                     stdout=subprocess.PIPE,
	                     stderr=subprocess.PIPE)
	
	if output:
		out = proc.stdout.read()
	else:
			proc.wait()

	return out
	

def disconnectUSB(dev):
	# out = runCmd("uhubctl | grep " + dev, output=True).split('\n')
	# port = re.search(r'\d+', out[0]).group()

	# runCmd("uhubctl -a 0 -p " + port)

	print ("Operation not supported")
	return -1
	
def reconnectUSB(dev, port):
	# runCmd("uhubctl -a 1 -p " + port)
	# time.sleep(3)
	# out = runCmd("adb devices | grep " + dev + " | wc -l", output=True)
	# while not (1 == int(out)):
	# 	print("."),
	# 	runCmd("uhubctl -a 2 -p " + port) #cycling the power seems to make sure it comes back
	# 	time.sleep(3)
	# 	out = runCmd("adb devices | grep " + dev + " | wc -l", output=True)

	# print("")
	print("Operation not supported")

def getBatteryLevel(dev):
	all = runCmd("adb -s " + dev + " shell dumpsys battery | grep -m 1 level", output=True)
	try:
		out = all.split('\n')
		#print ('cmdOutput: ' + str(out))
		batt = out[0].split(':')[1].strip()
		#print ('getBatteryLevel: ' +batt)
		return int(batt)
	except Exception as e:
		print(e)

def checkDevAvailability (devices, jobCount, full_batt):
	go = False
	readyDev = None
	devIndex =  jobCount % len(devices)
	
	while not go:
		devices[devIndex]['battery'] = getBatteryLevel(devices[devIndex]['id'])
		if (full_batt and 100 == devices[devIndex]['battery']) or not full_batt:
			readyDev = devices[devIndex]['id']
			go = True
			print (readyDev + " is ready!")

		if readyDev is None and full_batt:
			print("Waiting for a dev to charge to full...")
			time.sleep(300)

	return readyDev

def prepRun(readyDev, name):
	#Reset battery stats
	print("resetting battery stats..."), 
	runCmd("adb -s " + readyDev + " shell dumpsys batterystats --reset")
	print ("done!")

	#Reset logcat logs
	print ("resetting logcat logs..."), 
	runCmd("adb -s " + readyDev + " logcat -b all -c")
	print("done!")

	#Get state of the bt logs before starting
	print ("getting current state of btsnoop_hci.log..."), 
	timestr = time.strftime("%Y%m%d-%H%M%S")
	runCmd("adb -s " + readyDev + " pull sdcard/btsnoop_hci.log ./btsnoop_start_" + name+ "_" + timestr + ".log")
	print("done!")

	#Delete advertising stats
	print ("deleting packet capture files..."),
	runCmd("adb -s" + readyDev + " shell rm sdcard/Android/data/com.adafruit.bleuart/files/cap.txt")
	runCmd("adb -s" + readyDev + " shell rm sdcard/Android/data/com.adafruit.bleuart/files/gatt_cap.txt")
	print("done!")

def collect(dev, name, output, advLogging):
	timestr = time.strftime("%Y%m%d-%H%M%S")

	runCmd("adb -s "  + dev + " bugreport  > " + output + name + "-battery-" + timestr + ".zip")
	runCmd("adb -s " + dev + " pull sdcard/btsnoop_hci.log " + output + name + "-bt_log-" + timestr + ".log")
	runCmd("adb -s " + dev + " pull sdcard/Android/data/com.adafruit.bleuart/files/gatt_cap.txt " + output + name + "-gatt_cap-" + timestr + ".log")
	if advLogging:
		runCmd("adb -s " + dev + " pull sdcard/Android/data/com.adafruit.bleuart/files/cap.txt " + output + name + "-scan_cap-" + timestr + ".log")

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

	print ("running " + name + " on " + dev)

	if 'None' not in job['app']:
		runCmd("adb -s " + dev + " shell am start -n " + job['app'])
	
	
	collectData = False
	port = None

	advLogging = False
	for action in job['actions']:
		print(dev + ": " + str(action))
		if 'button' in action:
			pressButton(dev, action['button'])
		elif 'text' in action:
			if "--log-adv-t" in action['text']:
				advLogging = True

			runCmd("adb -s " + dev + " shell input text " + str(action['text']).replace(" ", "%s"))
		elif 'collect' in action:
			collectData = True
		elif 'screenOn' in action:
			toggleScreen(dev, action['screenOn'])
		elif 'pluggedIn' in action:
			if action['pluggedIn']:
				reconnectUSB(dev, port)
			else:
				port = disconnectUSB(dev)
		elif 'sleep' in action:
			time.sleep(int(action['sleep']))

	if 'None' not in job['app']:
		runCmd("adb -s " + dev + " shell am force-stop " + job['app'].split('/')[0])

	if collectData:
		collect(dev, name, output, advLogging)



def main():
	parser = argparse.ArgumentParser()
	parser.add_argument ("-i", "--input", required = True, help="path to jobs file")
	parser.add_argument ("-o", "--output", required = False, default='./', help="path to output directory")
	parser.add_argument ("-n", "--num_devs", default=1, help="number of devices to use")
	parser.add_argument('--full_batt', help='Require devices to have a full battery to run', action='store_true')
	parser.add_argument ('--sync', help='when -n is greater than 1, waits for all devices to be ready', action='store_true')
	args =  parser.parse_args()

	if not checkUserIsRoot():
		print ("Need root permissions (for enabling/disabling USB port)")
		exit(1)

	with open(args.input, "r") as f:
	    jobs = json.loads(f.read())

	proc = subprocess.Popen("adb devices | grep -w 'device'", shell=True, stdin=subprocess.PIPE,
	                     stdout=subprocess.PIPE,
	                     stderr=subprocess.PIPE)
	devices = []
	for line in proc.stdout.readlines():
		devices.append({"id" : line.split('\t')[0], "running" : False})

	#print(devices)

	for dev in devices:
		proc = subprocess.Popen("adb -s " + dev['id'] + " shell dumpsys battery | grep -m 1 level", shell=True, stdin=subprocess.PIPE,
	                         stdout=subprocess.PIPE,
	                         stderr=subprocess.PIPE)
		dev['battery'] = int(proc.stdout.readlines()[0].split(':')[1].strip())
	
	print("running job batch: " + jobs['name'])

	maxConcurrent = min(len(devices), args.num_devs)
	
	threads = []
	runningDevs = []
	jobCount = 0
	for job in jobs['jobs']:
		dev = checkDevAvailability(devices,  jobCount, args.full_batt)
		
		runningDevs.append((dev, job['name']))
		threads.append(threading.Thread(target = runJob, args = (job, dev, args.output, )))
		jobCount += 1
		
		if args.sync:
			if len(threads) == maxConcurrent:
				for t, d in zip(threads, runningDevs):
					prepRun(d[0], d[1])
					t.start()
				for t in threads:
					t.join()
				del threads[:]
				del runningDevs[:]
		else:
			prepRun(dev, job['name'],)
			threads[-1].start()		

			if len(threads) == maxConcurrent:
	    			threads[0].join()
				threads.pop(0)		
		 
			

if __name__ == '__main__':
	opLock = threading.Lock()
	main()
