#! /usr/bin/env python3
import requests
import time
import datetime
import sys
import json
from os import path
import yaml
import hashlib
import logging
from sys import stderr

debug_mode = True

if debug_mode is not True:
    import avea


debug_level = "DEBUG"
config_file = "../../config.yml"

debug_level_old = "INFO"
# initialize dynamic debug level
logging.basicConfig(stream=stderr, level=logging.INFO)
if "debug_level_old" not in locals():
    debug_level_old = "INFO"
if debug_level != debug_level_old:
    if debug_level == "DEBUG":
        logging.getLogger().setLevel(logging.DEBUG)
    elif debug_level == "INFO":
        logging.getLogger().setLevel(logging.INFO)
    elif debug_level == "WARNING":
        logging.getLogger().setLevel(logging.WARNING)
    elif debug_level == "ERROR":
        logging.getLogger().setLevel(logging.ERROR)
    elif debug_level == "CRITICAL":
        logging.getLogger().setLevel(logging.CRITICAL)
    else:
        logging.getLogger().setLevel(logging.INFO)
    logging.info("debug level set dynamically to: %s", debug_level)
    debug_level_old = debug_level


logging.debug("Initialize varaibles...")

payload = {
    "attachments": [],
    "text": "replace-me",
    "channel": "replace-me",
    "icon_url": "replace-me",
}

dirname = path.dirname(__file__)
timestampFile = ""
historyfile = ""
buildJobs = {}
config = {}
statusList = []


def load_config():
    """
    Loads configuration from yml to dictionary
    """
    logging.info("Loading config from %s", (config_file))
    try:
        stream = open(path.join(dirname, config_file), "r")
    except Exception:
        logging.error("Config file not found! Abort.")
        sys.exit(1)

    global config
    config = yaml.safe_load(stream)
    load_bulb(config)
    load_jenkins(config)
    load_mattermost(config)
    changePayload(config)


def load_bulb(config):
    """
    Loads bulb MAC adresses

    Args:
        config ([type]): [description]
    """

    this_bulb = None
    logging.debug("Loading bulb parameters...")
    global bulbAddrRot
    this_bulb = "red"
    bulbAddrRot = config["bulbs"]["red"]["addr"]
    logging.debug(
        "Loading bulb config. ID '%s' set to '%s'.",
        config["bulbs"][this_bulb]["name"],
        config["bulbs"][this_bulb]["addr"],
    )

    global bulbAddrGelb
    this_bulb = "yellow"
    bulbAddrGelb = config["bulbs"]["yellow"]["addr"]
    logging.debug(
        "Loading bulb config. ID '%s' set to '%s'.",
        config["bulbs"][this_bulb]["name"],
        config["bulbs"][this_bulb]["addr"],
    )

    global bulbAddrGruen
    this_bulb = "green"
    bulbAddrGruen = config["bulbs"]["green"]["addr"]
    logging.debug(
        "Loading bulb config. ID '%s' set to '%s'.",
        config["bulbs"][this_bulb]["name"],
        config["bulbs"][this_bulb]["addr"],
    )
    logging.debug("Done.")


def load_jenkins(config):
    """
    Loads Jenkins configuration

    Args:
        config ([dict]): Dictionary with configuration settings
    """
    logging.debug("Loading Jenkins parameters...")
    jenkinsUrl = config["jenkins"]["url"]
    jenkinsPort = config["jenkins"]["port"]
    global buildJobs
    for buildJob, link in config["jenkins"]["jobs"].items():
        buildJobs[buildJob] = jenkinsUrl + ":" + str(jenkinsPort) + "/" + link
    global historyfile
    historyfile = config["home"] + "/" + config["jenkins"]["historyfile"]
    logging.debug("Done.")


def load_mattermost(config):
    """
    Loads mattermost configuration

    Args:
        config (dict): Dictionary with configuration settings
    """
    logging.debug("Loading Mattermost parameters...")
    global timestampFile
    timestampFile = config["home"] + "/" + config["mattermost"]["updateFile"]
    logging.debug("Done.")


def changePayload(config):
    """
    Loads mattermost channel payload

    Args:
        config (dict): Dictionary with configuration settings
    """
    logging.debug("Loading Payload parameters...")
    global payload
    payload["channel"] = config["mattermost"]["channel"]
    logging.debug("Done.")


