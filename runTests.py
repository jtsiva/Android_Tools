import json
import argparse
import subprocess
import os
import time
from datetime import datetime
import re
import threading


def checkUserIsRoot():
	return 0 == os.getuid()

def runCmd(cmd, output = False, bg  = False):
	out = None
	#with opLock:
	if bg:
		proc = subprocess.Popen(cmd, shell=True)
	else:
		proc = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE,
		                     stdout=subprocess.PIPE,
		                     stderr=subprocess.PIPE)
	
	if output:
		out = proc.stdout.read().decode('utf-8')
	elif not bg:
		proc.wait()

	return out
	

def disconnectUSB(dev):
	out = runCmd("uhubctl | grep " + dev, output=True).split('\n')
	port = re.search(r'\d+', out[0]).group()

	runCmd("uhubctl -a 0 -p " + port)

	return port
	
def reconnectUSB(dev, port):
	runCmd("uhubctl -a 1 -p " + port)
	time.sleep(3)
	out = runCmd("adb devices | grep " + dev + " | wc -l", output=True)
	while not (1 == int(out)):
		print("."),
		runCmd("uhubctl -a 2 -p " + port) #cycling the power seems to make sure it comes back
		time.sleep(3)
		out = runCmd("adb devices | grep " + dev + " | wc -l", output=True)

	print("")

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
			time.sleep(60)

	return readyDev

def prepRun(readyDev, name, output, needBTSave = True):
	
	if 'hold' not in name:
		#Reset battery stats
		print("resetting battery stats..."), 
		runCmd("adb -s " + readyDev + " shell dumpsys batterystats --reset")
		print ("done!")

		#Reset logcat logs
		print ("resetting logcat logs..."), 
		runCmd("adb -s " + readyDev + " logcat -b all -c")
		print("done!")


		#Delete advertising stats
		print ("deleting packet capture files..."),
		runCmd("adb -s " + readyDev + " shell rm sdcard/Android/data/edu.nd.cse.gatt_client/files/*")
		print("done!")

def collect(dev, name, output, collectOptions):
	timestr = time.strftime("%Y%m%d%H%M%S")

	if None is not collectOptions: #minimal data
		runCmd("adb -s " + dev + " pull sdcard/Android/data/edu.nd.cse.gatt_client/files/ " + output)
		
		if iperfCmd is not None:
			while not os.path.exists(output+'files/'):
				time.sleep(1) #wait after pulling to make sure we have all the files over
			wifiOutputFixup(dev, output + 'files/', name)

		runCmd("mv " + output + "files/* " + output)
		runCmd("rm -r " + output + "files/")

		if 'bt' in collectOptions:
			runCmd("adb -s "  + dev + " bugreport bugreport.zip")
			runCmd("unzip bugreport.zip -d bugreport_tmp")
			runCmd("mv bugreport_tmp/bugreport-* bugreport_tmp/bugreport.txt")
			runCmd("python btsnooze.py bugreport_tmp/bugreport.txt > " + output + name + "-btsnoop-" + timestr + ".log")
			runCmd("rm -r bugreport_tmp/")
			runCmd("rm bugreport.zip")
		elif 'all' in collectOptions:
			runCmd("adb -s "  + dev + " bugreport  " + output + name + "-bugreport-" + timestr + ".zip")

		


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
	coords = runCmd("adb -s " + dev + " shell -x uiautomator dump  /dev/fd/1 | perl -ne 'printf \"%d %d\n\", ($1+$3)/2, ($2+$4)/2 if /text=\"" + name + "\" [^>]*bounds=\"\[(\d+),(\d+)\]\[(\d+),(\d+)\]\"/' -",
			output=True)

	runCmd("adb -s " + dev + " shell input tap " + coords)

def waitForApp (dev, app, timeout=0):
	start = datetime.now()

	currentTime = datetime.now()

	time.sleep(5)

	while (0 == timeout or timeout > (currentTime - start).seconds) and isAppRunning(dev, app):
		time.sleep(5)
		currentTime = datetime.now()

	if timeout < (currentTime - start).seconds:
		print("xxxxx Test timed out! xxxxx")
	else:
		print("completed in: " + str((currentTime - start).seconds) + " seconds")


def isAppRunning (dev, app):
	out = runCmd ("adb -s " + dev + " shell pidof " + app.split('/')[0], output=True)

	return 0 < len(out)

def wifiOutputFixup(dev, outputDir, app):
	import pandas as pd

	"""
	Need to get the wifi rate, which device was involved (client or server), and which
	direction the traffic was flowing

	We can get the rate and direction from the iperf command itself
	we can either get who was involved by checking the app name for 'client' or 'server'
	"""
	rate = None
	direction = None
	target = None
	global iperfCmd
	global trafficIsParallel

	cmds = iperfCmd.split('>')[0]
	

	match = re.search('-b(\s+)(\d+[KMG])', cmds)
	if match:
		rate = match.group(2)

	if '-R' in cmds:
		direction = 'out'
	else:
		direction = 'in'

	#is the traffic in parallel to BLE traffic or ambient?
	if trafficIsParallel:
		#we only want to try to edit files if we are on the client (who collected the data)
		if 'client' in app:
			if isAppRunning(dev, "com.nextdoordeveloper.miperf.miperf/com.nextdoordeveloper.miperf.miperf.MainActivity"):
				target = 'client'
			else:
				target = 'server'
	else:
		target = 'other'
		direction = 'none'

	if 'client' in app:
		iperfCmd = None
		# print ("DEBUG rate: " + rate)
		# print ("DEBUG dir: " + direction)
		# print ("DEBUG target: " + target)

		for filename in os.listdir(outputDir):
			print (outputDir + filename)	
			csv_input = pd.read_csv(outputDir + filename)
			csv_input['wifi_rate'] = rate
			csv_input['wifi_dir'] = direction
			csv_input['wifi_target'] = target

			csv_input.to_csv(outputDir + filename, index=False)
	

