
import numpy as np
import pandas as pd
from datetime import timedelta
from datetime import datetime
import json
import os
import ast
import scipy.stats as stats

import django
import sys
from pathlib import Path

# Config django environment to be able to run this script standalone
root_directory = Path(__file__).resolve().parent.parent.parent.parent
if str(root_directory) not in sys.path:
    sys.path.append(str(root_directory))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from apps.botops.models import BotAsset
from apps.backtestlab.models import BacktestResult
from apps.botops.ops.bot_catalog import check_last_ohlc_and_download_data, parse_string_list
from apps.botops.ops.strategies_catalog import strategy_functions

def execute_backtest(data, initial_equity, day_out=False, 
                       sl={'per':False,'trail_gap':False,'indicator':False,'in_again':False}, 
                       tp={'per':False,'trail_gap':False,'indicator':False,'in_again':False},
                       coms_op={"per":False,"val":1}, interval="1d",
                       as_data=False, palanca_lvs = [1,1,1,1]): #as data to use baktest data as strategy input


    sl_total = (sl['per']!=False)|(sl['trail_gap']!=False)|(sl['indicator']!=False)
    tp_total = (tp['per']!=False)|(tp['trail_gap']!=False)|(tp['indicator']!=False)

    date1 = data.loc[0,"Date"]
    date2 = data.loc[data.shape[0]-1,"Date"]
    years =  ((date2 - date1) / np.timedelta64(1, 'D'))/365
    print(years)

    #ORIGINAL
    data=data.copy() 
    data["position"]=0
    
    data["pos_in_price"]=0.0
    data["n_pos_in_price"]=0.0
    data["tp"]=0.0
    data["caeTP"]="-"
    data["sl"]=0.0
    data["caeSL"]="-"
    

    if sl_total:
        data["sl_trigg"]=0
    if tp_total:
        data["tp_trigg"]=0

    data["days_inside_st"]=0
    data["twi"]=0
    data["nex_lev"]=0.0
    data["equity"]=0.0    
    data["out_equity"]=0.0
    data["drawdown_trade"]=0.0
    data["coms_out"]=0.0
    data["coms_in"]=0.0



    longs_rets=[]
    short_rets=[]
    trades=[]
    drawdown_trades=[]
    days_inside=[]

    if sl_total:
        stops_l_triggered=[]
        stops_s_triggered=[]
    if tp:
        takes_l_triggered=[]
        takes_s_triggered=[]

    #executing every period 
    for i in range(data.shape[0]):
        palanca = palanca_lvs[1]
        if i == 0:
          data.loc[i,"position"] = 0
          data.loc[i,"equity"] = initial_equity
          continue
        if data.loc[i-1,"out_equity"] !=0:
            data.loc[i,"equity"] = data.loc[i-1,"out_equity"]
        else:
            data.loc[i,"equity"] = data.loc[i-1,"equity"]
        
        prev_position = data.loc[i-1,"position"]

        if sl_total&(sl["in_again"]==False):
            data.loc[i,"sl_trigg"] = data.loc[i-1,"sl_trigg"]
        if tp_total&(tp["in_again"]==False):
            data.loc[i,"tp_trigg"] = data.loc[i-1,"tp_trigg"]
        
        data.loc[i,"twi"] = data.loc[i-1,"twi"]
        #data.loc[ i,"nex_lev"] = palanca
        # si estamos adentro
        if prev_position != 0:
            close_price = data.loc[i,"Close"]
            open_price = data.loc[i,"Open"]

            active_tr_equity = data.loc[i,"equity"]

            if data.loc[i-1,"n_pos_in_price"] != 0:
                enter_price = data.loc[i-1,"n_pos_in_price"]
            else:
                enter_price = data.loc[i-1,"pos_in_price"]
            
            data.loc[i,"pos_in_price"] = enter_price
            data.loc[i,"days_inside_st"] = data.loc[i-1,"days_inside_st"] + 1


            active_tr_equity = data.loc[i-1,"equity"]
            #calculation of unrealized
            avg_price = (open_price + close_price)/2
            unrealized_per_sl = prev_position*(avg_price-enter_price)/enter_price
            #unrealized_pnl = active_tr_equity*unrealized_per_sl
      
            
            #actualizar sl
            if (sl["per"] != False):
                if (data.loc[i-1,"sl"]!=0):
                    data.loc[i,"sl"]=data.loc[i-1,"sl"]

            
            if (sl["trail_gap"] != False):  
 
                change_sl_enter_price = enter_price*(sl["trail_gap"]/100)
                
                # cuantas veces es lo unrealized con el gap
                unr_ratio_gap = unrealized_per_sl/sl["trail_gap"]
                #initial_stop_loss = enter_price - prev_position*change_sl_enter_price

                if (data.loc[i-1,"stop_loss"]!=0):
                    if unrealized_per_sl < (100*prev_position*(data.loc[i-1,"stop_loss"]-enter_price)/enter_price):
                        data.loc[i,"stop_loss"]=data.loc[i-1,"stop_loss"]
                    else:
                        # si el unrealized es la mitad del gap ponemos stop en "breakeven"
                        if (unr_ratio_gap > 0.5):
                            data.loc[i,"stop_loss"]=enter_price
                        else:
                            data.loc[i,"stop_loss"]=data.loc[i-1,"stop_loss"]
                        # si el unrealized sobrepasa el gap
                        if (unr_ratio_gap > 1):
                            data.loc[i,"stop_loss"]=enter_price + prev_position*(change_sl_enter_price*(unr_ratio_gap//1))
                    
            
            if (sl['indicator'] != False):
                if (data.loc[i-1,"stop_loss"]!=0):
                    data.loc[i,"stop_loss"]=data.loc[i-1,sl['indicator']]


            #actualizar tp
            if (tp["per"] != False):
                if (data.loc[i-1,"tp"]!=0):
                    data.loc[i,"tp"]=data.loc[i-1,"tp"]

            if (tp["trail_gap"] != False):  # modificar este bloque
                pass
                
            if (tp['indicator'] != False):
                if (data.loc[i-1,"tp"]!=0):
                    data.loc[i,"tp"]=data.loc[i-1,tp['indicator']]


            #Si EstamosLong
            if (prev_position == 1):
                
                close_condition = data.loc[i,"Close"]
                
                #evalue si hay que salir o mantener posicion
                #condicion de TAKEPROFIT
                if tp_total == False:
                    cond_out_tp = False
                else:
                    cond_out_tp = ((data.loc[i,"High"] > data.loc[i,"tp"])&(data.loc[i,"tp"]!=0))#&(data.loc[i,"tp"]==data.loc[i-1,"tp"]))
                    if cond_out_tp:
                        data.loc[i,"caeTP"]="TP"
                        close_condition = data.loc[i,"tp"]
                        if (tp["in_again"]==False):
                            data.loc[i,"tp_trigg"]=1
                
                #condicion de STOPLOSS
                if sl_total == False:
                    cond_out_sl = False
                else:
                    cond_out_sl = ((data.loc[i,"Low"] < data.loc[i,"sl"])&(data.loc[i,"sl"]!=0))#&(data.loc[i,"sl"]==data.loc[i-1,"stop_loss"]))
                    if cond_out_sl:
                        data.loc[i,"caeSL"]="SL"
                        close_condition = data.loc[i,"sl"]
                        if (sl["in_again"]==False):
                            data.loc[i,"sl_trigg"]=1
                
                #condicion de DAYOUT
                if day_out == False:
                    cond_day_out = False
                else: cond_day_out = (data.loc[i,"days_inside_st"]==day_out)
                
                cond_out =  data.loc[i,"cond_out_long"] | cond_out_sl | cond_out_tp | cond_day_out

                if (cond_out):

                    
                    #close position
                    
                    close_operation_price = close_condition
                    realized_per = palanca*(close_operation_price-enter_price)/enter_price
                    realized_pnl = palanca*realized_per*active_tr_equity

                    if coms_op["per"]:
                        coms_out=((active_tr_equity*palanca + realized_pnl)*coms_op["val"]/100)
                    else:
                        coms_out= coms_op["val"]
                    
                    data.loc[i,"coms_out"] = coms_out
                    data.loc[i,"PNL"] = realized_pnl - coms_out
                    data.loc[i,"PNL_per"] = 100*data.loc[i,"PNL"]/active_tr_equity
                    data.loc[i,"out_equity"]=active_tr_equity + realized_pnl - coms_out
                    data.loc[i,"unrealized_per"] = 0

 
                    #stats
                    data.loc[i,"drawdown_trade"] = min(realized_per, data.loc[i-1,"drawdown_trade"])
                    drawdown_trades.append(abs(data.loc[i,"drawdown_trade"]))
                    days_inside.append(data.loc[i,"days_inside_st"])
                    longs_rets.append(realized_per)
                    trades.append(realized_per)
                    data.loc[i,"days_inside_st"] = 0
                    
                    if cond_out_tp:
                        takes_l_triggered.append(realized_per)
                    if cond_out_sl:
                        stops_l_triggered.append(realized_per)
                    
                    if realized_per > 0:
                        data.loc[i,"twi"] = data.loc[i,"twi"] + 1
                    else:
                        data.loc[i,"twi"] = 0
                    
                    if data.loc[i,"twi"] == 0:
                        palanca = palanca_lvs[1]
                        data.loc[i,"nex_lev"] = palanca
                    elif data.loc[i,"twi"] == 1:
                        palanca = palanca_lvs[3]
                        data.loc[i,"nex_lev"] = palanca
                    elif data.loc[i,"twi"] == 2:
                        palanca = palanca_lvs[2]
                        data.loc[i,"nex_lev"] = palanca
                    elif data.loc[i,"twi"] == 3:
                        palanca = palanca_lvs[2]
                        data.loc[i,"nex_lev"] = palanca
                    else:
                        palanca = palanca_lvs[0]
                        data.loc[i,"nex_lev"] = palanca


                    data.loc[i,"position"] = 0

                else:
                    #maintain position
                    data.loc[i,"unrealized_per"] = unrealized_per_sl*100
                    data.loc[i,"position"] = 1
                    #stats
                    data.loc[i,"drawdown_trade"] = min(unrealized_per_sl, data.loc[i-1,"drawdown_trade"])

                    
            #Si EstamosShort
            if (prev_position == -1):
                
                close_condition = data.loc[i,"Close"]
        
                #condicion de TAKEPROFIT
                if tp_total == False:
                    cond_out_tp = False
                else:
                    cond_out_tp = ((data.loc[i,"Low"] < data.loc[i,"tp"])&(data.loc[i,"tp"]!=0))#&(data.loc[i,"take_profit"]==data.loc[i-1,"take_profit"]))
                                        
                    if cond_out_tp:
                        data.loc[i,"caeTP"]="TP"
                        close_condition = data.loc[i,"tp"]
                        if (tp["in_again"]==False):
                            data.loc[i,"tp_trigg"]=1
                
                #evalue si hay que salir o mantener posicion
                #condicion de STOPLOSS
                if sl_total == False:
                    cond_out_sl = False
                else:
                    cond_out_sl = ((data.loc[i,"High"] > data.loc[i,"stop_loss"])&(data.loc[i,"stop_loss"]!=0))#&(data.loc[i,"stop_loss"]==data.loc[i-1,"stop_loss"]))
                    if cond_out_sl:
                        data.loc[i,"caeSL"]="SL"
                        close_condition = data.loc[i,"sl"]
                        if (sl["in_again"]==False):
                            data.loc[i,"sl_trigg"]=1

                #condicion de DAYOUT
                if day_out == False:
                    cond_day_out = False
                else: cond_day_out = (data.loc[i,"days_inside_st"]==day_out)
                
                #evalue si hay que salir o mantener posicion
                cond_out =  data.loc[i,"cond_out_short"] | cond_out_sl | cond_out_tp | cond_day_out
                
                if cond_out:      

                    #close position
                    close_operation_price = close_condition
                    realized_per = palanca*(-close_operation_price+enter_price)/enter_price
                    realized_pnl = palanca*realized_per*active_tr_equity

                    if coms_op["per"]:
                        coms_out=((active_tr_equity*palanca + realized_pnl)*coms_op["val"]/100)
                    else:
                        coms_out= coms_op["val"]
                    
                    data.loc[i,"coms_out"] = coms_out
                    data.loc[i,"PNL"] = realized_pnl - coms_out
                    data.loc[i,"PNL_per"] = 100*data.loc[i,"PNL"]/active_tr_equity
                    data.loc[i,"out_equity"]=active_tr_equity + realized_pnl - coms_out
                    data.loc[i,"unrealized_per"] = 0

                    #stats
                    data.loc[i,"drawdown_trade"] = min(realized_per, data.loc[i-1,"drawdown_trade"])
                    drawdown_trades.append(abs(data.loc[i,"drawdown_trade"]))
                    days_inside.append(data.loc[i,"days_inside_st"])
                    short_rets.append(realized_per)
                    trades.append(realized_per)  
                    data.loc[i,"days_inside_st"] = 0 

                    if cond_out_tp:
                        takes_s_triggered.append(realized_per)
                    if cond_out_sl:
                        stops_s_triggered.append(realized_per)
                    
                    if realized_per > 0:
                        data.loc[i,"twi"] = data.loc[i,"twi"] + 1
                    else:
                        data.loc[i,"twi"] = 0

                    if data.loc[i,"twi"] == 0:
                        palanca = palanca_lvs[1]
                        data.loc[i,"nex_lev"] = palanca
                    elif data.loc[i,"twi"] == 1:
                        palanca = palanca_lvs[3]
                        data.loc[i,"nex_lev"] = palanca
                    elif data.loc[i,"twi"] == 2:
                        palanca = palanca_lvs[2]
                        data.loc[i,"nex_lev"] = palanca
                    elif data.loc[i,"twi"] == 3:
                        palanca = palanca_lvs[2]
                        data.loc[i,"nex_lev"] = palanca
                    else:
                        palanca = palanca_lvs[0]
                        data.loc[i,"nex_lev"] = palanca

                    data.loc[i,"position"] = 0

                else:

                    #maintain position
                    data.loc[i,"unrealized_per"] = unrealized_per_sl*100
                    data.loc[i,"position"] = -1
                    #stats
                    data.loc[i,"drawdown_trade"] = min(unrealized_per_sl, data.loc[i-1,"drawdown_trade"])

            else:
                pass

        #si estamos fuera
        if data.loc[i,"position"] == 0:
            #Si podems entrar en long
            if data.loc[i,"out_equity"] != 0: 
                equity_to_trade = data.loc[i,"out_equity"]
            elif data.loc[i-1,"out_equity"] != 0: 
                equity_to_trade = data.loc[i-1,"out_equity"]
            else:
                equity_to_trade = data.loc[i-1,"equity"]

            if data.loc[i-1,"pos_in_price"] == 0:
                data.loc[i,"pos_in_price"] = data.loc[i,"Close"]


            if data.loc[ i,"cond_signal_long"] == True:
                enter_to_l = True

                if sl_total:
                    if (sl["in_again"]==False):
                        if data.loc[ i-1,"cond_signal_long"] == False:
                            data.loc[i,"tp_trigg"]=0
                        else:
                            enter_to_l = False
                if tp_total:
                    if (tp["in_again"]==False):
                        if data.loc[ i-1,"cond_signal_long"] == False:
                            data.loc[i,"sl_trigg"]=0
                        else:
                            enter_to_l = False
                
                
                if enter_to_l:

                    if coms_op["per"]:
                        coms_in=((equity_to_trade*palanca)*coms_op["val"]/100)
                    else:
                        coms_in= coms_op["val"]

                    data.loc[i,"coms_in"] = coms_in
                    data.loc[i,"equity"] = equity_to_trade - coms_in
                    data.loc[i,"position"] = 1

                    if sl_total:
                        data.loc[i,"sl"] = data.loc[i,"stop_loss_in"]
                    if tp_total:
                        data.loc[i,"tp"] = data.loc[i,"take_profit_in"]
                    
                    data.loc[i,"n_pos_in_price"] = data.loc[i,"Close"]
                    if data.loc[i-1,"pos_in_price"] == 0:
                        data.loc[i,"pos_in_price"] = data.loc[i,"Close"]
                
                
                
            #Si podems entrar en Short
            if data.loc[i,"cond_signal_short"] == True:
                enter_to_s = True
        
                if sl_total:
                    if (sl["in_again"]==False):
                        if data.loc[ i-1,"cond_signal_short"] == False:
                            data.loc[i,"tp_trigg"]=0
                        else:
                            enter_to_s = False
                if tp_total:
                    if (tp["in_again"]==False):
                        if data.loc[ i-1,"cond_signal_short"] == False:
                            data.loc[i,"sl_trigg"]=0
                        else:
                            enter_to_s = False

                if enter_to_s:

                    if coms_op["per"]:
                        coms_in=((equity_to_trade*palanca)*coms_op["val"]/100)
                    else:
                        coms_in= coms_op["val"]

                    data.loc[i,"coms_in"] = coms_in
                    data.loc[i,"equity"] = equity_to_trade - coms_in
                    data.loc[i,"position"] = -1
              
                    if sl_total:
                        data.loc[i,"stop_loss"] = data.loc[i,"stop_loss_in"]
                    if tp_total:
                        data.loc[i,"tp"] = data.loc[i,"take_profit_in"]
                    
                    data.loc[i,"n_pos_in_price"] = data.loc[i,"Close"]
                    if data.loc[i-1,"pos_in_price"] == 0:
                        data.loc[i,"pos_in_price"] = data.loc[i,"Close"]
                
            if (data.loc[i,"cond_signal_short"] == False) & (data.loc[ i,"cond_signal_long"] == False) :
                data.loc[i,"twi"] = 0


    data["equity_in"]=data["equity"]

    data["equity"]=np.where((data["position"]!=0)&(data["pos_in_price"]!=0),
                            data["equity_in"]*(1+(data["position"]*(data["Close"]-data["pos_in_price"])/data["pos_in_price"])),data["equity"])
    data["equity"]=np.where((data["position"]!=0)&(data["pos_in_price"]==0),
                            data["equity_in"]*(1+(data["position"]*(data["Close"]-data["n_pos_in_price"])/data["n_pos_in_price"])),data["equity"])
    data["equity"]=np.where((data["out_equity"]>0),data["out_equity"],data["equity"])


    #Calculate the B&H returns
    data["chge_log_ptg"] = np.log(data.Close.div(data.Close.shift(1)))
    data["BH_rets"] = 100*(data.chge_log_ptg.cumsum().apply(np.exp)-1)
       
    data["Close_cummax"] = data["Close"].cummax()
    data["BH_drawdown"] = 100*(data["Close_cummax"]-data["Close"])/data["Close_cummax"]
    BH_maxdrawdown = data["BH_drawdown"].max()


    bh_rets = round(float(data.iloc[-1,:]["BH_rets"]),2)
    try:
        bh_rets_EA = round(float(100*((data.Close.iloc[-1] / data.Close.iloc[0])**(1/years)-1)),2)
    except:
        bh_rets_EA = 0

    #Calculate the Strategy returns
    data["s_position"]=data.position.shift(1)
    data.loc[0,"s_position"]=0

    data["period_returns_st"]=np.log(data.equity.div(data.equity.shift(1)))
    data.loc[0,"period_returns_st"]=0

    data.loc[0,"period_returns_st"] = 0
    
    data["cum_returns_st"]=100*(data.period_returns_st.cumsum().apply(np.exp)-1)

    if as_data:
        return data
    
    final_equity = round(float(data.loc[data.shape[0]-1,"equity"]),2)
    profit = final_equity-initial_equity
    total_comms = data["coms_out"].sum()+data["coms_in"].sum()

    data["st_rets"]= 100*((data["equity"]/initial_equity) - 1)
    
    #Calculate Drawdown
    data["cummax_equity_st"]=data["equity"].cummax()
    data["drawdown"]=100*(data["cummax_equity_st"]-data["equity"])/(data["cummax_equity_st"])
    max_drowdown= data["drawdown"].max()
    raw_returns=round(float(100*((final_equity+total_comms)-initial_equity)/initial_equity),2)
   
    try:        returns=round(float(data.loc[data.shape[0]-1,"st_rets"]),2)
    except:
        returns=0

    mean_returns_per_day=(returns/data.shape[0])

    try:
        returns_EA=round(float(100*((final_equity/initial_equity)**(1/years)-1)),2) #CAGR
    except:
        returns_EA=0
    try:
        time_invested = round(100*(abs(data["position"]).sum())/(data.shape[0]),2)
    except:
        time_invested=0
    
    #Trades
        #longs
    longs_rets = np.array(longs_rets)
    
    longs_wins = longs_rets[longs_rets>0]
    l_winners = (longs_wins).shape[0]
    
    long_loos = longs_rets[longs_rets<0]
    l_loosers = (long_loos).shape[0]
        #shorts
    short_rets = np.array(short_rets)

    short_wins = short_rets[short_rets>0]
    s_winners = (short_wins).shape[0]

    short_loos = short_rets[short_rets<0]
    s_loosers = (short_loos).shape[0]
    

    qt_winners = l_winners+s_winners
    qt_loosers = l_loosers+s_loosers

    number_of_trades=qt_winners+qt_loosers

    try:
        wl_ratio=qt_winners/qt_loosers
    except:
        wl_ratio=0
    #_
    try:
        returns_per_trade= round(returns/number_of_trades,2)
    except:
        returns_per_trade=0

    #_ratio longs/shorts returns
    sum_long_rets = np.sum(longs_rets)
    sum_short_rets = np.sum(short_rets)
    
    if (sum_long_rets > sum_short_rets):
        sesgo_long_short  = "longs"
    else:
        sesgo_long_short = "shorts"


    #_
    if l_winners+s_winners == 0:
        returns_winners_mean = 0
    elif l_winners == 0:
        returns_winners_mean = round(np.mean(short_wins),2)
    elif s_winners == 0:
        returns_winners_mean = round(np.mean(longs_wins),2)
    else:
        returns_winners_mean = round((np.mean(longs_wins) + np.mean(short_wins))/2,2)

    #_
    if l_loosers+s_loosers == 0:
        returns_loosers_mean = 0
    elif l_loosers == 0:
        returns_loosers_mean = round(np.mean(short_loos),2)
    elif s_loosers == 0:
        returns_loosers_mean = round(np.mean(long_loos),2)
    else:
        returns_loosers_mean = round((np.mean(long_loos) + np.mean(short_loos))/2,2)
    
    #_
    try:
        Profitable_per= round(100*qt_winners/(number_of_trades),2)
    except:
        Profitable_per=0
    #_
    try:
        mean_days_inside = np.mean(days_inside)
    except:
        mean_days_inside = 0

    
    #stop loss and take profits
    if sl_total:
        stops_l_triggered = np.array(stops_l_triggered)
        stops_s_triggered = np.array(stops_s_triggered)
        qty_of_sls_triggered = (stops_l_triggered).shape[0] + stops_s_triggered.shape[0]
        if ((stops_l_triggered).shape[0] > 0) & (stops_s_triggered.shape[0]>0):
            mean_rets_sls = round((np.mean(stops_l_triggered) + np.mean(stops_s_triggered))/2,2)
        elif ((stops_l_triggered).shape[0] > 0):
            mean_rets_sls = round((np.mean(stops_l_triggered)),2)
        else:
            mean_rets_sls = round((np.mean(stops_s_triggered)),2)
    else:
        qty_of_sls_triggered=0
        mean_rets_sls=0
    
    if tp_total:
        takes_l_triggered = np.array(takes_l_triggered)
        takes_s_triggered = np.array(takes_s_triggered)
        qty_of_tps_triggered = (takes_l_triggered).shape[0] + takes_s_triggered.shape[0]
        if ((takes_l_triggered).shape[0] > 0) & (takes_s_triggered.shape[0]>0):
            mean_rets_tps = round((np.mean(takes_l_triggered) + np.mean(takes_s_triggered))/2,2)
        elif ((takes_l_triggered).shape[0] > 0):
            mean_rets_tps = round((np.mean(takes_l_triggered)),2)
        else:
            mean_rets_tps = round((np.mean(takes_s_triggered)),2)
    else:
        qty_of_tps_triggered = 0
        mean_rets_tps=0


    #max drawdown per trade
    drawdown_trades = np.array(drawdown_trades)
    try:
        max_dd_trade = np.max(drawdown_trades)
    except:
        max_dd_trade = 0

    try:
        mean_dd_trade = np.mean(drawdown_trades)
    except:
        mean_dd_trade = 0

    #streaks
    max_qty_win_trade_list = []
    qty_win_trade = 0
    for tr in trades:
        if tr > 0:
            qty_win_trade += 1
        else:
            max_qty_win_trade_list.append(qty_win_trade)
            qty_win_trade = 0

    if len(max_qty_win_trade_list)==0:
        max_qty_win_trade=0
        avg_qty_win_trade=0
    else: 
        max_qty_win_trade=max(max_qty_win_trade_list)
        avg_qty_win_trade=sum(max_qty_win_trade_list)/len(max_qty_win_trade_list)

    max_qty_los_trade_list = []
    qty_los_trade = 0
    for tr in trades:
        if tr < 0:
            qty_los_trade += 1
        else:
            max_qty_los_trade_list.append(qty_los_trade)
            qty_los_trade = 0
    
    if len(max_qty_los_trade_list)==0:
        max_qty_los_trade=0
        avg_qty_los_trade=0
    else:
        max_qty_los_trade=max(max_qty_los_trade_list)
        avg_qty_los_trade=sum(max_qty_los_trade_list)/len(max_qty_los_trade_list)
    

    #other metrics
    profit_factor = (np.sum(longs_wins) + np.sum(short_wins))/abs(np.sum(short_loos) + np.sum(long_loos))
    adj_rets = round((returns_EA/(time_invested/100)),2)
    rets_risk_st = round((100*returns/(time_invested*max_drowdown)),2)
    rets_risk_trade = round((100*returns_per_trade/(mean_days_inside*mean_dd_trade)),2)

    print("_______RESULTS________")

    print('Buy & Hold returns: ',bh_rets,'%')#
    print('Buy & Hold Max Drowdown: ',BH_maxdrawdown,'%')#
    print('Strategy Returns NO Commisions: ', raw_returns,"%")#
    print('Total Commisions: $', total_comms)#
    print('Strategy Returns: ', returns,"%")#
    print('Initial Equity: $', initial_equity)#
    print('Final Equity: $', final_equity)#
    print('Profit: $', profit)#
    print('Time Invested: ', time_invested,"%")#
    print('Ajusted Returns: ', adj_rets)
    print('Max Drawdown: ', max_drowdown,"%")#
    print('Returns Risk Strategy: ', rets_risk_st)
    print('Returns Risk by Trade: ', rets_risk_trade)
    print(' ')
    print(' ')
    print('Buy & Hold returns EA: ',bh_rets_EA,'%')#
    print('Strategy returns EA (CAGR): ', returns_EA,"%")#
    print(' ')
    print(' ')
    print('No. Trades: ', number_of_trades)#
    print('Percent Profitable Trades: ', Profitable_per,"%")#
    print('Winners: ', qt_winners)  
    print('Loosers: ', qt_loosers)
    print('Long Winners: ',l_winners)
    print('Short Winners: ',s_winners)
    print('Long Loosers: ',l_loosers)
    print('Short Loosers: ',s_loosers)
    print('Long Retunrs: ',sum_long_rets)
    print('Short Retunrs: ',sum_short_rets)
    print('Sesgo Long/Short: ',sesgo_long_short)
    print(' ')
    print('Win/Loose ratio: ', wl_ratio)
    print('Returns per Trade: ', returns_per_trade,"%")#
    print('Returns per Day: ', mean_returns_per_day,"%")
    print('Returns Winners Mean: ', returns_winners_mean,"%")
    print('Returns Loosers Mean: ', returns_loosers_mean, "%")
    print('Profit Factor: ',profit_factor)#
    print('Mean days per trade: ',mean_days_inside)#
    print(' ')
    print('Average Consecutive winning Trades: ',avg_qty_win_trade)#
    print('Max Consecutive winning Trades: ',max_qty_win_trade)
    print('Average Consecutive losing Trades: ',avg_qty_los_trade)#
    print('Max Consecutive losing Trades: ',max_qty_los_trade)
    print(' ')
    print(' ')
    print('Mean Drawdown per Trade: ', mean_dd_trade,"%")#
    print('Max Drawdown per Trade: ', max_dd_trade,"%")#
    print(' ')
    print('Qty of stops loss triggered: ', qty_of_sls_triggered)#
    print('Qty of take prfit triggered: ', qty_of_tps_triggered)#
    print('Mean returns in stops loss triggered: ', mean_rets_sls)#
    print('Mean returns in take profit triggered: ', mean_rets_tps)#
    print(' ')
    

    start_test = data.loc[0,"Date"]
    end_test = data.loc[data.shape[0]-1,"Date"]

    summer_test={"start":start_test, "end":end_test, 
                 "BH_rets":bh_rets, "BH_rets_EA": bh_rets_EA, "BH_max_dd":BH_maxdrawdown,
                 "ST_rets":returns, "ST_rets_EA":returns_EA, "CAGR":returns_EA, "coms":total_comms, 
                 "in_equity":initial_equity, "fin_equity": final_equity, "profit": profit,
                 "t_invest":time_invested, "max_dd":max_drowdown, "adj_rets":adj_rets,
                 "rets_risk_st":rets_risk_st, "rets_risk_trd":rets_risk_trade, 
                 "no_trds":number_of_trades, "prof_trds":Profitable_per, 
                 "qt_wns":qt_winners, "qt_ls":qt_loosers, 
                 "long_wns":l_winners, "short_wns":s_winners, "long_ls":l_loosers, "short_ls":s_loosers, 
                 "long_rets":sum_long_rets,"short_rets":sum_short_rets,"sesgo_lg/sht":sesgo_long_short,
                 "wns/ls":wl_ratio, "rets/trds":returns_per_trade, "rets/dys":mean_returns_per_day, 
                 "wns_rets_mean":returns_winners_mean, "ls_rets_mean":returns_loosers_mean, 
                 "prof_fact":profit_factor, "dys_in_mean":mean_days_inside, 
                 "avg_wns_trds_cons":avg_qty_win_trade, "max_wns_trds_cons":max_qty_win_trade, 
                 "avg_ls_trds_cons":avg_qty_los_trade, "max_ls_trds_cons":max_qty_los_trade, 
                 "mean_dd/trd":mean_dd_trade, "max_dd/trd":max_dd_trade,
                 "qty_sls":qty_of_sls_triggered,"qty_tps":qty_of_tps_triggered,
                 "mean_rts_sl":mean_rets_sls,"mean_rts_tp":mean_rets_tps,
                 "distributions": {
                     "longs_rets": longs_rets.tolist() if hasattr(longs_rets, 'tolist') else longs_rets,
                     "short_rets": short_rets.tolist() if hasattr(short_rets, 'tolist') else short_rets,
                     "drawdown_trades": drawdown_trades.tolist() if hasattr(drawdown_trades, 'tolist') else drawdown_trades,
                     "days_inside": days_inside,
                 }} #35
                 
    return (data, summer_test)



def bootstrap_testh0_probability_distribution(returns_list, folder, name_abrev, plot=True):
    returns_list=returns_list.dropna().values
    # Número de muestras bootstrap  
    num_muestras = 5000

    statistic_of_back_test=np.mean(returns_list) # nuestro estadistico es la media
    list_of_returns_centered = returns_list - statistic_of_back_test #this to generate the null hypotesis distrobution
    estadisticas_bootstrap_ci = []
    estadisticas_bootstrap_h0=[]


    # resample for confidence interval and null hypotesis distribution using vectorized numpy
    muestras_ci = np.random.choice(returns_list, size=(num_muestras, len(returns_list)), replace=True)
    muestras_h0 = np.random.choice(list_of_returns_centered, size=(num_muestras, len(list_of_returns_centered)), replace=True)
    
    estadisticas_bootstrap_ci = muestras_ci.mean(axis=1).tolist()
    estadisticas_bootstrap_h0 = muestras_h0.mean(axis=1).tolist()

    
    confidence_interaval_30 = np.percentile(estadisticas_bootstrap_ci, [35, 65])
    confidence_interaval_50 = np.percentile(estadisticas_bootstrap_ci, [25, 75])
    confidence_interaval_70 = np.percentile(estadisticas_bootstrap_ci, [15, 85])

    # prueba de hypotesis
    nivel_de_significacia = 0.05
    media_h0 = np.mean(estadisticas_bootstrap_h0)
    desv_std_h0 = np.std(estadisticas_bootstrap_h0, ddof=1)

    Z_critico = stats.norm.ppf(1 - nivel_de_significacia)
    valor_critico = media_h0 + Z_critico * desv_std_h0

    if statistic_of_back_test > valor_critico:
        hypothesish0 = False
    else:
        hypothesish0 = True
    
    if hypothesish0 == False:
        hypothesisA = True
    else:
        hypothesisA = False

    bootstrap_results = {
        "confidence_interaval_30": list(confidence_interaval_30),
        "confidence_interaval_50": list(confidence_interaval_50),
        "confidence_interaval_70": list(confidence_interaval_70),
        "valor_critico": valor_critico,
        "hypothesish0": hypothesish0,
        "hypothesisA": hypothesisA,
        "estadisticas_bootstrap_ci": estadisticas_bootstrap_ci,
        "estadisticas_bootstrap_h0": estadisticas_bootstrap_h0,
        "media_h0": media_h0,
        "statistic_of_back_test": statistic_of_back_test
    }

    return bootstrap_results




def convert_position_to_signals(df):
    df = df.copy()
    df["cond_signal_long"] = False
    df["cond_signal_short"] = False
    df["cond_out_long"] = False
    df["cond_out_short"] = False
    
    df["prev_pos"] = df["position"].shift(1).fillna(0)
    
    df.loc[(df["prev_pos"] == 0) & (df["position"] == 1), "cond_signal_long"] = True
    df.loc[(df["prev_pos"] == 0) & (df["position"] == -1), "cond_signal_short"] = True
    
    df.loc[(df["prev_pos"] == 1) & (df["position"] != 1), "cond_out_long"] = True
    df.loc[(df["prev_pos"] == -1) & (df["position"] != -1), "cond_out_short"] = True
    
    # Reverse positions
    df.loc[(df["prev_pos"] == -1) & (df["position"] == 1), "cond_signal_long"] = True
    df.loc[(df["prev_pos"] == 1) & (df["position"] == -1), "cond_signal_short"] = True
    
    return df

def run(bot_asset_id):
    bot_asset = BotAsset.objects.get(id=bot_asset_id)
    asset = bot_asset.asset
    apiToken = bot_asset.bot.tg_key1
    chatID = bot_asset.bot.tg_key2
    
    # Extract params
    individual_sts_names = parse_string_list(bot_asset.params1) if bot_asset.params1 else []
    try:
        params_of_individual_sts = ast.literal_eval(bot_asset.params2) if bot_asset.params2 else []
    except Exception:
        params_of_individual_sts = eval(bot_asset.params2) if bot_asset.params2 else []

    if not individual_sts_names:
        print("No strategy defined")
        return
        
    print(f"Running backtest for BotAsset {bot_asset_id} - {asset} with {individual_sts_names}")

    # download data
    print("Downloading data...")
    downloaded_df = check_last_ohlc_and_download_data(asset, apiToken, chatID)
    if downloaded_df is None or downloaded_df.empty:
        print("Failed to download data.")
        return

    # create signals combining multiple strategies
    print("Creating combined signals...")
    data_st = downloaded_df.copy()
    data_st["sum_position"] = 0

    for idx, st_name in enumerate(individual_sts_names):
        st_params = params_of_individual_sts[idx] if idx < len(params_of_individual_sts) else None
        # Use a fresh copy so strategies don't conflict with each other
        _, _, _, temp_data = strategy_functions[st_name](downloaded_df.copy(), st_params)
        
        temp_pos_df = temp_data[["Date", "position"]].rename(columns={"position": f"pos_{idx}"})
        data_st = data_st.merge(temp_pos_df, on="Date", how="left")
        # Sum up positions, treating NAs as 0
        data_st["sum_position"] += data_st[f"pos_{idx}"].fillna(0)

    # Determine grouped position
    data_st["position"] = np.select([data_st["sum_position"] > 0, data_st["sum_position"] < 0], [1, -1], default=0)
    
    # Convert grouped positions to execute_backtest readable signals
    data_st = convert_position_to_signals(data_st)

    end_date = data_st["Date"].max()
    slices = [
        {"period": "all", "start_date": data_st["Date"].min()},
        {"period": "5y", "start_date": end_date - timedelta(days=5*365)},
        {"period": "1y", "start_date": end_date - timedelta(days=365)},
        {"period": "1q", "start_date": end_date - timedelta(days=90)},
    ]

    initial_equity = 10000

    for s in slices:
        print(f"\n================ Executing Backtest for {s['period']} ================")
        df_slice = data_st[data_st["Date"] >= s["start_date"]].copy()
        if df_slice.empty:
            print(f"No data for slice {s['period']}")
            continue
            
        df_slice = df_slice.reset_index(drop=True)
        
        # backtest
        try:
            bt_data, summer_test = execute_backtest(df_slice, initial_equity=initial_equity)
        except Exception as e:
            print(f"Error backtesting {s['period']}: {e}")
            continue
            
        # bootstrap
        longs_rets = summer_test["distributions"]["longs_rets"]
        short_rets = summer_test["distributions"]["short_rets"]
        all_rets = np.array(longs_rets + short_rets)
        if len(all_rets) > 1:
            try:
                bootstrap_res = bootstrap_testh0_probability_distribution(pd.Series(all_rets), "", "", plot=False)
                summer_test["bootstrap"] = bootstrap_res
            except Exception as e:
                print(f"Error in bootstrap for {s['period']}: {e}")
                summer_test["bootstrap"] = None
        else:
            summer_test["bootstrap"] = None

        # Create or update BacktestResult
        # To avoid type errors, replace NaN with None and Timestamp with string in metrics
        def clean_dict(d):
            if isinstance(d, dict):
                return {k: clean_dict(v) for k, v in d.items()}
            elif isinstance(d, list):
                return [clean_dict(v) for v in d]
            elif isinstance(d, (np.integer, int)):
                return int(d)
            elif isinstance(d, (np.floating, float)):
                if np.isnan(d) or np.isinf(d):
                    return None
                return float(d)
            elif hasattr(d, 'isoformat'): # Handles datetime and pandas Timestamp
                return d.isoformat()
            return d

        summer_test_clean = clean_dict(summer_test)

        equity_curve = {
            "Date": bt_data["Date"].dt.strftime("%Y-%m-%d").tolist(),
            "cum_returns_st": clean_dict(bt_data["cum_returns_st"].tolist())
        }
        
        bh_curve = {
            "Date": bt_data["Date"].dt.strftime("%Y-%m-%d").tolist(),
            "BH_rets": clean_dict(bt_data["BH_rets"].tolist())
        }
        
        drawdown_curve = {
            "Date": bt_data["Date"].dt.strftime("%Y-%m-%d").tolist(),
            "drawdown": clean_dict(bt_data["drawdown"].tolist())
        }
        
        distributions = summer_test_clean.pop("distributions", {})
        bootstrap = summer_test_clean.pop("bootstrap", {})
        distributions["bootstrap"] = bootstrap

        # Retry loop for handling SQLite 'database is locked' errors
        import time
        from django.db import OperationalError
        for attempt in range(5):
            try:
                BacktestResult.objects.update_or_create(
                    bot_asset=bot_asset,
                    period=s["period"],
                    defaults={
                        "metrics": summer_test_clean,
                        "distributions": distributions,
                        "equity_curve": equity_curve,
                        "bh_curve": bh_curve,
                        "drawdown_curve": drawdown_curve
                    }
                )
                print(f"Saved BacktestResult for {s['period']}")
                break
            except OperationalError as e:
                if 'locked' in str(e) and attempt < 4:
                    print(f"Database locked, retrying {attempt+1}/5...")
                    time.sleep(1)
                else:
                    raise

from django_q.tasks import async_task

def run_all_active_bots():
    active_assets = BotAsset.objects.filter(operate=True)
    for bot_asset in active_assets:
        try:
            # Enqueue each bot as a separate task to avoid global timeout and allow parallel execution
            async_task('apps.backtestlab.scripts.backtest_model.run', bot_asset.id)
            print(f"Enqueued backtest task for BotAsset {bot_asset.id}")
        except Exception as e:
            print(f"Error enqueuing backtest for BotAsset {bot_asset.id}: {e}")

if __name__=="__main__":
    if len(sys.argv) > 1:
        run(sys.argv[1])
    else:
        print("Please provide bot_asset_id as argument")