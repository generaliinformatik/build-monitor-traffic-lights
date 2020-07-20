import avea
import requests
import time
import datetime
import sys
import json
from os import path
import yaml
import hashlib

payload = {
    "attachments": [],
    "text":"replace-me",
    "channel":"replace-me",
    "icon_url":"replace-me"
}

colorRot = (255,0,0,1)
colorGruen = (0,200,0,1)
colorGelb = (207,95,0,1)
buildJobs = {}
timestampFile = ''
historyfile = ''
config = {}
dirname = path.dirname(__file__)
bulbAddrRot = ""
bulbAddrGelb = ""
bulbAddrGruen = ""
statusList = []

def load_config():
    '''Loads configuration from yml to dictionary
    '''
    stream = open(path.join(dirname, '../../config.yml'), 'r')
    global config
    config = yaml.load(stream, Loader=yaml.FullLoader)
    load_bulb(config)
    load_jenkins(config)
    load_mattermost(config)
    changePayload(config)

def load_bulb(config):
    '''Loads bulb MAC adresses

    Args:
        config ([type]): [description]
    '''
    global bulbAddrRot
    bulbAddrRot = config['bulbs']['bulbaddrrot']
    global bulbAddrGelb
    bulbAddrGelb = config['bulbs']['bulbaddrgelb']
    global bulbAddrGruen
    bulbAddrGruen = config['bulbs']['bulbaddrgruen']

def load_jenkins(config):
    '''Loads Jenkins configuration

    Args:
        config ([dict]): Dictionary with configuration settings
    '''
    jenkinsUrl = config['jenkins']['url']
    jenkinsPort = config['jenkins']['port']
    global buildJobs
    for buildJob, link in config['jenkins']['jobs'].items():
        buildJobs[buildJob] = jenkinsUrl + ':' + str(jenkinsPort) + '/' + link
    global historyfile
    historyfile = config['home'] + '/' + config['jenkins']['historyfile']

def load_mattermost(config):
    '''Loads mattermost configuration

    Args:
        config (dict): Dictionary with configuration settings
    '''
    global timestampFile
    timestampFile = config['home'] + '/' + config['mattermost']['updateFile']

def changePayload(config):
    '''Loads mattermost channel payload

    Args:
        config (dict): Dictionary with configuration settings
    '''
    global payload
    payload['channel'] = config['mattermost']['channel']