def main():
    """
    Main function to set bulbs based on Jenkins pipeline status
    """
    logging.info(
        "### Starting scan at "
        + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
    )
    #    bulbRot = None
    #    bulbGelb = None
    #    bulbGruen = None

    if debug_mode is not True:
        #        bulbRot = getBulb(config["bulbs"]["red"]["addr"])
        #        bulbGelb = getBulb(config["bulbs"]["yellow"]["addr"])
        #        bulbGruen = getBulb(config["bulbs"]["green"]["addr"])
        config["bulbs"]["red"]["ref"] = getBulb(config["bulbs"]["red"]["addr"])
        config["bulbs"]["yellow"]["ref"] = getBulb(config["bulbs"]["yellow"]["addr"])
        config["bulbs"]["green"]["ref"] = getBulb(config["bulbs"]["green"]["addr"])
    else:
        config["bulbs"]["red"]["ref"] = None
        config["bulbs"]["yellow"]["ref"] = None
        config["bulbs"]["green"]["ref"] = None

    failedJobs = []
    try:
        history = readHistory()
        for buildJob, link in buildJobs.items():
            resp = requests.get(link, verify=False)  # nosec
            logging.debug(resp)
            logging.debug(buildJob + " -> " + resp.text)
            hashedjobname = hashname(buildJob)
            if resp.text in config["jenkins"]["success_status"]:
                statusList.append(True)
                history[hashedjobname] = True
            elif resp.text in config["jenkins"]["fail_status"]:
                statusList.append(False)
                history[hashedjobname] = False
                failedJobs.append(
                    "[" + buildJob + "](" + generateBuildUrlFromStatusLink(link) + ")"
                )
            else:
                logging.info("### " + buildJob + " is currently running...")
                if hashedjobname in history:
                    historyvalue = history[hashedjobname]
                    logging.info(
                        "### Found history entry for "
                        + buildJob
                        + ": "
                        + str(historyvalue)
                    )
                    statusList.append(historyvalue)
                    if not historyvalue:
                        failedJobs.append(
                            "["
                            + buildJob
                            + "]("
                            + generateBuildUrlFromStatusLink(link)
                            + ")"
                            + " (laeuft gerade)"
                        )
                else:
                    logging.warning(
                        "### No history found for " + buildJob + ". Using default: True"
                    )
                    statusList.append(True)

        writeHistory(history)
        isCool = all(statusList)

        postStatusToMattermost(isCool, failedJobs)

        if isCool:
            logging.info("### Jenkins build was cool")
            turnOff(config["bulbs"]["red"])
            turnOff(config["bulbs"]["yellow"])
            blink(config["bulbs"]["green"], 2)
            turnOn(config["bulbs"]["green"])
        else:
            logging.info("### Jenkins build was uncool")
            turnOff(config["bulbs"]["green"])
            turnOff(config["bulbs"]["yellow"])
            blink(config["bulbs"]["red"], 2)
            turnOn(config["bulbs"]["red"])
        logging.info("### Scan done successfully")

    except Exception as e:
        turnOn(config["bulbs"]["yellow"])
        turnOff(config["bulbs"]["green"])
        turnOff(config["bulbs"]["red"])
        blink(config["bulbs"]["yellow"], 10)
        logging.error("Error: %s", e)
        logging.error("### Scan done with errors")


def generateBuildUrlFromStatusLink(link):
    """
    Redefine Jenkins build URL based on Jenkins status link

    Args:
        link (str): String with Jenkins Status URL

    Returns:
        [str]: String with Jenkins Build URL
    """
    logging.info("Incoming link: " + link)
    link = link.replace(
        "buildStatus/text?job=PIA-Agilisierung%2F",
        "view/Openshift/job/PIA-Agilisierung/job/",
    )
    logging.info("Outgoing link: " + link)
    return link


def postStatusToMattermost(isCool, failedJobs):
    """
    Post status message to mattermost channel

    Args:
        isCool (bool): status of Jenkins build
        failedJobs (list): list of failed Jenkins jobs
    """
    logging.info("### Post status to Mattermost")
    lastWritten = readTimestamp(timestampFile)
    minWaitTime = datetime.timedelta(minutes=config["mattermost"]["timeToWait"])
    currentTimeObj = datetime.datetime.now()
    if currentTimeObj - lastWritten > minWaitTime:
        if isCool:
            payload["text"] = "Aktueller Buildstatus: Grün"
            payload[
                "icon_url"
            ] = "http://<mattermost graphic url>/download/attachments/613124249/Ampel_gruen.jpg?api=v2"
        else:
            payload["text"] = "Kaputte Builds:\n" + "\n".join(failedJobs)
            payload[
                "icon_url"
            ] = "http://<mattermost graphic url>/download/attachments/613124249/Ampel_rot.jpg?api=v2"
        logging.info("Message to Mattermost: " + payload["text"])
        try:
            requests.post(
                config["mattermost"]["url"],
                data=json.dumps(payload),
                headers={"content-type": "application/json"},
                verify=False,  # nosec
            )
            logging.error("Request sent to Mettermost...")
        except Exception:
            logging.error("Failed to send request to Mettermost...")

        writeTimestamp(timestampFile, currentTimeObj)


