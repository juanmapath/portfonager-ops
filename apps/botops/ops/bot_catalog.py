import sys
from pathlib import Path
import pandas as pd
import json
from datetime import timedelta
from django.utils import timezone
import math
import ast  
import numpy as np 
import io
import requests


root_directory = Path(__file__).resolve().parent.parent.parent.parent
if str(root_directory) not in sys.path:
    sys.path.append(str(root_directory))

from apps.botops.ops.strategies_catalog import strategy_functions
from apps.botops.ops.candles_down import download_data, format_json_to_df
from apps.botops.ops.indicators import *

from apps.botops.ops.tgrm import send_to_telegram
from apps.botops.models import AssetSeries
#tools

def check_last_ohlc_and_download_data(asset, apiToken, chatID):
    today = pd.Timestamp.today()
    offset_days = 4000
    start_date = (today - pd.Timedelta(days=offset_days))

    # Check last ohlc
    asset_series, created = AssetSeries.objects.get_or_create(ticker=asset)
    now = timezone.now()

    if not created and asset_series.ochl_last_update:
        if now - asset_series.ochl_last_update < timedelta(minutes=10):
            print(f"[{asset}] Using cached OHLC data ({(now - asset_series.ochl_last_update).seconds // 60} mins old).")
            if asset_series.ochl:
                try:
                    df = format_json_to_df(asset_series.ochl)
                    if df is not None:
                        df["Date"] = pd.to_datetime(df["Date"])
                        df = df[df["Date"] >= start_date]
                        df = df.reset_index(drop=True)
                        return df
                except Exception as e:
                    print(f"[{asset}] Error parsing cached OHLC: {e}. Redownloading.")

    print(f"[{asset}] Downloading fresh OHLC data...")
    downloaded_df, raw_json = download_data(asset, apiToken, chatID)
    
    if downloaded_df is None or downloaded_df.empty:
        send_to_telegram(f"Failed to download {asset} data. Try to use last cached data", apiToken, chatID)
        if asset_series.ochl:
            try:
                df = format_json_to_df(asset_series.ochl)
                if df is not None:
                    df["Date"] = pd.to_datetime(df["Date"])
                    df = df[df["Date"] >= start_date]
                    df = df.reset_index(drop=True)
                    return df
            except Exception as e:
                print(f"[{asset}] Error parsing cached OHLC on fallback: {e}")
        return None
    
    # Save raw JSON to DB before filtering by start_date to keep history
    try:
        asset_series.ochl = raw_json
        asset_series.ochl_last_update = now
        asset_series.save()
        print(f"[{asset}] Successfully saved raw JSON OHLC data to DB.")
    except Exception as e:
        print(f"[{asset}] Error saving to DB: {e}. Data downloaded but not cached.")

    downloaded_df["Date"] = pd.to_datetime(downloaded_df["Date"])
    downloaded_df = downloaded_df[downloaded_df["Date"] >= start_date]
    downloaded_df = downloaded_df.reset_index(drop=True)

    return downloaded_df


def round_up(n, decimals=0):
    multiplier = 10 ** decimals
    return math.ceil(n * multiplier) / multiplier


def round_down(n, decimals=0):
    multiplier = 10 ** decimals
    return math.floor(n * multiplier) / multiplier


def parse_string_list(s):
    if not s or s == '[]': return []
    # Remove brackets and split by comma
    s = s.strip('[]')
    return [x.strip() for x in s.split(',')]