def main():
    '''Main function to set bulbs based on Jenkins pipeline status
    '''
    print("### Starting scan at " + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f'))
    bulbRot = getBulb(bulbAddrRot)
    bulbGelb = getBulb(bulbAddrGelb)
    bulbGruen = getBulb(bulbAddrGruen)
    failedJobs = []
    try:
        history = readHistory()
        for buildJob, link in buildJobs.items():
            resp = requests.get(link, verify=False)
            print(resp)
            print(buildJob + " -> " + resp.text)
            hashedjobname = hashname(buildJob)
            if resp.text in config['jenkins']['success_status']:
                statusList.append(True)
                history[hashedjobname] = True
            elif resp.text in config['jenkins']['fail_status']:
                statusList.append(False)
                history[hashedjobname] = False
                failedJobs.append('[' + buildJob + '](' + generateBuildUrlFromStatusLink(link) + ')')
            else:
                print("### " + buildJob + " is currently running...")
                if hashedjobname in history:
                    historyvalue = history[hashedjobname]
                    print("### Found history entry for " + buildJob + ": " + str(historyvalue))
                    statusList.append(historyvalue)
                    if not historyvalue:
                        failedJobs.append('[' + buildJob + '](' + generateBuildUrlFromStatusLink(link) + ')' + ' (läuft gerade)')
                else:
                    print("### No history found for " + buildJob + ". Using default: True")
                    statusList.append(True)

        writeHistory(history)
        isCool = all(statusList)

        postStatusToMattermost(isCool, failedJobs)

        if isCool:
            print("### Jenkins build was cool")
            turnOff(bulbRot)
            turnOff(bulbGelb)
            blink(bulbGruen, 2)
            turnOn(bulbGruen)
        else:
            print("### Jenkins build was uncool")
            turnOff(bulbGruen)
            turnOff(bulbGelb)
            blink(bulbRot, 2)
            turnOn(bulbRot)
        print("### Scan done successfully")
    except Exception as e:
        turnOn(bulbGelb)
        turnOff(bulbGruen)
        turnOff(bulbRot)
        blink(bulbGelb, 10)
        print(e)
        print("### Scan done with errors")

def generateBuildUrlFromStatusLink(link):
    '''Redefine Jenkins build URL based on Jenkins status link

    Args:
        link (str): String with Jenkins Status URL

    Returns:
        [str]: String with Jenkins Build URL
    '''
    print("Incoming link: " + link)
    link = link.replace("buildStatus/text?job=PIA-Agilisierung%2F", "view/Openshift/job/PIA-Agilisierung/job/")
    print("Outgoing link: " + link)
    return link

def postStatusToMattermost(isCool, failedJobs):
    '''Post status message to mattermost channel

    Args:
        isCool (bool): status of Jenkins build
        failedJobs (list): list of failed Jenkins jobs
    '''
    print("### Post status to Mattermost")
    lastWritten = readTimestamp(timestampFile)
    minWaitTime = datetime.timedelta(minutes=config['mattermost']['timeToWait'])
    currentTimeObj = datetime.datetime.now()
    if currentTimeObj - lastWritten > minWaitTime:
        if isCool:
            payload['text'] = 'Aktueller Buildstatus: Grün'
            payload['icon_url'] = 'http://<mattermost graphic url>/download/attachments/613124249/Ampel_gruen.jpg?api=v2'
        else:
            payload['text'] = 'Kaputte Builds:\n' + '\n'.join(failedJobs)
            payload['icon_url'] = 'http://<mattermost graphic url>/download/attachments/613124249/Ampel_rot.jpg?api=v2'
        print("Nachricht an Mattermost: " + payload['text'])
        resp = requests.post(config['mattermost']['url'] ,data=json.dumps(payload), headers={'content-type': 'application/json'}, verify=False)
       	writeTimestamp(timestampFile, currentTimeObj)

def turnOff(bulb):
    '''Turn off given bulb

    Args:
        bulb (object): Bulb object
    '''
    bulb.set_brightness(0)

def turnOn(bulb):
    '''Turn on given bulb

    Args:
        bulb (object): Bulb object
    '''
    bulb.set_brightness(4095)

def hashname(name):
    '''Hash given string

    Args:
        name (str): String to be hashed

    Returns:
        [str]: Hashed string
    '''
    return str(hashlib.sha1(name.encode()).hexdigest())

def readHistory():
    '''Read history file with saved history values

    Returns:
        list: List with hitory
    '''
    history = {}
    file = open(historyfile, 'r')
    for line in file.readlines():
        if len(line) > 0:
            key, value = line.split()
            history[key] = value == 'True'
    file.close()
    return history

def writeHistory(history):
    '''Writes history to file

    Args:
        history (list): List with history data
    '''
    file = open(historyfile, 'w')
    file.truncate(0)
    for key, value in history.items():
        file.write(key + " " + str(value) + "\n")
    file.close()

def getBulb(bulbAddr):
    '''Get bulb object from given MAC addtess

    Args:
        bulbAddr (str): MAC address of bulb

    Raises:
        Exception: bulb address not found

    Returns:
        object: bulb object
    '''
    bulb = avea.Bulb(bulbAddr)
    if bulb.get_name != "Unknown":
        return bulb
    else:
        raise Exception('no bulb found')

def blink(myBulb, times):
    '''Blinks a given bulb n times

    Args:
        myBulb (object): bulb object
        times (int): number of blinks
    '''
    print("### blink, blink, blink")
    for x in range(0,times):
        myBulb.set_brightness(1)
        time.sleep(0.3)
        myBulb.set_brightness(4095)
        time.sleep(0.5)

def readTimestamp(filename):
    '''Reads date-/timestamp from file

    Args:
        filename (str): filename to be written

    Returns:
        str: date-/timestamp
    '''
	file = open(filename, 'r')
	savedTimestamp = file.readline()
	file.close()
	if len(savedTimestamp)==0:
	    return datetime.datetime.strptime('1970-01-01 00:00:00.000', '%Y-%m-%d %H:%M:%S.%f')
	else:
		print("### Found last written timestamp: " + savedTimestamp)
		return datetime.datetime.strptime(savedTimestamp, '%Y-%m-%d %H:%M:%S.%f')

def writeTimestamp(filename, currentTimestamp):
    '''Writes date-/timestamp to file

    Args:
        filename (str): filename to be written
        currentTimestamp (str): date-/timestamp to be written
    '''
	print("### Writing to file '" + filename + "' content: " + currentTimestamp.strftime('%Y-%m-%d %H:%M:%S.%f'))
	file = open(filename, 'w')
	file.truncate(0)
	file.write(currentTimestamp.strftime('%Y-%m-%d %H:%M:%S.%f'))
	file.close()

if __name__ == '__main__':
    load_config()
    main()