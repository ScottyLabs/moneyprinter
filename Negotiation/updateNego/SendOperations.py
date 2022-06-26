#!/usr/bin/env python
import requests

def send_simple_message (recipientList, api_key, domain):
	return requests.post(
		f"{domain}/messages",
		auth=("api", api_key),
		data={"from": "Tze Hng <mailgun@sandbox0d2217c926064a2d944389872026616f.mailgun.org>",
			"to": recipientList,
			"subject": "Hello",
			"text": "Testing some Mailgun awesomness!"})


def send_template_message (recipientList, api_key, domain):
	return requests.post(
		f"{domain}/messages",
		auth=("api", api_key),
		data={"from": "Tze Hng <mailgun@sandbox0d2217c926064a2d944389872026616f.mailgun.org>",
			"to": recipientList,
			"subject": "Hello",
			"template": "testing",
			"v:test" : "test"
			})