#strategies
def run_multi_strategy(BotAsset, operate=False):
    bot_asset_id = BotAsset.id
    asset = BotAsset.asset
    apiToken = BotAsset.bot.tg_key1
    chatID = BotAsset.bot.tg_key2
    
    individual_sts_names = parse_string_list(BotAsset.params1)
    # params2 contains nested lists of numbers, eval works fine, or ast.literal_eval is safer
    try:
        params_of_individual_sts = ast.literal_eval(BotAsset.params2)
    except Exception:
        params_of_individual_sts = eval(BotAsset.params2)
        
    prev_active_sts = parse_string_list(BotAsset.params3)
    broker = BotAsset.broker
    prev_pos_gp = BotAsset.position
    prev_qty_open = BotAsset.qty_open
    prev_cap_to_trade = BotAsset.cap_to_trade
    prev_cap_to_add = BotAsset.cap_to_add
    prev_cap_value_in_trade = BotAsset.cap_value_in_trade
    prev_op_price = BotAsset.op_price
    prev_last_price = BotAsset.last_price
    prev_pnl = BotAsset.PNL
    prev_pnl_un = BotAsset.pnl_un
    prev_trades = BotAsset.trades
    prev_coms = BotAsset.coms
    
    
    coms_per_trade = BotAsset.broker.coms
    today = pd.Timestamp.today()
  
    #descargar velas
    downloaded_df = check_last_ohlc_and_download_data(asset,apiToken,chatID)

    if downloaded_df is None or downloaded_df.empty :
        send_to_telegram(f"Failed to download {asset} data",apiToken, chatID)
        return
    

    ##################analizar estrategias individuales##################

    sts_sum_pos = 0
    new_active_st_names = []
    i=0
    for st in individual_sts_names:
        data = downloaded_df
        params = params_of_individual_sts[i]
        nombre = st
        tipo_nombre = f'qtn_{nombre}'

        print(f'----------------------------------------------------------')
        print("")
        print("STATUS STRATEGY")
        print(f'ST{st}::{asset}::{tipo_nombre}')

        new_pos, new_close, _ , data_st = strategy_functions[nombre](data, params)  
        sts_sum_pos += new_pos
        if new_pos !=0:
            new_active_st_names.append(st)
        i+=1

    ###################analizar estrategias agrupadas##################

    if sts_sum_pos > 0:
        new_pos_gp = 1
    elif sts_sum_pos < 0:
        new_pos_gp = -1
    else:
        new_pos_gp = 0

    ###################operar estrategia agrupada##################

    current_position_value = prev_qty_open * new_close
    position_cost = prev_qty_open * prev_op_price

    if prev_pos_gp == 1:
        pnl_group = current_position_value - position_cost - coms_per_trade
    elif prev_pos_gp == -1:
        pnl_group = position_cost - current_position_value - coms_per_trade
    else:
        pnl_group = 0

    new_cap_value_in_trade = current_position_value

    message_order = ""
    message_order += f'{bot_asset_id}-{asset} -- TotPNL: ${prev_pnl}\n' 
    message_order += f'-> {broker} \n'

    change_side = False

    if (prev_pos_gp == new_pos_gp):
        if prev_pos_gp == 0:
            message_order += f'No position -> KEEP\n'
        else:
          
            sts_qty_prev_len =  len(prev_active_sts)
            sts_qty_new_len =  len(new_active_st_names)

            message_order += f'Pos Value: {round(new_cap_value_in_trade,1)}USD\n'
            message_order += f'Pos pnl: {round(pnl_group,1)}USD\n'
 
            #adding to the pos
            if (sts_qty_new_len > sts_qty_prev_len) & (prev_cap_to_add>0):
                
                new_cap_to_trade = prev_cap_to_trade + prev_cap_to_add - coms_per_trade
                new_cap_to_add = 0
                
                leverage = BotAsset.leverage
                leveraged_cap_to_add = prev_cap_to_add * leverage
                qty_to_add = round_up(leveraged_cap_to_add/new_close,4)
                
                new_qty_open = prev_qty_open + qty_to_add
                new_op_price = ((prev_qty_open*prev_op_price) + (qty_to_add*new_close))/(prev_qty_open+qty_to_add)
                new_coms = prev_coms + coms_per_trade
                new_cap_value_in_trade = new_qty_open * new_close
                new_cap_lever = (new_qty_open * new_op_price) - new_cap_to_trade if BotAsset.leverage > 1.0 else 0.0
                
                if operate == True:
                    BotAsset.params3 = new_active_st_names
                    BotAsset.qty_open = new_qty_open
                    BotAsset.cap_to_trade = new_cap_to_trade #ya tiene coms de entrada
                    BotAsset.cap_to_add = new_cap_to_add
                    BotAsset.cap_value_in_trade = new_cap_value_in_trade #ya tiene coms de entrada
                    BotAsset.cap_lever = new_cap_lever
                    BotAsset.op_price = new_op_price
                    BotAsset.coms = new_coms
                    BotAsset.last_price = new_close
                    BotAsset.updated_date = today
                    BotAsset.save()

                message_order += f'ADDING MONEY TO POS:::\n'
                message_order += f'--> CURRENT {prev_qty_open}qty BUY\n'
                message_order += f'--> New Cap {round(new_cap_value_in_trade,1)}USD\n'
                message_order += f'--> Buy +{qty_to_add}qty BUY\n'
                new_cap_lever = (prev_qty_open * prev_op_price) - prev_cap_to_trade if BotAsset.leverage > 1.0 else 0.0
                if operate == True:
                    BotAsset.cap_value_in_trade = new_cap_value_in_trade
                    BotAsset.cap_lever = new_cap_lever
                    BotAsset.pnl_un = pnl_group
                    BotAsset.last_price = new_close
                    BotAsset.updated_date = today
                    BotAsset.save()
                message_order += f'--> KEEP {prev_qty_open}qty KEEP\n'
     

    #si cierra largo o corto
    if ((prev_pos_gp != 0) & (new_pos_gp != prev_pos_gp)):

        new_pnl = pnl_group 
        new_pnl_un = 0
        new_op_price = new_close
        new_trades = prev_trades + 0.5
        new_coms = prev_coms + coms_per_trade
        new_position = 0
        new_qty_open = 0
        new_cap_to_trade = prev_cap_to_trade + pnl_group
        new_cap_value_in_trade = 0
     
        if operate == True:
            BotAsset.params3 = new_active_st_names
            BotAsset.position = 0
            BotAsset.qty_open = 0
            BotAsset.cap_to_trade = new_cap_to_trade
            BotAsset.cap_value_in_trade = 0
            BotAsset.cap_lever = 0.0
            BotAsset.op_price = new_op_price
            BotAsset.last_price = new_close
            BotAsset.pnl_un = 0
            BotAsset.PNL = prev_pnl + new_pnl
            BotAsset.trades = new_trades
            BotAsset.coms = new_coms
            BotAsset.updated_date = today
            BotAsset.save() 
        
        message_order += f'Pos pnl: {round(prev_pnl_un,1)}USD\n'
        message_order += f'CLOSE POSITION\n'
        message_order += f'--> Sell {round(prev_cap_value_in_trade,1)}USD\n'
        message_order += f'--> Sell -{prev_qty_open}qty SELL ALL\n'

        if new_pos_gp != 0:
            change_side = True

    #si abre largo o corto desde 0
    if (change_side == True) | ((prev_pos_gp == 0) & (new_pos_gp != 0)):

        if change_side == True:
            new_cap_to_trade = new_cap_to_trade + prev_cap_to_add - coms_per_trade #quita coms
            new_trades = new_trades + 0.5
            new_coms = new_coms + coms_per_trade
        else:
            new_cap_to_trade = prev_cap_to_trade + prev_cap_to_add - coms_per_trade #quita coms
            new_trades = prev_trades + 0.5
            new_coms = prev_coms + coms_per_trade

        leverage = BotAsset.leverage
        new_cap_to_add = 0
        
        leveraged_cap = new_cap_to_trade * leverage
        new_qty_open = round_down(leveraged_cap/new_close,4)
        new_cap_value_in_trade = new_qty_open * new_close
        new_op_price = new_close
        new_cap_lever = (new_qty_open * new_op_price) - new_cap_to_trade if leverage > 1.0 else 0.0

        if operate == True:
            BotAsset.params3 = new_active_st_names
            BotAsset.position = new_pos_gp
            BotAsset.qty_open = new_qty_open
            BotAsset.cap_to_trade = new_cap_to_trade #ya quito coms
            BotAsset.cap_to_add = new_cap_to_add
            BotAsset.cap_value_in_trade = new_cap_value_in_trade
            BotAsset.cap_lever = new_cap_lever
            BotAsset.op_price = new_op_price
            BotAsset.last_price = new_close
            BotAsset.pnl_un = 0
            BotAsset.trades = new_trades
            BotAsset.coms = new_coms
            BotAsset.updated_date = today
            BotAsset.save() 
        
        #just open long
        if new_pos_gp == 1:
            message_order += f'--> Buy {round(new_cap_to_trade,1)}USD\n'
            message_order += f'--> Buy +{new_qty_open}qty BUY\n'
            
        if new_pos_gp == -1:
            message_order += f'--> Sell short {round(new_cap_to_trade,1)}USD\n'
            message_order += f'--> Sell short +{new_qty_open}qty SELL short\n'
         

    message_order += f'________________\n'
    return message_order


