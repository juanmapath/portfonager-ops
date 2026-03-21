import requests
from pathlib import Path
import os
import pandas as pd

base_dir = Path(__file__).resolve().parent.parent.parent

def retrieve_telegram_keys(family,family_id,bot_id):

    dir_dbs=os.path.join(base_dir,"dbs",family,f'{family_id}_bots.csv')
    bots_df = pd.read_csv(dir_dbs)
    bots_df=bots_df.set_index("id")
    print(bots_df)

    apiToken = bots_df.loc[bot_id,"tg_key1"]
    chatID = bots_df.loc[bot_id,"tg_key2"]

    return (apiToken,chatID)

def send_to_telegram(message, apiToken, chatID):

    apiURL = f'https://api.telegram.org/bot{apiToken}/sendMessage'
    params = {
        'chat_id': chatID,
        'text': message,
    }

    try:
        response = requests.post(apiURL, json=params)
        if response.status_code == 200:
            print("Message sent successfully!")
        else:
            print("Message sending failed.")
            print(response.text)
    except Exception as e:
        print("no se pudo enviar mensaje a telegram")
        print(e)
