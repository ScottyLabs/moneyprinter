#!/usr/bin/env python
import requests
import secret

api_key = secret.api_key
domain = "https://api.mailgun.net/v3/sandbox0d2217c926064a2d944389872026616f.mailgun.org"

def send_simple_message ():
	return requests.post(
		f"{domain}/messages",
		auth=("api", api_key),
		data={"from": "Tze Hng <mailgun@sandbox0d2217c926064a2d944389872026616f.mailgun.org>",
			"to": ["tloke@andrew.cmu.edu"],
			"subject": "Hello",
			"text": "Testing some Mailgun awesomness!"})


def send_template_message():
	return requests.post(
		f"{domain}/messages",
		auth=("api", api_key),
		data={"from": "Tze Hng <mailgun@sandbox0d2217c926064a2d944389872026616f.mailgun.org>",
			"to": ["tloke@andrew.cmu.edu"],
			"subject": "Hello",
			"template": "testing",
			"v:test" : "test"
			})


send_template_message()