def run_one_strategy(BotAsset, operate=False):

    bot_asset_id = BotAsset.id
    asset = BotAsset.asset
    apiToken = BotAsset.bot.tg_key1
    chatID = BotAsset.bot.tg_key2

    individual_sts_names = parse_string_list(BotAsset.params1)[0]
    # params2 contains nested lists of numbers, eval works fine, or ast.literal_eval is safer
    try:
        params_of_individual_sts = ast.literal_eval(BotAsset.params2)[0]
    except Exception:
        params_of_individual_sts = eval(BotAsset.params2)[0]

    broker = BotAsset.broker
    prev_pos = BotAsset.position
    prev_qty_open = BotAsset.qty_open
    prev_cap_to_trade = BotAsset.cap_to_trade
    prev_cap_to_add = BotAsset.cap_to_add
    prev_cap_value_in_trade = BotAsset.cap_value_in_trade
    prev_op_price = BotAsset.op_price
    prev_last_price = BotAsset.last_price
    prev_pnl = BotAsset.PNL
    prev_pnl_un = BotAsset.pnl_un
    prev_trades = BotAsset.trades
    prev_coms = BotAsset.coms

    coms_per_trade = BotAsset.broker.coms
    today = pd.Timestamp.today()
   
    #descargar velas
    downloaded_df = check_last_ohlc_and_download_data(asset,apiToken,chatID)

    if downloaded_df is None or downloaded_df.empty :
        send_to_telegram(f"Failed to download {asset} data",apiToken, chatID)
        return
    
    cur_status_dict={}

    data = downloaded_df
    params = params_of_individual_sts
    nombre = individual_sts_names

    print(f'----------------------------------------------------------')
    print("")
    print("STATUS STRATEGY")
    print(f'{nombre}::{asset}')

    new_pos, new_close, _ , data_st = strategy_functions[nombre](data, params)  
    
    current_position_value = prev_qty_open * new_close
    position_cost = prev_qty_open * prev_op_price

    if prev_pos == 1:
        pnl_group = current_position_value - position_cost - coms_per_trade
    elif prev_pos == -1:
        pnl_group = position_cost - current_position_value - coms_per_trade
    else:
        pnl_group = 0

    new_cap_value_in_trade = current_position_value
    
    message_order = ""
    message_order += f'{bot_asset_id}-{asset} -- TotPNL: ${prev_pnl}\n' 
    message_order += f'-> {broker} \n'

    change_side = False

    if (prev_pos == new_pos):
        if prev_pos == 0:
            message_order += f'No position -> KEEP\n'
        else:
            message_order += f'Pos Value: {round(new_cap_value_in_trade,1)}USD\n'
            message_order += f'Pos pnl: {round(pnl_group,1)}USD\n'
            message_order += f'--> KEEP {prev_qty_open}qty KEEP\n'
            new_cap_lever = (prev_qty_open * prev_op_price) - prev_cap_to_trade if BotAsset.leverage > 1.0 else 0.0
            if operate == True:
                BotAsset.cap_value_in_trade = new_cap_value_in_trade
                BotAsset.cap_lever = new_cap_lever
                BotAsset.pnl_un = pnl_group
                BotAsset.last_price = new_close
                BotAsset.updated_date = today
                BotAsset.save()
     

    #si cierra largo o corto
    if ((prev_pos != 0) & (new_pos != prev_pos)):

        new_pnl = pnl_group 
        new_pnl_un = 0
        new_op_price = new_close
        new_trades = prev_trades + 0.5
        new_coms = prev_coms + coms_per_trade
        new_position = 0
        new_qty_open = 0
        new_cap_to_trade = prev_cap_to_trade + pnl_group
        new_cap_value_in_trade = 0
     
        if operate == True:
            BotAsset.position = 0
            BotAsset.qty_open = 0
            BotAsset.cap_to_trade = new_cap_to_trade
            BotAsset.cap_value_in_trade = 0
            BotAsset.cap_lever = 0.0
            BotAsset.op_price = new_op_price
            BotAsset.last_price = new_close
            BotAsset.pnl_un = 0
            BotAsset.PNL = prev_pnl + new_pnl
            BotAsset.trades = new_trades
            BotAsset.coms = new_coms
            BotAsset.updated_date = today
            BotAsset.save() 
        
        message_order += f'Pos pnl: {round(prev_pnl_un,1)}USD\n'
        message_order += f'CLOSE POSITION\n'
        message_order += f'--> Sell {round(prev_cap_value_in_trade,1)}USD\n'
        message_order += f'--> Sell -{prev_qty_open}qty SELL ALL\n'

        if new_pos != 0:
            change_side = True

    #si abre largo o corto desde 0
    if (change_side == True) | ((prev_pos == 0) & (new_pos != 0)):

        if change_side == True:
            new_cap_to_trade = new_cap_to_trade + prev_cap_to_add - coms_per_trade
            new_trades = new_trades + 0.5
            new_coms = new_coms + coms_per_trade
        else:
            new_cap_to_trade = prev_cap_to_trade + prev_cap_to_add - coms_per_trade
            new_trades = prev_trades + 0.5
            new_coms = prev_coms + coms_per_trade

        leverage = BotAsset.leverage
        new_cap_to_add = 0
        leveraged_cap = new_cap_to_trade * leverage 
        new_qty_open = round_down(leveraged_cap/new_close,4)
        new_cap_value_in_trade = new_qty_open * new_close
        new_op_price = new_close
        new_cap_lever = (new_qty_open * new_op_price) - new_cap_to_trade if leverage > 1.0 else 0.0

        if operate == True:
            BotAsset.position = new_pos
            BotAsset.qty_open = new_qty_open
            BotAsset.cap_to_trade = new_cap_to_trade
            BotAsset.cap_to_add = new_cap_to_add
            BotAsset.cap_value_in_trade = new_cap_value_in_trade
            BotAsset.cap_lever = new_cap_lever
            BotAsset.op_price = new_op_price
            BotAsset.last_price = new_close
            BotAsset.pnl_un = 0
            BotAsset.trades = new_trades
            BotAsset.coms = new_coms
            BotAsset.updated_date = today
            BotAsset.save() 
        
        #just open long
        if new_pos == 1:
            message_order += f'--> Buy {round(new_cap_to_trade,1)}USD\n'
            message_order += f'--> Buy +{new_qty_open}qty BUY\n'
            
        if new_pos == -1:
            message_order += f'--> Sell short {round(new_cap_to_trade,1)}USD\n'
            message_order += f'--> Sell short +{new_qty_open}qty SELL short\n'
         

    message_order += f'________________\n'
    return message_order


def follow_price_update_pos(BotAsset, operate=False):

    bot_asset_id = BotAsset.id
    asset = BotAsset.asset
    apiToken = BotAsset.bot.tg_key1
    chatID = BotAsset.bot.tg_key2

    individual_sts_names = parse_string_list(BotAsset.params1)[0]
    # params2 contains nested lists of numbers, eval works fine, or ast.literal_eval is safer
    try:
        params_of_individual_sts = ast.literal_eval(BotAsset.params2)[0]
    except Exception:
        params_of_individual_sts = eval(BotAsset.params2)[0]

    broker = BotAsset.broker
    prev_pos = BotAsset.position
    prev_qty_open = BotAsset.qty_open
    prev_cap_to_trade = BotAsset.cap_to_trade
    prev_cap_value_in_trade = BotAsset.cap_value_in_trade
    prev_op_price = BotAsset.op_price
    prev_last_price = BotAsset.last_price
    prev_pnl_un = BotAsset.pnl_un

    today = pd.Timestamp.today()
    offset_days = 50
    start_date = (today - pd.Timedelta(days=offset_days))
    
    #descargar velas
    downloaded_df = check_last_ohlc_and_download_data(asset,apiToken,chatID)

    if downloaded_df is None or downloaded_df.empty :
        send_to_telegram(f"Failed to download {asset} data",apiToken, chatID)
        return
    
    data = downloaded_df

    print(f'----------------------------------------------------------')
    print("FOLLOW PRICE")
    print("")

    new_pos = 1
    new_close = downloaded_df['Close'].iloc[-1]
    new_cap_value_in_trade = prev_qty_open*new_close
    pnl_group = new_cap_value_in_trade - prev_cap_to_trade
    
    message_order = ""
    message_order += f'{bot_asset_id}-{asset} -- TotUnrPNL: ${pnl_group}\n' 
    message_order += f'-> {broker} \n'
    message_order += f'Pos Value: {round(new_cap_value_in_trade,1)}USD\n'
    message_order += f'Pos pnl: {round(pnl_group,1)}USD\n'
    message_order += f'________________\n'

    if operate == True:
        BotAsset.cap_value_in_trade = new_cap_value_in_trade
        BotAsset.last_price = new_close
        BotAsset.pnl_un = pnl_group
        BotAsset.updated_date = today
        BotAsset.save() 
           
    return message_order


def one_strategy_cross_assets(BotAsset, operate=False):

    bot_asset_id = BotAsset.id
    asset_to_operate = BotAsset.asset
    apiToken = BotAsset.bot.tg_key1
    chatID = BotAsset.bot.tg_key2

    # El asset de las señales estará en params3[0]
    try:
        asset_signals = parse_string_list(BotAsset.params3)[0]
    except (IndexError, TypeError):
        send_to_telegram(f"Error: No signal asset found in params3 for {asset_to_operate}", apiToken, chatID)
        return

    # params1[0] is strategy name
    try:
        individual_sts_names = parse_string_list(BotAsset.params1)[0]
    except (IndexError, TypeError):
        send_to_telegram(f"Error: No strategy name found in params1 for {asset_to_operate}", apiToken, chatID)
        return

    # params2[0] is strategy params
    try:
        params_of_individual_sts = ast.literal_eval(BotAsset.params2)[0]
    except Exception:
        try:
            params_of_individual_sts = eval(BotAsset.params2)[0]
        except Exception:
            send_to_telegram(f"Error: Could not parse params in params2 for {asset_to_operate}", apiToken, chatID)
            return

    broker = BotAsset.broker
    prev_pos = BotAsset.position
    prev_qty_open = BotAsset.qty_open
    prev_cap_to_trade = BotAsset.cap_to_trade
    prev_cap_to_add = BotAsset.cap_to_add
    prev_cap_value_in_trade = BotAsset.cap_value_in_trade
    prev_op_price = BotAsset.op_price
    prev_last_price = BotAsset.last_price
    prev_pnl = BotAsset.PNL
    prev_pnl_un = BotAsset.pnl_un
    prev_trades = BotAsset.trades
    prev_coms = BotAsset.coms

    coms_per_trade = BotAsset.broker.coms
    today = pd.Timestamp.today()

    # Descargar velas del asset de SEÑALES
    df_signals = check_last_ohlc_and_download_data(asset_signals, apiToken, chatID)
    if df_signals is None or df_signals.empty:
        send_to_telegram(f"Failed to download {asset_signals} data (signals)", apiToken, chatID)
        return

    # Descargar velas del asset de OPERACION
    df_operate = check_last_ohlc_and_download_data(asset_to_operate, apiToken, chatID)
    if df_operate is None or df_operate.empty:
        send_to_telegram(f"Failed to download {asset_to_operate} data (operate)", apiToken, chatID)
        return

    params = params_of_individual_sts
    nombre = individual_sts_names

    print(f'----------------------------------------------------------')
    print("")
    print("STATUS STRATEGY CROSS ASSETS")
    print(f'{nombre}:: Signals:{asset_signals} -> Operate:{asset_to_operate}')

    # Correr estrategia en asset de señales
    new_pos, signal_close, _, _ = strategy_functions[nombre](df_signals, params)
    
    # Precio actual del asset de operación
    new_close = df_operate['Close'].iloc[-1]
    
    new_cap_value_in_trade = prev_qty_open * new_close
    pnl_group = new_cap_value_in_trade - prev_cap_to_trade - coms_per_trade
    
    message_order = ""
    message_order += f'{bot_asset_id}-{asset_to_operate} (Sig:{asset_signals}) -- TotPNL: ${prev_pnl}\n' 
    message_order += f'-> {broker} \n'

    change_side = False

    if (prev_pos == new_pos):
        if prev_pos == 0:
            message_order += f'No position -> KEEP\n'
        else:
            message_order += f'Pos Value: {round(new_cap_value_in_trade,1)}USD\n'
            message_order += f'Pos pnl: {round(pnl_group,1)}USD\n'
            message_order += f'--> KEEP {prev_qty_open}qty KEEP\n'
            if operate == True:
                BotAsset.cap_value_in_trade = new_cap_value_in_trade
                BotAsset.pnl_un = pnl_group
                BotAsset.last_price = new_close
                BotAsset.updated_date = today
                BotAsset.save()

    # si cierra largo o corto
    if ((prev_pos != 0) & (new_pos != prev_pos)):

        new_pnl = pnl_group 
        new_pnl_un = 0
        new_op_price = new_close
        new_trades = prev_trades + 0.5
        new_coms = prev_coms + coms_per_trade
        new_position = 0
        new_qty_open = 0
        new_cap_to_trade = new_cap_value_in_trade - coms_per_trade
        new_cap_value_in_trade = 0
     
        if operate == True:
            BotAsset.position = 0
            BotAsset.qty_open = 0
            BotAsset.cap_to_trade = new_cap_to_trade
            BotAsset.cap_value_in_trade = 0
            BotAsset.op_price = new_op_price
            BotAsset.last_price = new_close
            BotAsset.pnl_un = 0
            BotAsset.PNL = prev_pnl + new_pnl
            BotAsset.trades = new_trades
            BotAsset.coms = new_coms
            BotAsset.updated_date = today
            BotAsset.save() 
        
        message_order += f'Pos pnl: {round(prev_pnl_un,1)}USD\n'
        message_order += f'CLOSE POSITION\n'
        message_order += f'--> Sell {round(prev_cap_value_in_trade,1)}USD\n'
        message_order += f'--> Sell -{prev_qty_open}qty SELL ALL\n'

        if new_pos != 0:
            change_side = True

    # si abre largo o corto desde 0
    if (change_side == True) | ((prev_pos == 0) & (new_pos != 0)):

        if change_side == True:
            new_cap_to_trade = new_cap_to_trade + prev_cap_to_add - coms_per_trade
            new_trades = new_trades + 0.5
            new_coms = new_coms + coms_per_trade
        else:
            new_cap_to_trade = prev_cap_to_trade + prev_cap_to_add - coms_per_trade
            new_trades = prev_trades + 0.5
            new_coms = prev_coms + coms_per_trade

        new_cap_to_add = 0
        new_cap_value_in_trade = new_cap_to_trade 
        new_qty_open = round_down(new_cap_value_in_trade/new_close,4)
        new_op_price = new_close

        if operate == True:
            BotAsset.position = new_pos
            BotAsset.qty_open = new_qty_open
            BotAsset.cap_to_trade = new_cap_to_trade
            BotAsset.cap_to_add = new_cap_to_add
            BotAsset.cap_value_in_trade = new_cap_value_in_trade
            BotAsset.op_price = new_op_price
            BotAsset.last_price = new_close
            BotAsset.pnl_un = 0
            BotAsset.trades = new_trades
            BotAsset.coms = new_coms
            BotAsset.updated_date = today
            BotAsset.save() 
        
        # just open long
        if new_pos == 1:
            message_order += f'--> Buy {round(new_cap_to_trade,1)}USD\n'
            message_order += f'--> Buy +{new_qty_open}qty BUY\n'
            
        if new_pos == -1:
            message_order += f'--> Sell short {round(new_cap_to_trade,1)}USD\n'
            message_order += f'--> Sell short +{new_qty_open}qty SELL short\n'
         

    message_order += f'________________\n'
    return message_order

