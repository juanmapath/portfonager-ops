import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import re
import numpy as np
import time
import os
import json
from pathlib import Path
root_directory = Path(__file__).resolve().parent.parent.parent
print(root_directory)

def clean_float_list(values):
    cleaned = []
    for val in values:
        if isinstance(val, str):
            val = val.replace('−', '-').strip()  # Replace Unicode minus with ASCII
        try:
            cleaned.append(float(val))
        except Exception as e:
            print(f"Could not convert '{val}': {e}")
            cleaned.append(None)  # or np.nan if you're using pandas/numpy
    return cleaned


def scrap_finviz_screener_costum(params_dict, top=False):
    general_filters ={
    "cap":"cap_microover",
    "Price":"sh_price_o2",
    "AverageVolume":"sh_avgvol_o300",
    }
        
    dict_map_finviz_params = {
        "MarketCap":"cap",
        "Price":"sh_price",
        "AverageVolume":"sh_avgvol",
        "PEG":"fa_peg",
        "SalesGrowthQoQ":"fa_salesqoq",
        "SalesGrowthYoY":"fa_salesyoyttm",
        "ROA":"fa_roa",
        "ROE":"fa_roe",
        "ROIC": "fa_roi",
        "Debt/Equity":"fa_debteq",
        "GrossMargin":"fa_grossmargin",
        "PriceToEarnings":"fa_pe",
        "NetMargin":"fa_netmargin",
        "OperationMargin":"fa_opermargin",
        "QuickRatio":"fa_quickratio",
        "SalesGrowthLast5y":"fa_sales5years",
        "EPSGrowthLast5y":"fa_eps5years",
        "Industry":"ind",
    }

    custom_map ={
        "ticker":1,
        "company_name":2,
        "sector":3,
        "industry":4,
        "country":5,
        "marketCap":6,
        "price_per_earnings":7,
        "PEG":9,
        "price_per_sales":10,
        "price_per_book":11,
        "price_per_cash":12,
        "price_per_fcf":13,
        "sales_growth_5y":21,
        "sales_growth_qoq":23,
        "sales_growth_yoy":133,
        "EV/EBITDA":145,
        "shares_flaot":25,
        "insider_ownership":26,
        "insider_trans":27,
        "roa":32,
        "roe":33,
        "roic":34,
        "quick_ratio":36,
        "debt_to_quity":38,
        "oper_margin":40,
        "profit_margin":41,
        "earnings_date":68,
        "Price": 65,
    }

    url_base = "https://finviz.com/screener.ashx"
    
    # Build columns parameter 'c'
    column_ids = [str(val) for val in custom_map.values()]
    column_keys = list(custom_map.keys())
    c_param = ",".join(column_ids)

    # Build filter parameter 'f'
    filters = []
    for key, value in general_filters.items():
        if value:
            filters.append(value)
    
    for param, value in params_dict.items():
        if param in dict_map_finviz_params:
            key_abr = dict_map_finviz_params[param]
            if value != "any" and key_abr != "any":
                filters.append(f"{key_abr}_{value}")
    
    f_param = ",".join(filters)
    full_url = f"{url_base}?v=150&f={f_param}&ft=2&c={c_param}"
    print(f"Scrapping URL: {full_url}")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    }

    try:
        response = requests.get(full_url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")
        
        total_div = soup.find('div', id="screener-total")
        if not total_div:
            print("No results found or could not find screener-total div.")
            return pd.DataFrame()

        text = total_div.get_text(strip=True)
        match = re.search(r'/ (\d+)', text)
        if not match:
            print(f"Could not parse total count from text: {text}")
            return pd.DataFrame()
            
        total = int(match.group(1))
        no_pages = (total // 20) + (1 if total % 20 > 0 else 0)
        
        if top:
            no_pages = 1

        print(f"Total results: {total}, total pages: {no_pages}")

        all_data = []

        for pag in range(1, no_pages + 1):
            if pag > 1:
                time.sleep(1)
                pag_param = f"r={(pag-1)*2}1"
                current_url = f"{full_url}&{pag_param}"
                print(f"Scrapping page {pag} of {no_pages}: {current_url}")
                response = requests.get(current_url, headers=headers)
                response.raise_for_status()
                soup = BeautifulSoup(response.content, "html.parser")
            else:
                print(f"Scrapping page 1 of {no_pages}")

            rows = soup.find_all('tr', class_='styled-row')
            for row in rows:
                cols = row.find_all('td')
                
                row_data = {}
                offset = 1 if len(cols) > len(column_ids) else 0
                
                for i, key in enumerate(column_keys):
                    if i + offset < len(cols):
                        val = cols[i+offset].get_text(strip=True)
                        if val == "-":
                            val = None
                        elif "%" in val:
                            val = val.replace("%", "").replace(",", "")
                        row_data[key] = val
                
                all_data.append(row_data)

        df = pd.DataFrame(all_data)
        df["date"] = datetime.now().strftime("%Y-%m-%d")
        return df

    except Exception as e:
        print(f"Error in scrap_finviz_screener_costum: {e}")
        return pd.DataFrame()


def scrap_finviz_screener(params_dict, top=False):

   
    general_filters ={
    "cap":"cap_microover",
    "Price":"sh_price_o2",
    "AverageVolume":"sh_avgvol_o300",
}
        
    dict_map_finviz_params = {
        "MarketCap":"cap",
        "Price":"sh_price",
        "AverageVolume":"sh_avgvol",
        "PEG":"fa_peg",
        "SalesGrowthQoQ":"fa_salesqoq",
        "SalesGrowthYoY":"fa_salesyoyttm",
        "ROA":"fa_roa",
        "ROE":"fa_roe",
        "ROIC": "fa_roi",
        "Debt/Equity":"fa_debteq",
        "GrossMargin":"fa_grossmargin",
        "PriceToEarnings":"fa_pe",
        "NetMargin":"fa_netmargin",
        "OperationMargin":"fa_opermargin",
        "QuickRatio":"fa_quickratio",
        "SalesGrowthLast5y":"fa_sales5years",
        "EPSGrowthLast5y":"fa_eps5years",
        "Industry":"ind",
        
    }

    custom_map ={
        "Ticker":1,
        "Company":2,
        "sector":3,
        "industry":4,
        "country":5,
        "marketCap":6,
        "price_per_earnings":7,
        "PEG":9,
        "price_per_book":11,
        "price_per_cash":12,
        "price_per_fcf":13,
        "sales_growth_5y":21,
        "sales_growth_qoq":23,
        "sales_growth_yoy":133,
        "shares_flaot":25,
        "insider_ownership":26,
        "insider_trans":27,
        "roa":32,
        "roe":33,
        "roic":34,
        "quick_ratio":36,
        "debt_to_quity":38,
        "oper_margin":40,
        "profit_margin":41,
    }

    url_base = "https://finviz.com/screener.ashx"
    filter="&f="

    for param in general_filters:
        key = param
        value = general_filters[param]
        filter+=f"{value}%2C"
        
    for param in params_dict:
        key = param
        value = params_dict[param]
        key_abr = dict_map_finviz_params[key]
        if (param == "any") | (key_abr == "any"):
            pass
        else:
            filter+=f"{key_abr}_{value}%2C"

    filter += "o=-marketcap"

    #order &o=-marketcap, o=-netmargin
    #v111 -> overview

    first_call_url = f"{url_base}?v=111{filter}"
    print("url to Scrap:", first_call_url)

    headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
    }

    print(first_call_url)

    #page r= #pag1 -> nada, pag2,3,4,5,6 -> 21,41,61,81,101 (pag-1)*2
    #<div id="screener-total" class="count-text whitespace-nowrap">#1 / 120 Total</div>
    #20 per pag
    
    try:
        # first round call
        response = requests.get(first_call_url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")
        rows = soup.find_all('tr', class_='styled-row')
        total_div = soup.find('div', id="screener-total")

        if total_div:
            text = total_div.get_text(strip=True)  # "#1 / 120 Total"
            total = text.split('/')[-1].split()[0]  # ' 120 Total' -> ['120', 'Total']

            if (float(total)//20 - float(total)/20) == 0:
                no_pages = int(float(total)/20)
            else:
                no_pages = int(float(total)//20 +1)

            if top != False:
                no_pages = 1

        print("no_pages",no_pages)
        for pag in range(1,no_pages+1):

            time.sleep(1)

            print(f"Scrapping page {pag} of {no_pages}")

            valuation_url = first_call_url.replace("v=111","v=121")
            ownership_url = first_call_url.replace("v=111","v=131")
            finantial_url = first_call_url.replace("v=111","v=161")
            tecnical_url = first_call_url.replace("v=111","v=171")

            if pag == 1:
                pag_param = ""
                
            else:
                pag_param = f"r={(pag-1)*2}1"
                # first round call
                response = requests.get(f"{first_call_url}&{pag_param}", headers=headers)
                response.raise_for_status()
                soup = BeautifulSoup(response.content, "html.parser")
                rows = soup.find_all('tr', class_='styled-row')
                total_div = soup.find('div', id="screener-total")
                valuation_url = f"{valuation_url}&{pag_param}"
                finantial_url = f"{finantial_url}&{pag_param}"
                tecnical_url = f"{tecnical_url}&{pag_param}"
                ownership_url = f"{ownership_url}&{pag_param}"

            # Extract text from <a> elements in the second column
            tickers=[]
            company_name=[]
            sector=[]
            industry=[]
            country=[]
            marketCap=[]
        

            for row in rows:
                
                ticker_col = row.find_all('td')[1]  # Access the second <td> element
                company_name_col = row.find_all('td')[2]
                sector_col = row.find_all('td')[3]
                industry_col = row.find_all('td')[4]
                country_col = row.find_all('td')[5]
                market_col = row.find_all('td')[6]
          

                link = ticker_col.find('a') 
                cn =  company_name_col.find('a')  
                sc =  sector_col.find('a') 
                ic =  industry_col.find('a') 
                cc =  country_col.find('a')
                mc = market_col.find('a')

                if link:
                    tickers.append(link.get_text())
                    company_name.append(cn.get_text())
                    sector.append(sc.get_text())
                    industry.append(ic.get_text())
                    country.append(cc.get_text())
                    marketCap.append(mc.get_text())
                
            df = pd.DataFrame(
                {
                    "ticker":tickers,
                    "company_name":company_name,
                    "sector":sector,
                    "industry":industry,
                    "country":country,
                    "marketCap":marketCap,
            })


             #v131 -> ownership
            print("ownership")
            response11 = requests.get(ownership_url, headers=headers)
            response11.raise_for_status()
            soup11 = BeautifulSoup(response11.content, "html.parser")
            rows11 = soup11.find_all('tr', class_='styled-row')

            df["insider_ownership"] = "0.0"
            df["insider_trans"] = "0.0"
   

            i_row = 0
            
            for row in rows11:
                insider_ownership_col = row.find_all('td')[5]
                insider_trans_col = row.find_all('td')[6]
                io =  insider_ownership_col.find('a')  
                it =  insider_trans_col.find('a')  
                #add val to df
                df.loc[i_row,"insider_ownership"] = io.get_text().replace("%","")
                df.loc[i_row,"insider_trans"] = it.get_text().replace("%","")
   

                i_row+=1     

 
            #v161 -> valuation
            print("valuation")
            response1 = requests.get(valuation_url, headers=headers)
            response1.raise_for_status()
            soup1 = BeautifulSoup(response1.content, "html.parser")
            rows1 = soup1.find_all('tr', class_='styled-row')

            df["price_per_earnings"] = "0.0"
            df["price_per_book"] = "0.0"
            df["price_per_cash"] ="0.0"
            df["price_per_fcf"] = "0.0"
   

            i_row = 0
            for row in rows1:
                price_per_earnings_col = row.find_all('td')[3]
                price_per_book_col = row.find_all('td')[7]
                price_per_cash_col = row.find_all('td')[8]
                price_per_fcf_col = row.find_all('td')[9]

                ppe =  price_per_earnings_col.find('a')  
                ppb =  price_per_book_col.find('a') 
                ppc =  price_per_cash_col.find('a') 
                ppfcf =  price_per_fcf_col.find('a')  
                #add val to df

                df.loc[i_row,"price_per_earnings"] = ppe.get_text()
                df.loc[i_row,"price_per_book"] = ppb.get_text()
                df.loc[i_row,"price_per_cash"] = ppc.get_text()
                df.loc[i_row,"price_per_fcf"] = ppfcf.get_text()
   

                i_row+=1     

            #v161 -> financial
            print("finantial")
            response2 = requests.get(finantial_url, headers=headers)
            response2.raise_for_status()
            soup2 = BeautifulSoup(response2.content, "html.parser")
            rows2 = soup2.find_all('tr', class_='styled-row')


            df["roa"] = "0.0"
            df["roe"] = "0.0"
            df["quick_ratio"] ="0.0"
            df["debt_to_quity"] = "0.0"
            df["oper_margin"] = "0.0"
            df["profit_margin"] = "0.0"
            df["price"] = "0.0"

            i_row = 0
            for row in rows2:
                roa_col = row.find_all('td')[4]  # Access the second <td> element
                roe_col =  row.find_all('td')[5]  
                quick_ratio_col = row.find_all('td')[8]
                debt_to_quity_col = row.find_all('td')[10]
                oper_margin_col = row.find_all('td')[12]
                profit_margin_col = row.find_all('td')[13]
                price_col = row.find_all('td')[15]

                roa_el = roa_col.find('a') 
                roe_el =  roe_col.find('a')   
                qr_el = quick_ratio_col.find('a')
                dtq_el = debt_to_quity_col.find('a')
                om_el =  oper_margin_col.find('a')   
                pm_el = profit_margin_col.find('a')
                p_el =  price_col.find('a')   
                #add val to df
           
                df.loc[i_row,"roa"] = roa_el.get_text().replace("%","")
                df.loc[i_row,"roe"] = roe_el.get_text().replace("%","")
                df.loc[i_row,"quick_ratio"] = qr_el.get_text()
                df.loc[i_row,"debt_to_quity"] = dtq_el.get_text()
                df.loc[i_row,"oper_margin"] = om_el.get_text().replace("%","")
                df.loc[i_row,"profit_margin"] = pm_el.get_text().replace("%","")
                df.loc[i_row,"price"] = p_el.get_text()
              
                i_row+=1     

            #v171 -> tecnical
            print("tecnical")
            response3 = requests.get(tecnical_url, headers=headers)
            response3.raise_for_status()
            soup3 = BeautifulSoup(response3.content, "html.parser")
            rows3 = soup3.find_all('tr', class_='styled-row')

            df["sma50"] = "0.0"
            df["sma200"] = "0.0"
            df["rsi"] ="0.0"

            i_row = 0
            for row in rows3:
                sma50_col = row.find_all('td')[5]  # Access the second <td> element
                sma200_col =  row.find_all('td')[6]  
                rsi_col = row.find_all('td')[9]
        
                s50_el = sma50_col.find('a') 
                s200_el =  sma200_col.find('a')   
                rsi_el = rsi_col.find('a')

                #add val to df
                df.loc[i_row,"sma50"] = s50_el.get_text().replace("%","")
                df.loc[i_row,"sma200"] = s200_el.get_text().replace("%","")
                df.loc[i_row,"rsi"] = rsi_el.get_text()
        

                i_row+=1               
            
            if pag == 1:
                main_df = df.copy()
            else:
                main_df = pd.concat([main_df,df],  ignore_index=True)
        
        print(main_df)
        #add current date to the df
        main_df["date"] = datetime.now().strftime("%Y-%m-%d")

        return main_df
        

    except Exception as e:
        print(e)
        return False



def scrap_finviz_eps_series(ticker):
    
    endpoint = f'https://finviz.com/api/statement.ashx?t={ticker}'

    headers = { 
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
        "Content-Type":"text",
        "Accept":"application/json; charset=utf-8",
    }

    try:

        response = requests.get(endpoint, headers=headers)
        data = response.json()
        # Save the JSON data to local file
        local_json_path = os.path.join(root_directory, "dbs","statements", f"{ticker}_statement.json")
        os.makedirs(os.path.dirname(local_json_path), exist_ok=True)  # Create directory if it doesn't exist
        with open(local_json_path, 'w') as f:
            json.dump(data, f, indent=4)
        print(f"Saved data to local file: {local_json_path}")
        print("Successfully retrieved data from Browser")
        return True, data
    except Exception as e:
        print("Error retrieving data from Browser")
        print(e)
        return False, None


def update_finviz_metrics_series(ticker):
    from apps.botops.models import AssetSeries
    
    endpoint = f'https://finviz.com/api/statement.ashx?t={ticker}'

    headers = { 
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
        "Content-Type": "text",
        "Accept": "application/json; charset=utf-8",
    }

    try:
        response = requests.get(endpoint, headers=headers)
        response.raise_for_status()
        new_data_full = response.json()
        
        # Verify JSON
        if "data" not in new_data_full or "Period" not in new_data_full["data"]:
            print(f"[{ticker}] Finviz endpoint returned unexpected JSON structure.")
            return False, None
            
        new_data = new_data_full["data"]
        new_periods = new_data.get("Period", [])
        
        # Get or create AssetSeries
        asset_series, created = AssetSeries.objects.get_or_create(ticker=ticker)
        
        old_data = asset_series.fin_metrics_series
        
        # Merging logic
        if not old_data:
            merged_data = dict(new_data)
        else:
            old_periods = old_data.get("Period", [])
            merged_data = {k: list(v) for k, v in new_data.items()}
            
            # Ensure all keys from old_data exist in merged_data
            for k in old_data.keys():
                if k not in merged_data:
                    merged_data[k] = [""] * len(new_periods)

            # Append old data that is not present in new data
            for i, period in enumerate(old_periods):
                if period not in new_periods:
                    for k in merged_data.keys():
                        if k == "Period":
                            merged_data[k].append(period)
                        elif k in old_data and i < len(old_data[k]):
                            merged_data[k].append(old_data[k][i])
                        else:
                            merged_data[k].append("")
                            
        # Save back to database
        asset_series.fin_metrics_series = merged_data
        asset_series.save()
        
        print(f"[{ticker}] Successfully updated fin_metrics_series")
        return True, merged_data

    except Exception as e:
        print(f"[{ticker}] Error retrieving or merging data from Finviz")
        print(e)
        return False, None


if __name__ == "__main__":

    #finantial filters f=
    #marketcap cap_midover, cao_smallunder
    #ROA fa_roa_o5
    #ROE fa_roe_o10
    #NetMargin fa_netmargin_o10
    #Operation Margin  fa_opermargin_pos, fa_opermargin_o10
    #Quickratio fa_quickratio_o 1

    scrap_finviz_eps_series("AAPL")
    #scrap_finviz_screener(["any","any","any","any","any","o1","any","any","o30","any","o10","o0.5","o30","pos"])
    
    #scrap_TradingView_metrics("AMZN","NASDAQ")