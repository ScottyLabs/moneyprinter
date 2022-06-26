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
negotiation = sh[2]
api_key = secret.api_key
domain = secret.domain


# In[3]:


def makeNewRow (row, negotiation_cols_list, filtered_cols_list):
    result = {}
    for colname in negotiation_cols_list:
        if colname in filtered_cols_list:
            result[colname] = row[colname]          
        else:
            result[colname] = "Null"           
    return result


# In[4]:


def removeNegotiationfromOutreach (outreach_df):
    noNego = outreach_df[(outreach_df["Status"] != "Negotiating")]
    outreach.clear()
    outreach.set_dataframe(noNego,(1,1))
    


# In[5]:


def updateNegotiation (request):
    outreach_df = outreach.get_as_df()
    negotiation_df = negotiation.get_as_df()
    #get the negotiating rows
    filtereddf = outreach_df[(outreach_df["Status"] == "Negotiating")]
    filtered_cols_list = filtereddf.columns.to_list()
    negotiation_cols_list = negotiation_df.columns.to_list()
    
    for index, row in filtereddf.iterrows():
        newrow = makeNewRow (row, negotiation_cols_list, filtered_cols_list)
        rowdf = pd.DataFrame(newrow,index=[0])
        negotiation_df = pd.concat([negotiation_df, rowdf], ignore_index=True)
        
        
    negotiation.set_dataframe(negotiation_df,(1,1))
    removeNegotiationfromOutreach (outreach_df)

    return "Successfully updated Negotiation"