def signal_dollar_bot(BotAsset, operate=False):
    url_trm = "https://www.datos.gov.co/api/views/ceyp-9c7c/rows.csv?accessType=DOWNLOAD"
    url_json = "https://datos.gov.co/api/views/ceyp-9c7c/rows.json" #llave data item[0]
    trm_gov=requests.get("https://www.datos.gov.co/api/views/ceyp-9c7c/rows.csv?accessType=DOWNLOAD")
    data = trm_gov.content.decode('utf8')
    df_read = pd.read_csv(io.StringIO(data))
    df = df_read.drop(columns=["VIGENCIAHASTA"])
    df = df.rename(columns={"VALOR":"Close","VIGENCIADESDE":"Date"})
    df["Date"]=pd.to_datetime(df["Date"], format="%d/%m/%Y")
    usd_kls = df.sort_values(by="Date", ascending=True).reset_index(drop=True).copy()

    zscore_period = 10
    zs_buy_level = -1.9
    bb_period = 10
    bb_std = 2
    
    usd_kls["zscore"]=zscore(usd_kls,zscore_period,"Close")
    usd_kls["BB_mid"] = usd_kls["Close"].rolling(window=bb_period).apply(lambda x: np.mean(x))
    usd_kls["BB_std"] = usd_kls["Close"].rolling(window=bb_period).apply(lambda x: np.std(x))
    usd_kls["BB_low"] = usd_kls.BB_mid - usd_kls.BB_std*bb_std
    usd_kls["BB_high"] = usd_kls.BB_mid + usd_kls.BB_std*bb_std

    last_index = len(usd_kls.index.values) - 1
    previous_index = last_index -1 

    print(usd_kls.tail(30))

    usdcop = round(usd_kls.loc[last_index,"Close"],1)
    zvalue = round(usd_kls.loc[last_index,"zscore"],2)
    bbdvalue = round(usd_kls.loc[last_index,"BB_low"],2)

    prev_usdcop = round(usd_kls.loc[previous_index,"Close"],1)
    prev_zvalue = round(usd_kls.loc[previous_index,"zscore"],2)
    prev_bbdvalue = round(usd_kls.loc[previous_index,"BB_low"],2)

    message_order = ""
    message_order += f'-----------\n'
    message_order += f'USDCOP: ${usdcop}\n'
    message_order += f'z: {zvalue}\n'
    message_order += f'BB Down: {bbdvalue}\n'
    message_order += f'-----------\n'
    if ((zvalue < zs_buy_level)&(prev_zvalue > zs_buy_level))|((usdcop<bbdvalue)&(prev_usdcop>prev_bbdvalue)):
        message_order += f'BUY DOLLARS!!!\n'
    else:
        message_order += f'Dont Buy yet!\n'
    message_order += f'-----------------------------\n'

    return message_order


