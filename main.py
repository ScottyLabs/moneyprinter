#!/usr/bin/env python
# coding: utf-8

# In[1]:


import pygsheets
import pandas as pd
import requests
import secret
from SendOperations import send_simple_message , send_template_message


# In[2]:


gc = pygsheets.authorize(service_file='scotty-353808-bc21c60f8263.json')
sh = gc.open('Sponsor Outreach')
outreach = sh[1]
api_key = secret.api_key
domain = secret.domain


# In[3]:


df = outreach.get_as_df()


# In[5]:


def getOutreachEmail (df):
    filtereddf = df[(df["Status"] == "Outreach") & (df["Send New Email"] == "Yes")]
    return filtereddf["Email"].tolist()


# In[7]:


def checkValidStatusCode (response):
    statusCode = response.status_code
    if statusCode == 200:
        return "Emails Successfully Sent"
    else:
        return "Emails not sent, check Mailgun logs"


# In[17]:


def resetStatus (sheet, df):
    df["Send New Email"] = df["Send New Email"].apply (lambda x : "No")
    sheet.set_dataframe(df,(1,1))


# In[8]:


def sendoutreach (request) :
    emailingList = getOutreachEmail(df)
    response = send_template_message(emailingList, api_key, domain)
    resetStatus (outreach, df)
    return checkValidStatusCode (response)


# In[ ]:




