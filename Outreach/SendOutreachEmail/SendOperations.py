#!/usr/bin/env python
import requests

def send_simple_message (recipientList, api_key, domain):
	return requests.post(
		f"https://api.mailgun.net/v3/{domain}/messages",
		auth=("api", api_key),
		data={"from": f"Scotty Labs <mailgun@{domain}>",
			"to": recipientList,
			"subject": "Hello",
			"text": "Testing some Mailgun awesomness!"})


def send_template_message (recipientList, api_key, domain, template):
	return requests.post(
		f"https://api.mailgun.net/v3/{domain}/messages",
		auth=("api", api_key),
		data={"from": f"Scotty Labs <mailgun@{domain}>",
			"to": recipientList,
			"subject": "Hello from Scottylabs!",
			"template": template
			})