def runJob(job, dev, output):
	name = job['name']
	if not os.path.isdir(output):
		output = './'

	shellCmd = False
	if 'shell' not in job['app']:
		print ("running " + name + " on " + dev)
	else:
		shellCmd = True
		print ("running shell command")

	if 'None' not in job['app'] and not shellCmd:
		runCmd("adb -s " + dev + " shell am start -a android.intent.action.MAIN -c android.intent.category.LAUNCHER -n " + job['app'])
	
	global iperfCmd
	global trafficIsParallel

	if 'iperf' in job['app']:
		trafficIsParallel = True
	
	collectData = None
	port = None

	noKill = False
	for action in job['actions']:
		print(dev + ": " + str(action))
		if 'button' in action:
			pressButton(dev, action['button'])
		elif 'text' in action:
			if shellCmd:
				if 'iperf' in name:
					if 'kill' in name:
						print ("killing iperf3....")
						runCmd('sudo pkill iperf3')
					else:
						iperfCmd = action['text']
						#get ip addr
						#print('adb -s ' + dev + ' shell ifconfig wlan0 | grep -oE \"\\b([0-9]{1,3}\.){3}[0-9]{1,3}\\b\" | head -1')
						ipAddr = runCmd('adb -s ' + dev + ' shell ifconfig wlan0 | grep -oE \"\\b([0-9]{1,3}\.){3}[0-9]{1,3}\\b\" | head -1', output=True)
						
						#start iperf!
						#print("iperf3 -c " + ipAddr.strip() + " -i 0 -u -p 5201 " + action['text'])
						runCmd("iperf3 -c " + ipAddr.strip() + " -i 0 -u -p 5201 " + iperfCmd, bg=True)
				else:
					if 'iperf' in action['text']:
						iperfCmd = action['text']
					runCmd(action['text'])
			else:
				#clear any text
				runCmd("adb -s " + dev + " shell input keyevent KEYCODE_MOVE_END")
				runCmd("adb -s " + dev + " shell input keyevent --longpress " + " ".join(['KEYCODE_DEL']*50))

				#now enter text
				runCmd("adb -s " + dev + " shell input text " + str(action['text']).replace(" ", "%s"))
		elif 'collect' in action:
			if action['collect'] or 'true' in action['collect']:
				collectData = 'min'
			elif 'bt' in action['collect']:
				collectData = 'bt' #including min
			elif 'all' in action['collect']:
				collectData = 'all'
			else:
				collectData = None

		elif 'screenOn' in action:
			toggleScreen(dev, action['screenOn'])
		elif 'pluggedIn' in action:
			if action['pluggedIn']:
				reconnectUSB(dev, port)
			else:
				port = disconnectUSB(dev)
		elif 'sleep' in action:
			time.sleep(int(action['sleep']))
		elif 'noKill' in action:
			noKill = bool(action['noKill'])
		elif 'wait' in action:
			waitForApp(dev, job['app'], action['wait'])

	if 'None' not in job['app'] and not noKill:
		runCmd("adb -s " + dev + " shell am force-stop " + job['app'].split('/')[0])

	collect(dev, name, output, collectData)


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
		devices.append({"id" : line.decode('utf-8').split('\t')[0], "running" : False})

	#print(devices)

	for dev in devices:
		proc = subprocess.Popen("adb -s " + dev['id'] + " shell dumpsys battery | grep -m 1 level", shell=True, stdin=subprocess.PIPE,
	                         stdout=subprocess.PIPE,
	                         stderr=subprocess.PIPE)
		dev['battery'] = int(proc.stdout.readlines()[0].decode('utf-8').split(':')[1].strip())
	
	print("running job batch: " + jobs['name'])

	maxConcurrent = min(len(devices), int(args.num_devs))
	
	threads = []
	runningDevs = []
	jobCount = 0
	for job in jobs['jobs']:
		dev = checkDevAvailability(devices,  jobCount, args.full_batt)
		
		skipPrep = 'None' in job['app']
		for action in job['actions']:
			if 'collect' in action:
				if not action['collect']:
					skipPrep = True
			else:
				skipPrep = True

		runningDevs.append((dev, job['name'], skipPrep))
		threads.append(threading.Thread(target = runJob, args = (job, dev, args.output, )))
		jobCount += 1
		
		if args.sync:
			if len(threads) == maxConcurrent:
				for t, d in zip(threads, runningDevs):
					prepRun(d[0], d[1], args.output, not d[2])
					
					t.start()
				for t in threads:
					t.join()
				del threads[:]
				del runningDevs[:]
		else:
			if not skipPrep: 
				prepRun(dev, job['name'],args.output)
			threads[-1].start()		

			if len(threads) == maxConcurrent:
				threads[0].join()
				threads.pop(0)
			#
		#
	#
		 
			

if __name__ == '__main__':
	iperfCmd = None
	trafficIsParallel = False
	opLock = threading.Lock()
	main()