def turnOff(myBulb):
    """
    Turn off given bulb

    Args:
        myBulb (object): Bulb object
    """
    logging.debug("Set bulb '%s' to OFF.", (str(myBulb["name"])))
    if debug_mode is not True:
        myBulb["ref"].set_brightness(0)


def turnOn(myBulb):
    """
    Turn on given bulb

    Args:
        myBulb (object): Bulb object
    """
    logging.debug("Set bulp '%s' to ON.", (str(myBulb["name"])))
    if debug_mode is not True:
        myBulb["ref"].set_brightness(4095)


def hashname(name):
    """
    Hash given string

    Args:
        name (str): String to be hashed

    Returns:
        [str]: Hashed string
    """
    #    return str(hashlib.sha1(name.encode()).hexdigest())
    return str(hashlib.sha256(name.encode()).hexdigest())


def readHistory():
    """
    Read history file with saved history values

    Returns:
        list: List with hitory
    """
    history = {}
    try:
        file = open(historyfile, "r")
        for line in file.readlines():
            if len(line) > 0:
                key, value = line.split()
                history[key] = value == "True"
        file.close()
    except Exception:
        logging.error("Failed to read from history file: %s", (historyfile))

    return history


def writeHistory(history):
    """
    Writes history to file

    Args:
        history (list): List with history data
    """
    try:
        file = open(historyfile, "w")
        file.truncate(0)
        for key, value in history.items():
            file.write(key + " " + str(value) + "\n")
        file.close()
    except Exception:
        logging.error("Failed to write to hstory file: %s", (historyfile))


def getBulb(myBulb):
    """
    Get bulb object from given MAC addtess

    Args:
        myBulb (object): object of bulb

    Raises:
        Exception: bulb address not found

    Returns:
        object: bulb object
    """
    bulb = avea.Bulb(myBulb["addr"])
    if bulb.get_name != "Unknown":
        logging.debug("Bulb '%s' found.", str(myBulb["name"]))
        return bulb
    else:
        logging.error("No bulb '%s' found.", str(myBulb["name"]))
        raise Exception("No bulb '%s' found.", str(myBulb["name"]))


def blink(myBulb, times):
    """
    Blinks a given bulb n times

    Args:
        myBulb (object): bulb object
        times (int): number of blinks
    """
    #    logging.info("### blink, blink, blink")
    for x in range(0, times):
        if debug_mode is not True:
            myBulb["ref"].set_brightness(1)
            time.sleep(0.3)
            myBulb["ref"].set_brightness(4095)
            time.sleep(0.5)
            logging.info("Blink '%s' bulb...", str(myBulb["name"]))
        else:
            logging.debug("Blink '%s' bulb... (debug)", str(myBulb["name"]))


def readTimestamp(filename):
    """
    Reads date-/timestamp from file

    Args:
        filename (str): filename to be written

    Returns:
        str: date-/timestamp
    """
    file = open(filename, "r")
    savedTimestamp = file.readline()
    file.close()
    if len(savedTimestamp) == 0:
        return datetime.datetime.strptime(
            "1970-01-01 00:00:00.000", "%Y-%m-%d %H:%M:%S.%f"
        )
    else:
        logging.debug("### Found last written timestamp: " + savedTimestamp)
        return datetime.datetime.strptime(savedTimestamp, "%Y-%m-%d %H:%M:%S.%f")


def writeTimestamp(filename, currentTimestamp):
    """
    Writes date-/timestamp to file

    Args:
        filename (str): filename to be written
        currentTimestamp (str): date-/timestamp to be written
    """
    logging.debug(
        "### Writing to file '"
        + filename
        + "' content: "
        + currentTimestamp.strftime("%Y-%m-%d %H:%M:%S.%f")
    )
    try:
        file = open(filename, "w")
        file.truncate(0)
        file.write(currentTimestamp.strftime("%Y-%m-%d %H:%M:%S.%f"))
        file.close()
    except Exception:
        logging.error("Failed to write to timestamp file: %s", (filename))


if __name__ == "__main__":
    load_config()
    main()