def signal_options_bot(BotAsset, operate=False):
    
    bot_asset_id = BotAsset.id
    asset = BotAsset.asset
    apiToken = BotAsset.bot.tg_key1
    chatID = BotAsset.bot.tg_key2

    bot_id = BotAsset.bot.id
    family_id = BotAsset.bot.family.id
    assets = BotAsset.__class__.objects.filter(bot__family__id=family_id, bot__id=bot_id, operate=True)

    message_order = ""
    if BotAsset == assets[0]:
        message_order += signal_options_bot_macro(BotAsset)
    
    individual_sts_names = parse_string_list(BotAsset.params1)[0]
    # params2 contains nested lists of numbers, eval works fine, or ast.literal_eval is safer
    try:
        params_of_individual_sts = ast.literal_eval(BotAsset.params2)[0]
    except Exception:
        params_of_individual_sts = eval(BotAsset.params2)[0]
      

    #descargar velas
    downloaded_df = check_last_ohlc_and_download_data(asset,apiToken,chatID)

    if downloaded_df is None or downloaded_df.empty :
        send_to_telegram(f"Failed to download {asset} data",apiToken, chatID)
        return

    data = downloaded_df
    params = params_of_individual_sts
    nombre = individual_sts_names

    print(f'----------------------------------------------------------')
    print("STATUS STRATEGY")
    print(f'ST{nombre}::{asset}')

    new_pos, close, _ , data_st = strategy_functions[nombre](data, params)  
    
    close = round(data_st['Close'].iloc[-1],2)
    prev_close = round(data_st['Close'].iloc[-2],2)

    if new_pos!=0:

        message_order += f'-----------\n'
        message_order += f'ST{asset}::{nombre}::\n'
        message_order += f'Close:{close}-Prev{prev_close}\n'
        message_order += f'BUYYY BUY BUY BUYYYY\n'
        message_order += f'-----------\n'
    return message_order




