#!/usr/bin/env python
# coding: utf-8

# In[1]:


import pygsheets
import pandas as pd
import requests
import os


# In[2]:


gc = pygsheets.authorize(service_file = 'scottylabssponsor-9ee3dc6d59b9.json')
sh = gc.open('Sponsor Outreach')
negotiation = sh[2]
deliverables = sh[3]

# In[3]:


def makeNewRow (row, deliverables_cols_list, filtered_cols_list):
    result = {}
    for colname in deliverables_cols_list:
        if colname in filtered_cols_list:
            result[colname] = row[colname]          
        else:
            result[colname] = "Null"           
    return result


# In[4]:


def removeConfirmedfromNego (nego_df):
    noConfirmed = nego_df[(nego_df["Status"] != "Confirmed")]
    negotiation.clear()
    negotiation.set_dataframe(noConfirmed,(1,1))
    


# In[5]:


def updateNegoDeliver (request):
    negotiation_df = negotiation.get_as_df()
    deliverables_df = deliverables.get_as_df()
    #get the negotiating rows
    filtereddf = negotiation_df[(negotiation_df["Status"] == "Confirmed")]
    filtered_cols_list = filtereddf.columns.to_list()
    deliverables_cols_list = deliverables_df.columns.to_list()
    
    for index, row in filtereddf.iterrows():
        newrow = makeNewRow (row, deliverables_cols_list, filtered_cols_list)
        rowdf = pd.DataFrame(newrow,index=[0])
        deliverables_df = pd.concat([deliverables_df, rowdf], ignore_index=True)
        
    
    deliverables.clear()
    deliverables.set_dataframe(deliverables_df,(1,1))
    removeConfirmedfromNego (negotiation_df)
    
    return "Successfully updated Deliverables"


# In[ ]:




