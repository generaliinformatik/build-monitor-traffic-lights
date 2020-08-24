import socket
import requests
import json
import subprocess
import sys


def get_ip_address():
    """
	Get IP address from shell script output

	Returns:
		str: IP address
	"""
    # get ip address from console
    return subprocess.check_output(
        ["/home/pi/ampel/scripts/parse_ip_addr.sh", "eth0"]
    ).decode(sys.stdout.encoding)


def main():
    """
	Function to send new IP address to mattermost channel
	"""
    mattermostWebHook = "https://<mattermost channel url>"
    print("Writing to Mattermost: " + mattermostWebHook)
    payload = {
        "attachments": [
            {
                "text": "Raspberry wurde neugestartet. IP: " + get_ip_address(),
                "color": "warning",
                "thumb_url": "http://<mattermost graphic url>/download/attachments/613124249/Ampel_gruen.jpg?api=v2",
            }
        ],
        "text": "IP Adresse",
        "channel": "#lampe",
        "icon_url": "http://<mattermost graphic url>/download/attachments/613124249/Ampel_gruen.jpg?api=v2",
    }
    headers = {"content-type": "application/json"}
    resp = requests.post(
        mattermostWebHook, data=json.dumps(payload), headers=headers, verify=False
    )
    print("Done with status " + str(resp))


if __name__ == "__main__":
    main()