def signal_options_bot_macro(BotAsset):

    available_capital = BotAsset.bot.capital_active
    apiToken = BotAsset.bot.tg_key1
    chatID = BotAsset.bot.tg_key2
    
    message_order = "OPTIONS ALERTS:\n"

    list_macro_assets = ["^VIX","HYG", "LQD", "DX-Y.NYB"]
    for asset in list_macro_assets:
        data_macro = check_last_ohlc_and_download_data(asset,apiToken,chatID)
        data_macro["date_str"] = pd.to_datetime(data_macro["Date"]).dt.strftime('%Y-%m-%d')
        if asset is list_macro_assets[0]:
            df_master = data_macro
            df_master.rename(columns={'Close': asset}, inplace=True)
        if data_macro is not None and asset is not list_macro_assets[0]:
            df_master = df_master.merge(data_macro[["date_str","Close"]], on="date_str", how="left")
            df_master.rename(columns={'Close': asset}, inplace=True)

    df_master.rename(columns={"DX-Y.NYB": "DXY", "^VIX": "VIX"}, inplace=True)
    df_master.dropna(inplace=True)
    print(df_master)
    df_master.reset_index(inplace=True)
    def get_rolling_slope(series, window=10):
        y = series.values
        x = np.arange(window)
        sum_x, sum_x2 = np.sum(x), np.sum(x**2)
        divisor = window * sum_x2 - sum_x**2
        slopes = [np.nan] * (window - 1)
        for i in range(window, len(y) + 1):
            y_slice = y[i-window:i]
            m = (window * np.sum(x * y_slice) - sum_x * np.sum(y_slice)) / divisor
            slopes.append(m)
        return pd.Series(slopes, index=series.index)

    def get_zscore(series, window=60):
        r = series.rolling(window=window)
        return (series - r.mean()) / r.std(ddof=0)
    
    df_master["Z_Risk"] = get_zscore(df_master["HYG"] / df_master["LQD"], window=28)
    df_master["Z_DXY"] = get_zscore(df_master["DXY"], window=28)
    df_master["Slope_Risk"] = get_rolling_slope(df_master["Z_Risk"], window=3)
    df_master["Slope_DXY"] = get_rolling_slope(df_master["Z_DXY"], window=3)
    df_master["Slope_Risk10"] = get_rolling_slope(df_master["Z_Risk"], window=10)
    df_master["Slope_DXY10"] = get_rolling_slope(df_master["Z_DXY"], window=10)

    df_master["Cond_RisKOn"] = np.where(df_master["Slope_Risk"] > 0, 1, 0)
    df_master["Cond_DollarStrong"] = np.where(df_master["Slope_DXY"] > 0, 1, 0)
    df_master["Cond_RisKOn10"] = np.where(df_master["Slope_Risk10"] > 0, 1, 0)
    df_master["Cond_DollarStrong10"] = np.where(df_master["Slope_DXY10"] > 0, 1, 0)
    df_master["Cond_HighVol"] = np.where(df_master["VIX"] > 20, 1, 0)

    df_master["Scenario_ID"] = (
        df_master["Cond_RisKOn"].astype(str) + "|" +
        df_master["Cond_DollarStrong"].astype(str) + "|" +
        df_master["Cond_HighVol"].astype(str)
    )
    df_master["Scenario_ID10"] = (
        df_master["Cond_RisKOn10"].astype(str) + "|" +
        df_master["Cond_DollarStrong10"].astype(str) + "|" +
        df_master["Cond_HighVol"].astype(str)
    )

    name_scenario ={
        "1|0|1": {"msg": "OPERAR FUERTE (Diver)(Mag QQQ)", "per": 0.15},
        "1|0|0": {"msg": "OPERAR (Buy the Dip)(Mag QQQ)", "per": 0.1},
        "0|1|1": {"msg": "OPERAR (Pánico)(smallC ARKK)", "per": 0.1},
        "0|0|1": {"msg": "OPERAR (Pánico)(smallC ARKK)", "per": 0.1},
        "1|1|0": {"msg": "OPERAR POCO", "per": 0.05},
        "1|1|1": {"msg": "NO OPERAR (Zona de Ruido)", "per": 0},
        "0|1|0": {"msg": "OPERAR POCO", "per": 0.05},
        "0|0|0": {"msg": "OPERAR POCO", "per": 0.05},
    }
    name_scenario_10 = {
        "0|0|1": {"msg": "OPERAR FUERTE (smallC ARKK)", "per": 0.15},
        "0|1|1": {"msg": "OPERAR FUERTE (Mag QQQ)", "per": 0.15},
        "1|1|1": {"msg": "OPERAR", "per": 0.1},
        "1|0|0": {"msg": "OPERAR (NO smallC)", "per": 0.1},
        "0|1|0": {"msg": "OPERAR", "per": 0.1},
        "0|0|0": {"msg": "NO OPERAR", "per": 0},
        "1|0|1": {"msg": "NO OPERAR", "per": 0},
        "1|1|0": {"msg": "NO OPERAR (Muerte lenta)", "per": 0},
    }

    last_row = df_master.iloc[-1]
    scenario_id = last_row["Scenario_ID"]
    scenario_id_10 = last_row["Scenario_ID10"]
    print("Scenario ID:", scenario_id)
    print("Scenario ID10:", scenario_id_10)
    print(df_master[["Slope_Risk","Slope_DXY","VIX","Scenario_ID","Scenario_ID10"]])


    message_order += f'-----------\n'
    message_order += f'Disponible: {available_capital}USDn\n'
    message_order += f'RiskOn|DollarStrong|HighVol\n'
    message_order += f'->{scenario_id} - {name_scenario[scenario_id]["msg"]} - { round(available_capital*name_scenario[scenario_id]["per"],2)}USD\n'
    message_order += f'{scenario_id_10} - {name_scenario_10[scenario_id_10]["msg"]} - {round(available_capital*name_scenario_10[scenario_id_10]["per"],2)}USD\n'
    message_order += f'-----------\n'            

    return message_order




#catalogs
bots_functions={
    "MultiStrategy": run_multi_strategy,
    "OneStrategy": run_one_strategy,
    "FollowPrice": follow_price_update_pos,
    "SignalDollar": signal_dollar_bot,
    "SignalOptions": signal_options_bot,
    "CrossAssetsOneSt": one_strategy_cross_assets,
}

if __name__ == '__main__':
    #test
    pass