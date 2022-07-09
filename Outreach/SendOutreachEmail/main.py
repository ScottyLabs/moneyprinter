import pygsheets
import pandas as pd
import requests
from SendOperations import send_simple_message , send_template_message
import os

# In[2]:

gc = pygsheets.authorize(service_file = 'scottylabssponsor-9ee3dc6d59b9.json')
sh = gc.open('Sponsor Outreach')
outreach = sh[1]


# In[3]:


def env_vars(request, key):
    return str(os.environ.get(key, 'Specified environment variable is not set.'))



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
    df = outreach.get_as_df()
    recipientsList = getOutreachEmail(df)
    api_key = env_vars (request, 'mailgun_api_key')
    domain = env_vars (request, 'mailgun_domain')
    template = env_vars (request, 'template')    
    response = send_template_message(recipientsList, api_key, domain, template)
    resetStatus (outreach, df)
    return checkValidStatusCode (response)



