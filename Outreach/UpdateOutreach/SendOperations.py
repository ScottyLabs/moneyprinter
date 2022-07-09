#!/usr/bin/env python
import requests

def send_simple_message (recipientList, api_key, domain, sendDomain):
	return requests.post(
		f"{domain}/messages",
		auth=("api", api_key),
		data={"from": f"Scottylabs <mailgun@{sendDomain}>",
			"to": recipientList,
			"subject": "Hello",
			"text": "Testing some Mailgun awesomness!"})


def send_template_message (recipientList, api_key, domain, sendDomain, template):
	return requests.post(
		f"{domain}/messages",
		auth=("api", api_key),
		data={"from": f"Scottylabs <mailgun@{sendDomain}>",
			"to": recipientList,
			"subject": "Hello from Scottylabs!",
			f"template": {template}
			})


