import requests
import pandas as pd
from datetime import datetime, date, timedelta
import yfinance as yf
from pathlib import Path
import sys
import time
import json
import os
#selenium scraps
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException

root_directory = Path(__file__).resolve().parent.parent.parent.parent
if str(root_directory) not in sys.path:
    sys.path.append(str(root_directory))
#bring in general scripts
from apps.botops.ops.tgrm import send_to_telegram


def format_json_to_df(json_data):
    if not json_data or 'chart' not in json_data or not json_data['chart']['result']:
        return None

    result = json_data['chart']['result'][0]
    thicker_timestamp_values = result.get('timestamp', [])
    indicators = result.get('indicators', {})
    quote = indicators.get('quote', [{}])[0]

    thicker_close_values = quote.get("close", [])
    thicker_open_values = quote.get("open", [])
    thicker_high_values = quote.get("high", [])
    thicker_low_values = quote.get("low", [])
    thicker_volume_values = quote.get("volume", [])

    dict_values = {'timestamp': thicker_timestamp_values, 
                   'Close': thicker_close_values, 
                   'Open': thicker_open_values,
                   'High': thicker_high_values,
                   'Low': thicker_low_values,
                   'Volume': thicker_volume_values}

    df_price = pd.DataFrame(dict_values)
    df_price["Date"] = pd.to_datetime(df_price["timestamp"], unit='s')

    return df_price


def get_api_data_yf_native(symbol, tgmToken, tgm_id):

    # First try to get data from API
    interval = '1d'
    end_dt = datetime.now()    
    end_timestamp = int(datetime.timestamp(end_dt))
    
    url = f"https://query2.finance.yahoo.com/v8/finance/chart/{symbol}?period1=0&period2={end_timestamp}&interval={interval}&includePrePost=true&events=div%7Csplit%7Cearn&&lang=en-US&region=US&source=cosaic"
    headers = {
        "sec-ch-ua": '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "upgrade-insecure-requests": "1",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
    }
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')

    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 5)
    timeout = 15  # seconds
    start_time = time.time()
    
    
    try:
        driver.get(url)
        wait.until(lambda driver: driver.find_element(By.TAG_NAME, "pre"))
        
        text_content = None
        while True:
            try:
                # Get the pre element and extract its text
                pre_element = driver.find_element(By.TAG_NAME, "pre")
                text_content = pre_element.text
                
                # Try to parse the text as JSON to verify it's valid
                thicker_data = json.loads(text_content)
                
                # Safety check for "chart" key
                if "chart" not in thicker_data or thicker_data["chart"] is None:
                    print(f"Missing 'chart' key in data for {symbol}")
                    return False, None, None

                if thicker_data["chart"]["result"] != None:
                    print("Successfully retrieved data from Browser")
                else:
                    return False, None, None
            
                break  # Break the loop if we got valid JSON
                
            except (StaleElementReferenceException, json.JSONDecodeError) as e:
                print(f"Error: {str(e)}, retrying...")
                time.sleep(0.5)
                
            if time.time() - start_time > timeout:
                send_to_telegram(f"Failed to download {symbol} data due to internal retry timeout", tgmToken, tgm_id)
                print(f"Internal retry timeout for {symbol}")
                return False, None, None

    except TimeoutException:
        print(f"Selenium TimeoutException for {symbol}")
        send_to_telegram(f"Selenium Timeout for {symbol} after 5s wait", tgmToken, tgm_id)
        return False, None, None
    except Exception as e:
        print(f"Unexpected error in get_api_data_yf_native: {str(e)}")
        return False, None, None
    finally:
        # Close the browser ALWAYS
        try:
            driver.quit()
        except:
            pass
    
    # Parse the JSON content
    

    """ try:
        response = requests.get(url, headers=headers)
        print(f"Response status code: {response.status_code}")
        
        if response.status_code == 429:
            print("Rate limited. Waiting 5 seconds before retrying...")
            time.sleep(2)
            response = requests.get(url, headers=headers)
            print(f"Retry response status code: {response.status_code}")
        
        if response.status_code != 200:
            time.sleep(2)
            raise Exception(f"Failed to get data. Status code: {response.status_code}")

        thicker_data = response.json()
        
    except Exception as e:
        send_to_telegram(f"Failed to download {symbol} data {e}",tgmToken, tgm_id)
        print(f"API request failed: {str(e)}")
        print("Attempting to read from local file...")
        
        # Try to read from local JSON file
        local_json_path = os.path.join(root_directory, "dbs/stock_series_yf_fail/", f"{symbol}.json")
        if os.path.exists(local_json_path):
            print(f"Reading data from local file: {local_json_path}")
            with open(local_json_path, 'r') as f:
                thicker_data = json.load(f)
        else:
            raise Exception(f"API request failed and no local file found at {local_json_path}") """

    # Process the data (whether from API or local file)
    df_price = format_json_to_df(thicker_data)

    print(df_price)
    
    return True, df_price, thicker_data


def download_data(asset, tgmToken, tgm_id):

    print(f'----------------------------------------')
    print(f'--------Downloading-{asset}-------------')
    print(f'----------------------------------------')

    try:
        success, df, raw_json = get_api_data_yf_native(asset, tgmToken, tgm_id)

        if success:
            df = df.reset_index(drop=False)
            data = df[["Date","Close","Open","High","Low","Volume"]].copy()
            return data, raw_json
        else:
            print(f"Failed to download data for {asset} from API, trying local JSON file...")
            local_json_path = os.path.join(root_directory, "dbs", "stock_series_yf_fail", f"{asset}.json")
            print(f"Local JSON path: {local_json_path}")
            try:
                with open(local_json_path, 'r') as f:
                    thicker_data = json.load(f)
                print("Data retrieved from JSON in dbs")
                df = format_json_to_df(thicker_data)
                return df, thicker_data
            except:
                print(f"Failed retrieved JSON of {asset} from local dbs")
                return None, None
    except Exception as e:
        print(f"General failure in download_data for {asset}: {str(e)}")
        return None, None


def get_yf_price_series(symbol,start,end):

    data = yf.download(symbol, start, end, auto_adjust=True)
    if data.empty:
        print(f"No se pudieron descargar los datos para {symbol}")
        return None

    # Verificar y ajustar columnas si es un MultiIndex
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.droplevel(1)
        
    data.reset_index(inplace=True)
        
    return data


    

if __name__=="__main__":

    symbol="MSFT"
    end="0"
    tgmToken = "6120637447:AAF05J92UxAfPY985RGqmNlVtgog6Htq2x8"
    tgm_id = "1366278576"
    #symbol_klines(symbol, interval, start, end)
    #get_last_price(symbol)
    #download_data(symbol, tgmToken, tgm_id)
    pass
