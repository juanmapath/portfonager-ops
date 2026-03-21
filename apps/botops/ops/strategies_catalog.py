import sys
from pathlib import Path
from datetime import timedelta

import pandas as pd
import numpy as np
import statsmodels.api as sm

root_directory = Path(__file__).resolve().parent.parent.parent.parent
if str(root_directory) not in sys.path:
    sys.path.append(str(root_directory))
from apps.botops.ops.tgrm import send_to_telegram
from apps.botops.ops.indicators import supertrend, MACD, RSI, zscore
from apps.botops.ops.candles_down import download_data


#mean reversion strategies

def bollinger_bands(data, params):

  ma = params[0]
  mult = params[1]

  index_of_strategy = f"{ma}_{mult}"
   
  data = data.copy()
  print(f"----- BollingerBands_ma{ma}_std{mult} - MeanRev ----")

  data["BB_mid"] = data["Close"].rolling(window=ma).apply(lambda x: np.mean(x))
  data["BB_std"] = data["Close"].rolling(window=ma).apply(lambda x: np.std(x))
  data["BB_down"] = data.BB_mid - data.BB_std*mult

  data["cond_BBdown"]=np.where((data["Close"]<data["BB_down"]),True,False)
  data = data.dropna().reset_index(drop=True)
  data["position"]=0
  data["position_enter_price"]=0.0
  data["position_enter_price"] = data["position_enter_price"].astype(float)
  data["unrealized_PL"]=0.0
  data["unrealized_PL"] = data["unrealized_PL"].astype(float)
  data["unrealized_PL_per"]=0.0


  for i in range(data.shape[0]):
      if i == 0:
        data.loc[i,"position"] = 0
        continue
      #si estamos fuera
      if data.loc[i-1,"position"].item() == 0:
        #Evalue si hay que entrar en la posicion
        if data.loc[i,"cond_BBdown"].item() == True:
          data.loc[i,"position"] = 1
          data.loc[i,"position_enter_price"] = data.loc[i,"Close"]
        else:
          continue
      
      #Si estamos dentro
      else:
        enter_price = data.loc[i-1,"position_enter_price"]
        close_price = data.loc[i,"Close"]
        data.loc[i,"position_enter_price"] = enter_price
        data.loc[i,"unrealized_PL"] = close_price-enter_price
        data.loc[i,"unrealized_PL_per"] = round((100*(close_price-enter_price)/enter_price),2)
        
        #Evalue si hay que salir o mantener la posicion
        if data.loc[i,"Close"] > data.loc[i-1,"High"]:
          data.loc[i,"position"] = 0
        else:
          data.loc[i,"position"] = 1
  
  previous_row=(data.iloc[-2,:]).to_dict()
  current_row=(data.iloc[-1,:]).to_dict()

  data_to_show=data[["Date","Close","BB_down","cond_BBdown","position","unrealized_PL"]].tail(15)
  print(data_to_show)
  print('------->')

  return [current_row["position"],current_row["Close"],current_row["unrealized_PL_per"],data]


def money_flow_index(data, params):
   
    data = data.copy()

    mfi_periods = params[0]
    in_mfi = params[1]
    days_in = params[2]
    
    
    data = data.copy()
    print(f"----- MoneyFlowIndex_mfi_periods{mfi_periods}_in_mfi{in_mfi}_days_in{days_in} - MeanRev ----")

    #MFI INDICATOR
    serie = data.copy()
    serie["TP"]=(serie['High'] + serie['Low'] + serie['Close']) / 3  #tipical Price
    serie['RMF'] = serie['TP'] * serie['Volume'] #Raw Money Flow (RMF)

    # Calculate Positive Money Flow (PMF) and Negative Money Flow (NMF) for each period
    serie['PMF'] = serie['RMF'].where(serie['Close'] > serie['Close'].shift(1), 0)
    serie['NMF'] = serie['RMF'].where(serie['Close'] < serie['Close'].shift(1), 0)
    # Calculate Money Ratio (MR) for each period
    serie['MR'] = serie['PMF'].rolling(window=mfi_periods).sum() / serie['NMF'].rolling(window=mfi_periods).sum()
    # Calculate Money Flow Index (MFI) for each period
    data['MFI'] = 100 - (100 / (1 + serie['MR']))

    #CONDITIONS
    data["cond_MFI"]=np.where((data["MFI"]<in_mfi),True,False)

    #STRATEGY EXECUTION
    data = data.dropna().reset_index(drop=True)
    data["position"]=0
    data["days_in_trade"]=0
    data["position_enter_price"]=0.0
    data["position_enter_price"] = data["position_enter_price"].astype(float)
    data["unrealized_PL"]=0.0
    data["unrealized_PL"] = data["unrealized_PL"].astype(float)
    data["unrealized_PL_per"]=0.0

    days_in_trade=0

    for i in range(data.shape[0]):
      if i == 0:
        data.loc[i,"position"] = 0
        continue

      #si estamos fuera
      if data.loc[i-1,"position"] == 0:
        #Evalue si hay que entrar en la posicion
        if ((data.loc[ i,"cond_MFI"] == True)):
          data.loc[i,"position"] = 1
          data.loc[i,"position_enter_price"] = data.loc[i,"Close"]
        else:
          continue
      #Si estamos dentro
      else:
        enter_price = data.loc[i-1,"position_enter_price"]
        close_price = data.loc[i,"Close"]
        data.loc[i,"position_enter_price"] = enter_price
        data.loc[i,"unrealized_PL"] = close_price-enter_price
        data.loc[i,"unrealized_PL_per"] = round((100*(close_price-enter_price)/enter_price),2)
        #Evalue si hay que salir o mantener la posicion
        days_in_trade+=1
        if ((data.loc[ i,"Close"] > data.loc[ i-1,"High"])|((days_in_trade==days_in))):
          data.loc[i,"position"] = 0
          days_in_trade=0
        else:
          data.loc[i,"position"] = 1
        data.loc[i,"days_in_trade"] = days_in_trade

    previous_row=(data.iloc[-2,:]).to_dict()
    current_row=(data.iloc[-1,:]).to_dict()

    data_to_show=data[["Date","Close","High","MFI","position","days_in_trade","unrealized_PL"]].tail(15)
    print(data_to_show)
    print('------->')
    return [current_row["position"],current_row["Close"],current_row["unrealized_PL_per"],data]


def lowest_low(data, params):
    
    data = data.copy()

    lookback = params[0]
    sl = -params[1]
    
    index_of_strategy = f"{lookback}_{sl}"
    
    data = data.copy()
    print(f"----- LowestLow_lookback{lookback}_sl{sl} - MeanRev ----")


    #CONDITIONS
    data["lowest_back"]=data.Low.rolling(lookback).min()
    data["cond_NR"]=np.where(((data["Low"]==data["lowest_back"])),True,False)

    data = data.dropna().reset_index(drop=True)
    data["position"]=0
    data["position_enter_price"]=0.0
    data["position_enter_price"] = data["position_enter_price"].astype(float)
    data["unrealized_PL"]=0.0
    data["unrealized_PL"] = data["unrealized_PL"].astype(float)
    data["unrealized_PL_per"]=0.0


    for i in range(data.shape[0]):
      if i == 0:
        data.loc[i,"position"] = 0
        continue

      #si estamos fuera
      if data.loc[ i-1,"position"] == 0:
        #Evalue si hay que entrar en la posicion
        if (data.loc[ i,"cond_NR"] == True):
          data.loc[i,"position"] = 1
          data.loc[i,"position_enter_price"] = data.loc[i,"Close"]
        else:
          continue
      #Si estamos dentro
      else:
        enter_price = data.loc[i-1,"position_enter_price"]
        close_price = data.loc[i,"Close"]
        data.loc[i,"position_enter_price"] = enter_price
        data.loc[i,"unrealized_PL"] = close_price-enter_price
        data.loc[i,"unrealized_PL_per"] = round((100*(close_price-enter_price)/enter_price),2)
        
        #Evalue si hay que salir o mantener la posicion
        if (data.loc[ i,"Close"] > data.loc[ i-1,"High"])|(data.loc[i,"unrealized_PL_per"]<sl):
          data.loc[i,"position"] = 0
        else:
          data.loc[i,"position"] = 1


    previous_row=(data.iloc[-2,:]).to_dict()
    current_row=(data.iloc[-1,:]).to_dict()

    data_to_show=data[["Date","Close","Low","High","lowest_back","cond_NR","position", "unrealized_PL", "unrealized_PL_per"]].tail(15)
    print(data_to_show)
    print('------->')

    print('Position to take:',current_row["position"])

    return [current_row["position"],current_row["Close"],current_row["unrealized_PL_per"],data]


def rsi_weakness(data, params):
   
    rsi_period = params[0]
    in_rsi = params[1]

    index_of_strategy = f"{rsi_period}_{in_rsi}"
    
    data = data.copy()
    print(f"----- RSI_Weakness_rsi_period{rsi_period}_in_rsi{in_rsi} - MeanRev ----")

    #RSI INDICATOR
    serie = data.Close.copy().to_frame()
    serie["change"]=serie.Close.diff()
    serie["changeup"] = np.where(serie["change"]>0,serie["change"],0)
    serie["changedown"] = np.where(serie["change"]<0,serie["change"],0)
    avg_up = serie["changeup"].rolling(rsi_period).mean()
    avg_down = serie["changedown"].rolling(rsi_period).mean().abs()
    data["rsi"] = round(((100 * avg_up) / (avg_up + avg_down)),2)

    data["cond_RSI"]=np.where((data["rsi"] < in_rsi),True,False)
    data = data.dropna().reset_index(drop=True)
    data["position"]=0
    data["position_enter_price"]=0.0
    data["position_enter_price"] = data["position_enter_price"].astype(float)
    data["unrealized_PL"]=0.0
    data["unrealized_PL"] = data["unrealized_PL"].astype(float)
    data["unrealized_PL"] = data["unrealized_PL"].astype(float)
    data["unrealized_PL_per"]=0.0
    data["unrealized_PL_per"] = data["unrealized_PL_per"].astype(float)

    for i in range(data.shape[0]):
        if i == 0:
          data.loc[i,"position"] = 0
          continue
        #si estamos fuera
        if data.loc[i-1,"position"].item() == 0:
          #Evalue si hay que entrar en la posicion
          if data.loc[i,"cond_RSI"].item() == True:
            data.loc[i,"position"] = 1
            data.loc[i,"position_enter_price"] = data.loc[i,"Close"]
          else:
            continue
        
        #Si estamos dentro
        else:
          enter_price = data.loc[i-1,"position_enter_price"]
          close_price = data.loc[i,"Close"]
          data.loc[i,"position_enter_price"] = enter_price
          data.loc[i,"unrealized_PL"] = close_price-enter_price
          data.loc[i,"unrealized_PL_per"] = round((100*(close_price-enter_price)/enter_price),2)
          
          #Evalue si hay que salir o mantener la posicion
          if data.loc[i,"Close"] > data.loc[i-1,"High"]:
            data.loc[i,"position"] = 0
          else:
            data.loc[i,"position"] = 1
    
    previous_row=(data.iloc[-2,:]).to_dict()
    current_row=(data.iloc[-1,:]).to_dict()

    data_to_show=data[["Date","Close","rsi","cond_RSI","position","unrealized_PL"]].tail(20)
    print(data_to_show)
    print('------->')

    print('Position to take:',current_row["position"])

    return [current_row["position"],current_row["Close"],current_row["unrealized_PL_per"],data]

   
def trend_pull_back_rsi(data, params):

    rsi_window = params[0]
    out_rsi = params[1]
    in_rsi = params[2]
    ma_slow = params[3]
    ma_fast = params[4]

    
    data = data.copy()
    print(f"-----SEC TrendPullBack RSI {rsi_window}rsi__out{out_rsi}_in{in_rsi}_ma_slow{ma_slow}_ma_fast{ma_fast} - MeanRev ----")

    #RSI INDICATOR
    data["change"]=data["Close"].diff()
    data["changeup"] = np.where(data["change"]>0,data["change"],0)
    data["changedown"] = np.where(data["change"]<0,data["change"],0)
    avg_up = data["changeup"].rolling(rsi_window).mean()
    avg_down = data["changedown"].rolling(rsi_window).mean().abs()
    data["rsi"] = round(((100 * avg_up) / (avg_up + avg_down)),2)

    #MAS

    data["ma_s"] = data.Close.rolling(window=ma_slow).mean()
    data["ma_f"] = data.Close.rolling(window=ma_fast).mean()
    data["ma_pocket"] = np.where((data["Close"]< data["ma_f"])&(data["Close"] > data["ma_s"]),True, False)
    data["cond_signal_long"]=np.where((data["ma_pocket"] == True)&(data["rsi"] < in_rsi) ,True,False)

    

    #SUPERTREND
    
    supert = supertrend(data, lookback=56, multiplier=3.5)
    data["supertrend"]=supert["supertrend"]
    data["sup_bul_bear"]=np.where(data["supertrend"]>data["Close"],-1,1)
    data["sp_change"]=np.where(data["sup_bul_bear"]!=data["sup_bul_bear"].shift(),1,0)
    
    data["position"]=0
    data["position_enter_price"]=0.0
    data["position_enter_price"] = data["position_enter_price"].astype(float)
    data["unrealized_PL"]=0.0
    data["unrealized_PL"] = data["unrealized_PL"].astype(float)
    data["unrealized_PL_per"]=0.0
    data["out_by_sp"]=0
    data["out_by_st"]=0
    data["t"]=0

    #data = data.dropna().reset_index(drop=True)
    data = data.reset_index(drop=True)
    #replace nan with 0
    data = data.fillna(0)
    
    t=1

    for i in range(data.shape[0]):
        if i == 0:
          data.loc[i,"position"] = 0
          continue
        #si estamos fuera
        if data.loc[i-1,"position"].item() == 0:
          #Evalue si hay que entrar en la posicion
          if t >0:
            t+=1
          data.loc[i,"t"]=t
          #Evalue si hay que entrar en la posicion
          if (data.loc[ i,"cond_signal_long"] == True)&(t>7):#21
            t=1
            data.loc[i,"position"] = 1
            data.loc[i,"position_enter_price"] = data.loc[i,"Close"]
          else:
            continue
        
        #Si estamos dentro
        else:
          enter_price = data.loc[i-1,"position_enter_price"]
          close_price = data.loc[i,"Close"]
          data.loc[i,"position_enter_price"] = enter_price
          data.loc[i,"unrealized_PL"] = close_price-enter_price
          data.loc[i,"unrealized_PL_per"] = round((100*(close_price-enter_price)/enter_price),2)
          #Evalue si hay que salir o mantener la posicion
          if data.loc[i,"rsi"] > out_rsi:
            data.loc[i,"position"] = 0
            data.loc[i,"out_by_st"] = 1
          else:
            if (data.loc[ i,"Close"] < data.loc[i,"supertrend"])&(data.loc[i,"sp_change"]==1):
                data.loc[i,"position"] = 0
                data.loc[i,"out_by_sp"] = 1
                t=1
            else:
              data.loc[i,"position"] = 1
    
    current_row=(data.iloc[-1,:]).to_dict()

    data_to_show=data[["Date","Close","rsi","ma_s","ma_f","position","cond_signal_long","unrealized_PL"]].tail(15)
    print(data_to_show)
    print('------->')

    print('Position to take:',current_row["position"])

    return [current_row["position"],current_row["Close"],current_row["unrealized_PL_per"],data]


def buy_weakness(data, params):

  MACD_inputs = params[0]
  wr = params[2]
  weak_in = params[1]

  index_of_strategy = f"{MACD_inputs}_{wr}_{weak_in}"
  
  data = data.copy()
  print(f"----- BuyWeaknessMACD MACD_inputs{MACD_inputs}__wr{wr}_weakin{weak_in} - MeanRev ----")


  #DEMA5
  data["EMA5"]=data.Close.ewm(span=5).mean()
  data['DEMA_EMA5'] = data.EMA5.ewm(span=5).mean()
  data['DEMA5'] = 2 * data['EMA5'] - data['DEMA_EMA5']

  #EMA50
  data["EMA50"]=data.Close.ewm(span=50).mean()

  #EMA100
  data["EMA100"]=data.Close.ewm(span=100).mean()

  #EMA200
  data["EMA200"]=data.Close.ewm(span=200).mean()

  #MACDs
  fast_period = MACD_inputs[0]
  slow_period = MACD_inputs[1]
  signal_period = MACD_inputs[2]
  macd = MACD(data['Close'], fast_period, slow_period, signal_period)
  data['macd_line'] = macd[0]
  data['signal_line'] = macd[1]
  data['macd_histogram'] = macd[2]

  window_size=3
  slopes = []
  for i in range(window_size-1, len(data)):
      x = np.arange(i-window_size+1, i+1)
      y = data["macd_line"].values[i-window_size+1:i+1]
      slope, _ = np.polyfit(x, y, 1)
      slopes.append(slope)

  data['macd_slope'] = np.nan
  data.loc[window_size-1:, 'macd_slope'] = slopes

  slopes = []
  for i in range(window_size-1, len(data)):
      x = np.arange(i-window_size+1, i+1)
      y = data["macd_histogram"].values[i-window_size+1:i+1]
      slope, _ = np.polyfit(x, y, 1)
      slopes.append(slope)

  data['hist_slope'] = np.nan
  data.loc[window_size-1:, 'hist_slope'] = slopes


  #SUPERTREND
  supert = supertrend(data, lookback=fast_period, multiplier=2)
  data["supertrend"]=supert["supertrend"]
  

  #RSI
  rsi_serie=RSI(data, window=14)
  data["rsi"]=rsi_serie


  #WR INDICATOR
  wr_period=wr
  data['Highest High'] = data['High'].rolling(window=wr_period).max()
  data['Lowest Low'] = data['Low'].rolling(window=wr_period).min()
  data["WR"] = ((data['Highest High'] - data['Close']) / (data['Highest High'] - data['Lowest Low'])) * -100

  #data["cond_ema50"]=np.where(data["DEMA5"]>data["DEMA50"],1,-1)
  #data["cond_ema100"]=np.where(data["DEMA100"]>data["DEMA50"],1,-1)
  #data["cond_ema200"]=np.where(data["DEMA200"]>data["DEMA50"],1,-1)

  data["cond_ema50"]=np.where(data["DEMA5"]>data["EMA50"],1,-1)
  data["cond_ema100"]=np.where(data["EMA100"]<data["EMA50"],1,-1)
  data["cond_ema200"]=np.where(data["EMA200"]<data["EMA50"],1,-1)
  data["cond_macdline"]=np.where(data["macd_line"]>0,1,-1)
  data["cond_macdgap"]=np.where(data["macd_line"]>data["signal_line"],1,-1)
  data["cond_macdslope"]=np.where(data["macd_slope"]>0,1,-1)
  data["cond_macdsbarras"]=np.where(data["hist_slope"]>0,1,-1)
  data["cond_supert"]=np.where(data["Close"]>data["supertrend"],1,-1)
  data["cond_rsi"]=np.where(data["rsi"]>70,1,0)
  data["cond_rsi"]=np.where(data["rsi"]<30,-1,data["cond_rsi"])
  data["cond_wr"]=np.where(data["WR"]>-30,1,0)
  data["cond_wr"]=np.where(data["WR"]<-30,-1,data["cond_wr"])
  data["sum"]=(data["cond_ema50"]+data["cond_ema100"]+data["cond_ema200"]+data["cond_macdline"]+
                  data["cond_macdgap"]+data["cond_macdslope"]+data["cond_macdsbarras"]+data["cond_supert"]+
                  data["cond_rsi"]+data["cond_wr"])
  

  data = data.dropna().reset_index(drop=True)
  data["position"]=0
  data["position_enter_price"]=0.0
  data["position_enter_price"] = data["position_enter_price"].astype(float)
  data["unrealized_PL"]=0.0
  data["unrealized_PL"] = data["unrealized_PL"].astype(float)
  data["unrealized_PL_per"]=0.0


  for i in range(data.shape[0]):
    if i == 0:
      data.loc[i,"position"] = 0
      continue
    #si estamos fuera
    if data.loc[ i-1,"position"]== 0:
      #Evalue si hay que entrar en la posicion
      if (data.loc[ i,"sum"] == weak_in)&(data.loc[ i-1,"sum"]> weak_in):
        data.loc[i,"position"] = 1
        data.loc[i,"position_enter_price"] = data.loc[i,"Close"]
      else:
        continue
    #Si estamos dentro
    else:
      enter_price = data.loc[i-1,"position_enter_price"]
      close_price = data.loc[i,"Close"]
      data.loc[i,"position_enter_price"] = enter_price
      data.loc[i,"unrealized_PL"] = close_price-enter_price
      data.loc[i,"unrealized_PL_per"] = round((100*(close_price-enter_price)/enter_price),2)
      #Evalue si hay que salir o mantener la posicion
      if (data.loc[ i,"Close"] > data.loc[ i-1,"High"]):
        data.loc[i,"position"] = 0
      else:
        data.loc[i,"position"] = 1


  previous_row=(data.iloc[-2,:]).to_dict()
  current_row=(data.iloc[-1,:]).to_dict()

  data_to_show=data[["Date","Close","Low","High","sum","position","unrealized_PL"]].tail(30)
  print(data_to_show)
  print('------->')

  print('Position to take:',current_row["position"])

  return [current_row["position"],current_row["Close"],current_row["unrealized_PL_per"],data]
  

def regression_rsi(data, params):
    
    data = data.copy()

    day_reg = params[0]
    rsi_win = params[1]
    
    index_of_strategy = f"{day_reg}_{rsi_win}"
    
    data = data.copy()
    print(f"----- RegresRSI_day_reg{day_reg}_rsi_win{rsi_win} - MeanRev ----")


    #LINEAR REGRESSION
    window_size = day_reg
    rsi = rsi_win
    slopes = []
    predicted_values = []


    for i in range(len(data)):
        if i >= window_size - 1:
            x = data['Close'].iloc[i - window_size + 1:i + 1]
            if len(x) > 1:
                model = sm.OLS(x, sm.add_constant(np.arange(len(x)))).fit()
                slope = model.params.iloc[1]  # Slope of the regression line
                predicted_value = model.fittedvalues.iloc[-1]  # Predicted value
                slopes.append(slope)
                predicted_values.append(predicted_value)
            else:
                slopes.append(np.nan)
                predicted_values.append(np.nan)
        else:
            slopes.append(np.nan)
            predicted_values.append(np.nan)

    # Calculate the fitted values
    data['Slope'] = slopes
    data['Predicted_Values'] = predicted_values

    #RSI INDICATOR
    serie = data.copy()
    serie["change"]=serie["Close"].diff()
    serie["changeup"] = np.where(serie["change"]>0,serie["change"],0)
    serie["changedown"] = np.where(serie["change"]<0,serie["change"],0)
    avg_up = serie["changeup"].rolling(rsi).mean()
    avg_down = serie["changedown"].rolling(rsi).mean().abs()
    data["rsi"] = round(((100 * avg_up) / (avg_up + avg_down)),2)

    

    #CONDITIONS
    data["cond_signal_long"]=np.where((data["Slope"]>0)&(data["rsi"]<30),True,False)  
    data["cond_signal_short"]=False#np.where((data["Slope"]<0)&(data["rsi"]>70),True,False) 

    data = data.dropna().reset_index(drop=True)
    data["position"]=0
    data["position_enter_price"]=0.0
    data["position_enter_price"] = data["position_enter_price"].astype(float)
    data["unrealized_PL"]=0.0
    data["unrealized_PL"] = data["unrealized_PL"].astype(float)
    data["unrealized_PL_per"]=0.0

    for i in range(data.shape[0]):
      if i == 0:
        data.loc[i,"position"] = 0
        continue

      #si estamos fuera
      if data.loc[ i-1,"position"] == 0:
        #Evalue si hay que entrar en la posicion
        if (data.loc[ i,"cond_signal_long"] == True):
          data.loc[i,"position"] = 1
          data.loc[i,"position_enter_price"] = data.loc[i,"Close"]
        elif (data.loc[ i,"cond_signal_short"] == True):
          data.loc[i,"position"] = -1
          data.loc[i,"position_enter_price"] = data.loc[i,"Close"]
        else:
          continue
      #Si estamos dentro
      else:
        enter_price = data.loc[i-1,"position_enter_price"]
        close_price = data.loc[i,"Close"]
        data.loc[i,"position_enter_price"] = enter_price

        if (data.loc[i-1,"position"] == 1):

          data.loc[i,"unrealized_PL"] = close_price-enter_price
          data.loc[i,"unrealized_PL_per"] = round((100*(close_price-enter_price)/enter_price),2)
          
          #Evalue si hay que salir o mantener la posicion
          if (data.loc[ i,"Close"] > data.loc[ i-1,"High"]):
            data.loc[i,"position"] = 0
          else:
            data.loc[i,"position"] = 1
        

    previous_row=(data.iloc[-2,:]).to_dict()
    current_row=(data.iloc[-1,:]).to_dict()

    data_to_show=data[["Date","Close","Low","High","cond_signal_long","position", "unrealized_PL", "unrealized_PL_per"]].tail(15)
    print(data_to_show)
    print('------->')

    print('Position to take:',current_row["position"])

    return [current_row["position"],current_row["Close"],current_row["unrealized_PL_per"],data]


def regression_rsi_short(data, params):
    
    data = data.copy()

    day_reg = params[0]
    rsi_win = params[1]
    
    print(f"----- RegresRSI_day_reg{day_reg}_rsi_win{rsi_win}short - MeanRev ----")


    #LINEAR REGRESSION
    window_size = day_reg
    rsi = rsi_win
    slopes = []
    predicted_values = []
    for i in range(len(data)):
        if i >= window_size - 1:
            x = data['Close'].iloc[i - window_size + 1:i + 1]
            if len(x) > 1:
                model = sm.OLS(x, sm.add_constant(np.arange(len(x)))).fit()
                slope = model.params.iloc[1]  # Slope of the regression line
                predicted_value = model.fittedvalues.iloc[-1]  # Predicted value
                slopes.append(slope)
                predicted_values.append(predicted_value)
            else:
                slopes.append(np.nan)
                predicted_values.append(np.nan)
        else:
            slopes.append(np.nan)
            predicted_values.append(np.nan)

    # Calculate the fitted values
    data['Slope'] = slopes
    data['Predicted_Values'] = predicted_values

    #RSI INDICATOR
    serie = data.copy()
    serie["change"]=serie["Close"].diff()
    serie["changeup"] = np.where(serie["change"]>0,serie["change"],0)
    serie["changedown"] = np.where(serie["change"]<0,serie["change"],0)
    avg_up = serie["changeup"].rolling(rsi).mean()
    avg_down = serie["changedown"].rolling(rsi).mean().abs()
    data["rsi"] = round(((100 * avg_up) / (avg_up + avg_down)),2)

    

    #CONDITIONS
    data["cond_signal_long"]=False#np.where((data["Slope"]>0)&(data["rsi"]<30),True,False)  
    data["cond_signal_short"]=np.where((data["Slope"]<0)&(data["rsi"]>70),True,False) 

    data = data.dropna().reset_index(drop=True)
    data["position"]=0
    data["position_enter_price"]=0.0
    data["position_enter_price"] = data["position_enter_price"].astype(float)
    data["unrealized_PL"]=0.0
    data["unrealized_PL"] = data["unrealized_PL"].astype(float)
    data["unrealized_PL_per"]=0.0


    for i in range(data.shape[0]):
      if i == 0:
        data.loc[i,"position"] = 0
        continue

      #si estamos fuera
      if data.loc[ i-1,"position"] == 0:
        #Evalue si hay que entrar en la posicion
        if (data.loc[ i,"cond_signal_long"] == True):
          data.loc[i,"position"] = 1
          data.loc[i,"position_enter_price"] = data.loc[i,"Close"]
        elif (data.loc[ i,"cond_signal_short"] == True):
          data.loc[i,"position"] = -1
          data.loc[i,"position_enter_price"] = data.loc[i,"Close"]
        else:
          continue
      #Si estamos dentro
      else:
        enter_price = data.loc[i-1,"position_enter_price"]
        close_price = data.loc[i,"Close"]
        data.loc[i,"position_enter_price"] = enter_price

        
        if (data.loc[i-1,"position"] == -1):
          
          data.loc[i,"unrealized_PL"] = -close_price+enter_price
          data.loc[i,"unrealized_PL_per"] = round((100*(-close_price+enter_price)/enter_price),2)

          #Evalue si hay que salir o mantener la posicion
          if (data.loc[ i,"Close"] < data.loc[ i-1,"Low"]):
            data.loc[i,"position"] = 0
          else:
            data.loc[i,"position"] = -1


    previous_row=(data.iloc[-2,:]).to_dict()
    current_row=(data.iloc[-1,:]).to_dict()

    data_to_show=data[["Date","Close","Low","High","cond_signal_short","position", "unrealized_PL", "unrealized_PL_per"]].tail(15)
    print(data_to_show)
    print('------->')

    print('Position to take:',current_row["position"])

    return [current_row["position"],current_row["Close"],current_row["unrealized_PL_per"],data]


def buy_weakness_x(data, params):

  MACD_inputs = params[0]
  weak_in = params[1]

  
  data = data.copy()
  print(f"----- BuyWeaknessMACDXXX MACD_inputs{MACD_inputs}__weakin{weak_in} - MeanRev ----")


  #DEMA5
  data["EMA5"]=data.Close.ewm(span=5).mean()
  data['DEMA_EMA5'] = data.EMA5.ewm(span=5).mean()
  data['DEMA5'] = 2 * data['EMA5'] - data['DEMA_EMA5']

  #EMA50
  data["EMA50"]=data.Close.ewm(span=50).mean()


  #MACDs
  fast_period = MACD_inputs[0]
  slow_period = MACD_inputs[1]
  signal_period = MACD_inputs[2]
  macd = MACD(data['Close'], fast_period, slow_period, signal_period)
  data['macd_line'] = macd[0]
  data['signal_line'] = macd[1]
  data['macd_histogram'] = macd[2]

  window_size=3
  slopes = []
  for i in range(window_size-1, len(data)):
      x = np.arange(i-window_size+1, i+1)
      y = data["macd_line"].values[i-window_size+1:i+1]
      slope, _ = np.polyfit(x, y, 1)
      slopes.append(slope)

  data['macd_slope'] = np.nan
  data.loc[window_size-1:, 'macd_slope'] = slopes

  slopes = []
  for i in range(window_size-1, len(data)):
      x = np.arange(i-window_size+1, i+1)
      y = data["macd_histogram"].values[i-window_size+1:i+1]
      slope, _ = np.polyfit(x, y, 1)
      slopes.append(slope)

  data['hist_slope'] = np.nan
  data.loc[window_size-1:, 'hist_slope'] = slopes


  #SUPERTREND
  supert = supertrend(data, lookback=fast_period, multiplier=2)
  data["supertrend"]=supert["supertrend"]
  

  #RSI
  rsi_serie=RSI(data, window=14)
  data["rsi"]=rsi_serie

  data["cond_ema50"]=np.where(data["DEMA5"]>data["EMA50"],1,-1)
  data["cond_macdline"]=np.where(data["macd_line"]>0,1,-1)
  data["cond_macdgap"]=np.where(data["macd_line"]>data["signal_line"],1,-1)
  data["cond_macdslope"]=np.where(data["macd_slope"]>0,1,-1)
  data["cond_macdsbarras"]=np.where(data["hist_slope"]>0,1,-1)
  data["cond_supert"]=np.where(data["Close"]>data["supertrend"],1,-1)
  data["cond_rsi"]=np.where(data["rsi"]>75,2,0)
  data["cond_rsi"]=np.where((data["rsi"]>65)&(data["rsi"]<75),1,data["cond_rsi"])
  data["cond_rsi"]=np.where((data["rsi"]<35)&(data["rsi"]>25),-1,data["cond_rsi"])
  data["cond_rsi"]=np.where(data["rsi"]<25,-2,data["cond_rsi"])

  data["sum"]=(data["cond_ema50"]
               +data["cond_macdline"]+
                  data["cond_macdgap"]+data["cond_macdslope"]+data["cond_macdsbarras"]+
                  data["cond_supert"]+
                  data["cond_rsi"])
  

  data = data.dropna().reset_index(drop=True)
  data["position"]=0
  data["position_enter_price"]=0.0
  data["position_enter_price"] = data["position_enter_price"].astype(float)
  data["unrealized_PL"]=0.0
  data["unrealized_PL"] = data["unrealized_PL"].astype(float)
  data["unrealized_PL_per"]=0.0


  for i in range(data.shape[0]):
    if i == 0:
      data.loc[i,"position"] = 0
      continue
    #si estamos fuera
    if data.loc[ i-1,"position"]== 0:
      #Evalue si hay que entrar en la posicion
      if (data.loc[ i,"sum"] <= weak_in)&(data.loc[ i-1,"sum"]> data.loc[ i,"sum"]):
        data.loc[i,"position"] = 1
        data.loc[i,"position_enter_price"] = data.loc[i,"Close"]
      else:
        continue
    #Si estamos dentro
    else:
      enter_price = data.loc[i-1,"position_enter_price"]
      close_price = data.loc[i,"Close"]
      data.loc[i,"position_enter_price"] = enter_price
      data.loc[i,"unrealized_PL"] = close_price-enter_price
      data.loc[i,"unrealized_PL_per"] = round((100*(close_price-enter_price)/enter_price),2)
      #Evalue si hay que salir o mantener la posicion
      if (data.loc[ i,"Close"] > data.loc[ i-1,"High"]):
        data.loc[i,"position"] = 0
      else:
        data.loc[i,"position"] = 1


  previous_row=(data.iloc[-2,:]).to_dict()
  current_row=(data.iloc[-1,:]).to_dict()

  data_to_show=data[["Date","Close","Low","High","sum","position","unrealized_PL"]].tail(30)
  print(data_to_show)
  print('------->')

  print('Position to take:',current_row["position"])

  return [current_row["position"],current_row["Close"],current_row["unrealized_PL_per"],data]



#MOMENTUM STRATEGIES
def macd_hist(data, params):
      
    MACD_inputs = params[0]
    fast_period = MACD_inputs[0]
    slow_period = MACD_inputs[1]
    signal_period = MACD_inputs[2]
    
    enter_day = params[1]

    index_of_strategy = f"{MACD_inputs}_{enter_day}"
    
    print(f"-----SEC MacdHist MACD{MACD_inputs}_enter_day{enter_day} - Momentum ----")


    #MACD INDICATOR
    data = data.copy()
    ema_fast = data['Close'].ewm(span=fast_period, adjust=False).mean()
    ema_slow = data['Close'].ewm(span=slow_period, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
    data['macd_histogram'] = macd_line - signal_line

    data["green_days"]=0

    data = data.dropna().reset_index(drop=True)
    data["position"]=0
    data["position_enter_price"]=0.0
    data["position_enter_price"] = data["position_enter_price"].astype(float)
    data["unrealized_PL"]=0.0
    data["unrealized_PL"] = data["unrealized_PL"].astype(float)
    data["unrealized_PL_per"]=0.0

    for i in range(data.shape[0]):
        if data.loc[i,"macd_histogram"] > 0:
            data.loc[i,"green_days"] = data.loc[i-1,"green_days"] +1
        else:
            data.loc[i,"green_days"] = 0

    data["cond_signal_long"]=np.where((data["green_days"] == enter_day),True,False)

    for i in range(data.shape[0]):
        if i == 0:
          data.loc[i,"position"] = 0
          continue
        #si estamos fuera
        if data.loc[i-1,"position"] == 0:
          #Evalue si hay que entrar en la posicion
          if data.loc[i,"cond_signal_long"] == True:
            data.loc[i,"position"] = 1
            data.loc[i,"position_enter_price"] = data.loc[i,"Close"]
          else:
            continue
        
        #Si estamos dentro
        else:
          enter_price = data.loc[i-1,"position_enter_price"]
          close_price = data.loc[i,"Close"]
          data.loc[i,"position_enter_price"] = enter_price
          data.loc[i,"unrealized_PL"] = close_price-enter_price
          data.loc[i,"unrealized_PL_per"] = round((100*(close_price-enter_price)/enter_price),2)
          #Evalue si hay que salir o mantener la posicion
          if (data.loc[i,"Close"] >  data.loc[i-1,"Close"])&(data.loc[i,"Close"] >  data.loc[i-1,"Open"]):
            data.loc[i,"position"] = 0
        
          else:
            data.loc[i,"position"] = 1
    
    previous_row=(data.iloc[-2,:]).to_dict()
    current_row=(data.iloc[-1,:]).to_dict()

    data_to_show=data[["Date","Close","macd_histogram","position","cond_signal_long","unrealized_PL"]].tail(15)
    print(data_to_show)
    print('------->')

    print('Position to take:',current_row["position"])

    return [current_row["position"],current_row["Close"],current_row["unrealized_PL_per"],data]


def zscore_bull(data,params):
    
    data = data.copy()

    zscore_period = params[0]
    z_in = params[1]
    ema = params[3]
    days_in = params[2]
    
    #index_of_strategy = f"{kvo}_{ema}"
    
    
    print(f"----- ZScore{zscore_period} z_in{z_in} ema{ema} days_in{days_in}- TrendFollowing ----")



    #ZSCORE CALCULATION

    data["ma"] = data["Close"].rolling(window=zscore_period).mean()
    data["stdev"] = data["Close"].rolling(window=zscore_period).std()
    data['zscore'] = (data['Close'] - data["ma"]) / (data["stdev"])

    # DEMA CLOSE
    data["EMA_0"]=data.Close.ewm(span=5).mean()
    data["EMA"]=data.Close.ewm(span=ema).mean()

    

    #CONDITIONS
    data["bullish"]=np.where(data["EMA_0"]>data["EMA"],True,False)
    data["cond_out"]=np.where(((((data["zscore"]<2) & (data["zscore"].shift()>2))|
                                ((data["zscore"]<1) & (data["zscore"].shift()>1)))),True,False)
    data["cond_signal_long"]=np.where((data["zscore"]>z_in)&(data["zscore"].shift()<z_in)&data["bullish"],True,False)
    data["cond_signal_short"]=False

    data = data.dropna().reset_index(drop=True)
    data["position"]=0
    data["position_enter_price"]=0.0
    data["position_enter_price"] = data["position_enter_price"].astype(float)
    data["unrealized_PL"]=0.0
    data["unrealized_PL"] = data["unrealized_PL"].astype(float)
    data["days_in_trade"]=0
    data["unrealized_PL_per"]=0.0

    days_in_trade=0

    for i in range(data.shape[0]):
      if i == 0:
        data.loc[i,"position"] = 0
        continue

      #si estamos fuera
      if data.loc[ i-1,"position"] == 0:
        #Evalue si hay que entrar en la posicion
        if (data.loc[ i,"cond_signal_long"] == True):
          data.loc[i,"position"] = 1
          data.loc[i,"position_enter_price"] = data.loc[i,"Close"]
        elif (data.loc[ i,"cond_signal_short"] == True):
          pass
        else:
          continue
      #Si estamos dentro
      else:
        enter_price = data.loc[i-1,"position_enter_price"]
        close_price = data.loc[i,"Close"]
        data.loc[i,"position_enter_price"] = enter_price
        days_in_trade+=1

        if (data.loc[i-1,"position"] == 1):

          data.loc[i,"unrealized_PL"] = close_price-enter_price
          data.loc[i,"unrealized_PL_per"] = round((100*(close_price-enter_price)/enter_price),2)
          
          #Evalue si hay que salir o mantener la posicion
          if (data.loc[ i,"cond_out"] == True)|(data.loc[i,"bullish"] == False)|(days_in_trade==days_in):
            data.loc[i,"position"] = 0
            days_in_trade = 0
          else:
            data.loc[i,"position"] = 1
            data.loc[i,"days_in_trade"] = days_in_trade
        


    previous_row=(data.iloc[-2,:]).to_dict()
    current_row=(data.iloc[-1,:]).to_dict()

    data_to_show=data[["Date","Close","Low","High","cond_signal_long","position", "unrealized_PL", "unrealized_PL_per"]].tail(20)
    print(data_to_show)
    print('------->')

    print('Position to take:',current_row["position"])

    return [current_row["position"],current_row["Close"],current_row["unrealized_PL_per"], data]


def kvo_dema(data,params):
    
    data = data.copy()

    kvo = params[0]
    demaKVO = params[1]
    
    #index_of_strategy = f"{kvo}_{ema}"
    
    print(f"----- KVO{kvo}_KVODEMA{demaKVO} - TrendFollowing ----")
   


    #KVO INDICATOR
    fastT = kvo[0]
    slowT = kvo[1]
    data['hlc3'] = (data['High'] + data['Low'] + data['Close']) / 3
    data['KVOTrend'] = np.where(data['hlc3'] > data['hlc3'].shift(1), data['Volume'] * 100, -data['Volume'] * 100)

    data['KVOFast'] = data['KVOTrend'].ewm(span=fastT, adjust=False).mean()
    data['KVOSlow'] = data['KVOTrend'].ewm(span=slowT, adjust=False).mean()

    data['KVO'] = data['KVOFast'] - data['KVOSlow']

    #Doble exp Moving Average sec strtegy
    data["EMA"]=data.KVO.ewm(span=demaKVO).mean()
    data['DEMA_EMA'] = data.EMA.ewm(span=demaKVO).mean()
    data['dema'] = 2 * data['EMA'] - data['DEMA_EMA']

  

    #CONDITIONS
    data["cond_signal_long"]=np.where((data["dema"]>0)&(data["dema"]<0),True,False)
    data["cond_signal_short"]=False

    data = data.dropna().reset_index(drop=True)
    data["position"]=0
    data["position_enter_price"]=0.0
    data["position_enter_price"] = data["position_enter_price"].astype(float)
    data["unrealized_PL"]=0
    data["unrealized_PL_per"]=0


    for i in range(data.shape[0]):
      if i == 0:
        data.loc[i,"position"] = 0
        continue

      #si estamos fuera
      if data.loc[ i-1,"position"] == 0:
        #Evalue si hay que entrar en la posicion
        if (data.loc[ i,"cond_signal_long"] == True):
          data.loc[i,"position"] = 1
          data.loc[i,"position_enter_price"] = data.loc[i,"Close"]
        elif (data.loc[ i,"cond_signal_short"] == True):
          pass
        else:
          continue
      #Si estamos dentro
      else:
        enter_price = data.loc[i-1,"position_enter_price"]
        close_price = data.loc[i,"Close"]
        data.loc[i,"position_enter_price"] = enter_price

        if (data.loc[i-1,"position"] == 1):

          data.loc[i,"unrealized_PL"] = close_price-enter_price
          data.loc[i,"unrealized_PL_per"] = round((100*(close_price-enter_price)/enter_price),2)
          
          #Evalue si hay que salir o mantener la posicion
          if (data.loc[ i,"Close"] > data.loc[ i-1,"High"]):
            data.loc[i,"position"] = 0
          else:
            data.loc[i,"position"] = 1
        
        elif (data.loc[i-1,"position"] == -1):
          
          pass


    previous_row=(data.iloc[-2,:]).to_dict()
    current_row=(data.iloc[-1,:]).to_dict()

    data_to_show=data[["Date","Close","Low","High","cond_signal_long","position", "unrealized_PL", "unrealized_PL_per"]].tail(20)
    print(data_to_show)
    print('------->')

    print('Position to take:',current_row["position"])

    return [current_row["position"],current_row["Close"],current_row["unrealized_PL_per"], data]


def rsi_stremgth(data,params):
    
    data = data.copy()

    rsi_period=params[0]
    r_in=params[1]
    ema=params[2]

    
    #index_of_strategy = f"{kvo}_{ema}"
    
    print(f"-----RSI STRENGHT rsi_period{rsi_period}__r_in{r_in}__emabull{ema} - TrendFollowing ----")
   

    #RSI INDICATOR
    serie = data.copy()
    serie["change"]=serie["Close"].diff()
    serie["changeup"] = np.where(serie["change"]>0,serie["change"],0)
    serie["changedown"] = np.where(serie["change"]<0,serie["change"],0)
    avg_up = serie["changeup"].rolling(rsi_period).mean()
    avg_down = serie["changedown"].rolling(rsi_period).mean().abs()
    data["rsi"] = round(((100 * avg_up) / (avg_up + avg_down)),2)
    
    #EMAS
    data["ema"]=data.Close.ewm(span=ema, min_periods=ema).mean()

  

    #CONDITIONS
    data["cond_signal_long"]=np.where((data["Close"]>data["ema"])&
                                      (data["rsi"]>r_in)&(data["rsi"].shift()<r_in),True,False)
    data["cond_signal_short"]=False

    data = data.dropna().reset_index(drop=True)
    data["position"]=0
    data["position_enter_price"]=0.0
    data["position_enter_price"] = data["position_enter_price"].astype(float)
    data["unrealized_PL"]=0.0
    data["unrealized_PL"] = data["unrealized_PL"].astype(float)
    data["unrealized_PL_per"]=0.0


    for i in range(data.shape[0]):
      if i == 0:
        data.loc[i,"position"] = 0
        continue

      #si estamos fuera
      if data.loc[ i-1,"position"] == 0:
        #Evalue si hay que entrar en la posicion
        if (data.loc[ i,"cond_signal_long"] == True):
          data.loc[i,"position"] = 1
          data.loc[i,"position_enter_price"] = data.loc[i,"Close"]
        elif (data.loc[ i,"cond_signal_short"] == True):
          pass
        else:
          continue
      #Si estamos dentro
      else:
        enter_price = data.loc[i-1,"position_enter_price"]
        close_price = data.loc[i,"Close"]
        data.loc[i,"position_enter_price"] = enter_price

        if (data.loc[i-1,"position"] == 1):

          data.loc[i,"unrealized_PL"] = close_price-enter_price
          data.loc[i,"unrealized_PL_per"] = round((100*(close_price-enter_price)/enter_price),2)
          
          #Evalue si hay que salir o mantener la posicion
          if (data.loc[ i,"Close"] > data.loc[ i-1,"High"]):
            data.loc[i,"position"] = 0
          else:
            data.loc[i,"position"] = 1
        
        elif (data.loc[i-1,"position"] == -1):
          
          pass


    previous_row=(data.iloc[-2,:]).to_dict()
    current_row=(data.iloc[-1,:]).to_dict()

    data_to_show=data[["Date","Close","Low","High","cond_signal_long","position", "unrealized_PL", "unrealized_PL_per"]].tail(20)
    print(data_to_show)
    print('------->')

    print('Position to take:',current_row["position"])

    return [current_row["position"],current_row["Close"],current_row["unrealized_PL_per"],data]


def zs_pull(data,params):
    
    data = data.copy()

    zscore_period = params[0]
    z_lvl = params[1]

    data['zscore'] = zscore(data,zscore_period)

    #CONDITIONS
    data["cond_signal_long"]=np.where((data["zscore"]>z_lvl)&(data["zscore"].shift()<z_lvl), True, False)
    data["cond_signal_short"]=False

    data["cond_out_long"]=np.where((data["cond_signal_long"]!=True)|
                                   ((data["cond_signal_long"]!=True)&(data["Close"]>data["High"].shift())), True, False)
    data["cond_out_short"]=False


    data = data.dropna().reset_index(drop=True)
    data["position"]=0
    data["position_enter_price"]=0
    data["position_enter_price"] = data["position_enter_price"].astype(float)
    data["unrealized_PL"]=0
    data["unrealized_PL"] = data["unrealized_PL"].astype(float)
    data["unrealized_PL_per"]=0
    data["unrealized_PL_per"] = data["unrealized_PL_per"].astype(float)
    data["out_by_sp"]=0
    data["out_by_ema"]=0
    data["t"]=0


    t=1
    for i in range(data.shape[0]):
      if i == 0:
        data.loc[i,"position"] = 0
        continue

      #si estamos fuera
      if data.loc[ i-1,"position"] == 0:
        if t >0:
          t+=1
        data.loc[i,"t"]=t

        #Evalue si hay que entrar en la posicion
        if (data.loc[ i,"cond_signal_long"] == True)&(t>16):#16
          data.loc[i,"position"] = 1
          data.loc[i,"position_enter_price"] = data.loc[i,"Close"]
        elif (data.loc[ i,"cond_signal_short"] == True):
          pass
        else:
          continue
      #Si estamos dentro
      else:
        enter_price = data.loc[i-1,"position_enter_price"]
        close_price = data.loc[i,"Close"]
        data.loc[i,"position_enter_price"] = enter_price

        if (data.loc[i-1,"position"] == 1):

          data.loc[i,"unrealized_PL"] = close_price-enter_price
          data.loc[i,"unrealized_PL_per"] = round((100*(close_price-enter_price)/enter_price),2)
          
          #Evalue si hay que salir o mantener la posicion
        if (data.loc[i,"cond_out_long"]):
            data.loc[i,"position"] = 0
        else:
            data.loc[i,"position"] = 1
        

    current_row=(data.iloc[-1,:]).to_dict()

    data_to_show=data[["Date","Close","Low","High","cond_signal_long","position", "unrealized_PL", "unrealized_PL_per"]].tail(20)
    print(data_to_show)
    print('------->')

    print('Position to take:',current_row["position"])

    return [current_row["position"],current_row["Close"],current_row["unrealized_PL_per"],data]
  


#TREND STRATEGIES

def golden_cross(data,params):
    
    data = data.copy()

    ema1 =params[0]
    ema2 =params[1]
    
    #index_of_strategy = f"{kvo}_{ema}"
    
   
    print(f"----- ema1{ema1}ema2{ema2} - TrendFollowing ----")



    #EMAS
    data["ema1"]=data.Close.ewm(span=ema1, min_periods=ema1).mean()
    data["ema2"]=data.Close.ewm(span=ema2, min_periods=ema2).mean()

    
    #SUPERTREND
    supert = supertrend(data, lookback=28, multiplier=3.5)
    data["supertrend"]=supert["supertrend"]
    data["sup_bul_bear"]=np.where(data["supertrend"]>data["Close"],-1,1)
    data["sp_change"]=np.where(data["sup_bul_bear"]!=data["sup_bul_bear"].shift(),1,0)

    #CONDITIONS
  
    data["cond_signal_long"]=np.where(data["ema1"] > data["ema2"],True,False)
    data["cond_signal_short"]=False

    data = data.dropna().reset_index(drop=True)
    data["position"]=0
    data["position_enter_price"]=0.0
    data["position_enter_price"] = data["position_enter_price"].astype(float)
    data["unrealized_PL"]=0.0
    data["unrealized_PL"] = data["unrealized_PL"].astype(float)
    data["unrealized_PL_per"]=0.0
    data["out_by_sp"]=0
    data["out_by_ema"]=0
    data["t"]=0


    t=1
    for i in range(data.shape[0]):
      if i == 0:
        data.loc[i,"position"] = 0
        continue

      #si estamos fuera
      if data.loc[ i-1,"position"] == 0:
        if t >0:
          t+=1
        data.loc[i,"t"]=t

        #Evalue si hay que entrar en la posicion
        if (data.loc[ i,"cond_signal_long"] == True)&(t>16):#16
          t=1
          data.loc[i,"position"] = 1
          data.loc[i,"position_enter_price"] = data.loc[i,"Close"]
        elif (data.loc[ i,"cond_signal_short"] == True):
          pass
        else:
          continue
      #Si estamos dentro
      else:
        enter_price = data.loc[i-1,"position_enter_price"]
        close_price = data.loc[i,"Close"]
        data.loc[i,"position_enter_price"] = enter_price

        if (data.loc[i-1,"position"] == 1):

          data.loc[i,"unrealized_PL"] = close_price-enter_price
          data.loc[i,"unrealized_PL_per"] = round((100*(close_price-enter_price)/enter_price),2)
          
          #Evalue si hay que salir o mantener la posicion
          if (data.loc[i,"ema1"] < data.loc[i,"ema2"]):
            data.loc[i,"position"] = 0
            data.loc[i,"out_by_ema"] = 1
          else:
            if (data.loc[ i,"Close"] < data.loc[i,"supertrend"])&(data.loc[i,"sp_change"]==1):
                data.loc[i,"position"] = 0
                data.loc[i,"out_by_sp"] = 1
                t=1

            else:
              data.loc[i,"position"] = 1
        
        elif (data.loc[i-1,"position"] == -1):
          
          pass


    previous_row=(data.iloc[-2,:]).to_dict()
    current_row=(data.iloc[-1,:]).to_dict()

    data_to_show=data[["Date","Close","Low","High","ema2","cond_signal_long","position", "unrealized_PL", "unrealized_PL_per"]].tail(20)
    print(data_to_show)
    print('------->')

    print('Position to take:',current_row["position"])

    return [current_row["position"],current_row["Close"],current_row["unrealized_PL_per"],data]
   

def kvo_bull(data,params):
    
    data = data.copy()

    kvo = params[0]
    ema = params[1]
    
    #index_of_strategy = f"{kvo}_{ema}"
    

    print(f"----- KVO{kvo}_EMA{ema} - TrendFollowing ----")


   

    #KVO INDICATOR
    fastT = kvo[0]
    slowT = kvo[1]
    data['hlc3'] = (data['High'] + data['Low'] + data['Close']) / 3
    data['KVOTrend'] = np.where(data['hlc3'] > data['hlc3'].shift(1), data['Volume'] * 100, -data['Volume'] * 100)

    data['KVOFast'] = data['KVOTrend'].ewm(span=fastT, adjust=False).mean()
    data['KVOSlow'] = data['KVOTrend'].ewm(span=slowT, adjust=False).mean()

    data['KVO'] = data['KVOFast'] - data['KVOSlow']

   
    # DEMA CLOSE
    data["EMA_0"]=data.Close.ewm(span=5).mean()
    data["EMA"]=data.Close.ewm(span=ema).mean()

    

    #CONDITIONS
    bullish_cond = data["EMA_0"]>data["EMA"]
    data["cond_signal_long"]=np.where((data["KVO"]>0)&(data["KVO"]<0).shift()&bullish_cond,True,False)
    data["cond_signal_short"]=False

    data = data.dropna().reset_index(drop=True)
    data["position"]=0
    data["position_enter_price"]=0.0
    data["position_enter_price"] = data["position_enter_price"].astype(float)
    data["unrealized_PL"]=0.0
    data["unrealized_PL"] = data["unrealized_PL"].astype(float)
    data["unrealized_PL_per"]=0.0

    for i in range(data.shape[0]):
      if i == 0:
        data.loc[i,"position"] = 0
        continue

      #si estamos fuera
      if data.loc[ i-1,"position"] == 0:
        #Evalue si hay que entrar en la posicion
        if (data.loc[ i,"cond_signal_long"] == True):
          data.loc[i,"position"] = 1
          data.loc[i,"position_enter_price"] = data.loc[i,"Close"]
        elif (data.loc[ i,"cond_signal_short"] == True):
          pass
        else:
          continue
      #Si estamos dentro
      else:
        enter_price = data.loc[i-1,"position_enter_price"]
        close_price = data.loc[i,"Close"]
        data.loc[i,"position_enter_price"] = enter_price

        if (data.loc[i-1,"position"] == 1):

          data.loc[i,"unrealized_PL"] = close_price-enter_price
          data.loc[i,"unrealized_PL_per"] = round((100*(close_price-enter_price)/enter_price),2)
          
          #Evalue si hay que salir o mantener la posicion
          if (data.loc[ i,"Close"] > data.loc[ i-1,"High"])&(data.loc[i,"EMA_0"]<data.loc[i,"EMA"]):
            data.loc[i,"position"] = 0
          else:
            data.loc[i,"position"] = 1
        
        elif (data.loc[i-1,"position"] == -1):
          
          pass


    previous_row=(data.iloc[-2,:]).to_dict()
    current_row=(data.iloc[-1,:]).to_dict()

    data_to_show=data[["Date","Close","Low","High","cond_signal_long","position", "unrealized_PL", "unrealized_PL_per"]].tail(20)
    print(data_to_show)
    print('------->')

    print('Position to take:',current_row["position"])

    return [current_row["position"],current_row["Close"],current_row["unrealized_PL_per"],data]


def kvo_bull_spt(data,params):
    
    data = data.copy()

    kvo = params[0]
    ema = params[1]
    
    #index_of_strategy = f"{kvo}_{ema}"
    

    print(f"----- KVO{kvo}_EMA{ema}_supertrend28-3.5_t12 - TrendFollowing ----")
   

    #KVO INDICATOR
    fastT = kvo[0]
    slowT = kvo[1]
    data['hlc3'] = (data['High'] + data['Low'] + data['Close']) / 3
    data['KVOTrend'] = np.where(data['hlc3'] > data['hlc3'].shift(1), data['Volume'] * 100, -data['Volume'] * 100)

    data['KVOFast'] = data['KVOTrend'].ewm(span=fastT, adjust=False).mean()
    data['KVOSlow'] = data['KVOTrend'].ewm(span=slowT, adjust=False).mean()

    data['KVO'] = data['KVOFast'] - data['KVOSlow']

   
    # EMA CLOSE
    data["EMA_0"]=data.Close.ewm(span=5).mean()
    data["EMA"]=data.Close.ewm(span=ema).mean()

    #SUPERTREND
    supert = supertrend(data, lookback=28, multiplier=3.5)
    data["supertrend"]=supert["supertrend"]
    data["sup_bul_bear"]=np.where(data["supertrend"]>data["Close"],-1,1)
    data["sp_change"]=np.where(data["sup_bul_bear"]!=data["sup_bul_bear"].shift(),1,0)


    #CONDITIONS
    bullish_cond = data["EMA_0"]>data["EMA"]
    #supertrend_bull = data["Close"]>data["supertrend"]
    data["cond_signal_long"]=np.where((data["KVO"]>0)&(data["KVO"]<0).shift()&bullish_cond,True,False)
    data["cond_signal_short"]=False

    data = data.dropna().reset_index(drop=True)
    data["position"]=0
    data["position_enter_price"]=0.0
    data["position_enter_price"] = data["position_enter_price"].astype(float)
    data["unrealized_PL"]=0.0
    data["unrealized_PL"] = data["unrealized_PL"].astype(float)
    data["unrealized_PL_per"]=0.0
    data["out_by_sp"]=0
    data["out_by_ema"]=0
    data["t"]=0

    t=1
    for i in range(data.shape[0]):
      if i == 0:
        data.loc[i,"position"] = 0
        continue

      #si estamos fuera
      if data.loc[ i-1,"position"] == 0:
        if t >0:
          t+=1
        data.loc[i,"t"]=t
        #Evalue si hay que entrar en la posicion
        if (data.loc[ i,"cond_signal_long"] == True)&(t>12):
          t=1
          data.loc[i,"position"] = 1
          data.loc[i,"position_enter_price"] = data.loc[i,"Close"]


        elif (data.loc[ i,"cond_signal_short"] == True):
          pass
        else:
          continue
      #Si estamos dentro
      else:
        enter_price = data.loc[i-1,"position_enter_price"]
        close_price = data.loc[i,"Close"]
        data.loc[i,"position_enter_price"] = enter_price

        if (data.loc[i-1,"position"] == 1):

          data.loc[i,"unrealized_PL"] = close_price-enter_price
          data.loc[i,"unrealized_PL_per"] = round((100*(close_price-enter_price)/enter_price),2)
          
          #Evalue si hay que salir o mantener la posicion
          if (data.loc[ i,"Close"] > data.loc[ i-1,"High"])&(data.loc[i,"EMA_0"]<data.loc[i,"EMA"]):
            data.loc[i,"position"] = 0
            data.loc[i,"out_by_ema"] = 1
          else:
            if (data.loc[ i,"Close"] < data.loc[i,"supertrend"])&(data.loc[i,"sp_change"]==1):
                data.loc[i,"position"] = 0
                data.loc[i,"out_by_sp"] = 1
                t=1

            else:
              data.loc[i,"position"] = 1
        
        elif (data.loc[i-1,"position"] == -1):
          pass


    previous_row=(data.iloc[-2,:]).to_dict()
    current_row=(data.iloc[-1,:]).to_dict()

    data_to_show=data[["Date","Close","Low","High","cond_signal_long","position", "unrealized_PL", "unrealized_PL_per"]].tail(20)
    print(data_to_show)
    print('------->')

    print('Position to take:',current_row["position"])

    return [current_row["position"],current_row["Close"],current_row["unrealized_PL_per"],data]


def macd_slope(data,params):
    
    data = data.copy()

    MACD_inputs =params[0]
    ema =params[1]
    
    #index_of_strategy = f"{kvo}_{ema}"
    

    print(f"----- MACD_inputs{MACD_inputs} - ema{ema} - TrendFollowing ----")


    #MACD
    data = data.copy()
    fast_period = MACD_inputs[0]
    slow_period = MACD_inputs[1]
    signal_period = MACD_inputs[2]
    #MACD INDICATOR
    data = data.copy()
    ema_fast = data['Close'].ewm(span=fast_period, adjust=False).mean()
    ema_slow = data['Close'].ewm(span=slow_period, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
    data['macd_histogram'] = macd_line - signal_line
    data['macd_line'] = macd_line
    data['signal_line'] = signal_line

    # DEMA CLOSE
  
    data["EMA_0"]=data.Close.ewm(span=5).mean()
    data["EMA"]=data.Close.ewm(span=ema).mean()

    #CONDITIONS
    data["bullish"]=np.where(data["EMA_0"]>data["EMA"],True,False)
    data["cond_signal_long"]=np.where((data["macd_line"]>0)&(data["macd_line"].shift()<0)&data["bullish"],True,False)
    data["cond_signal_short"]=False

    data = data.dropna().reset_index(drop=True)
    data["position"]=0
    data["position_enter_price"]=0.0
    data["position_enter_price"] = data["position_enter_price"].astype(float)
    data["unrealized_PL"]=0.0
    data["unrealized_PL"] = data["unrealized_PL"].astype(float)
    data["unrealized_PL_per"]=0.0


    for i in range(data.shape[0]):
      if i == 0:
        data.loc[i,"position"] = 0
        continue

      #si estamos fuera
      if data.loc[ i-1,"position"] == 0:
        #Evalue si hay que entrar en la posicion
        if (data.loc[ i,"cond_signal_long"] == True):
          data.loc[i,"position"] = 1
          data.loc[i,"position_enter_price"] = data.loc[i,"Close"]
        elif (data.loc[ i,"cond_signal_short"] == True):
          pass
        else:
          continue
      #Si estamos dentro
      else:
        enter_price = data.loc[i-1,"position_enter_price"]
        close_price = data.loc[i,"Close"]
        data.loc[i,"position_enter_price"] = enter_price

        if (data.loc[i-1,"position"] == 1):

          data.loc[i,"unrealized_PL"] = close_price-enter_price
          data.loc[i,"unrealized_PL_per"] = round((100*(close_price-enter_price)/enter_price),2)
          
          #Evalue si hay que salir o mantener la posicion
          if (data.loc[i,"macd_line"] < 0)|(data.loc[i,"bullish"]==False):
            data.loc[i,"position"] = 0
          else:
            data.loc[i,"position"] = 1
        
        elif (data.loc[i-1,"position"] == -1):
          
          pass


    previous_row=(data.iloc[-2,:]).to_dict()
    current_row=(data.iloc[-1,:]).to_dict()

    data_to_show=data[["Date","Close","Low","High","cond_signal_long","position", "unrealized_PL", "unrealized_PL_per"]].tail(20)
    print(data_to_show)
    print('------->')

    print('Position to take:',current_row["position"])

    return [current_row["position"],current_row["Close"],current_row["unrealized_PL_per"],data]
   

def macd_slope_spt(data,params):
    
    data = data.copy()

    MACD_inputs =params[0]
    ema =params[1]
    
    #index_of_strategy = f"{kvo}_{ema}"
    

    print(f"----- MACD_inputs{MACD_inputs} - ema{ema} - TrendFollowing ----")


    #MACD
    data = data.copy()
    fast_period = MACD_inputs[0]
    slow_period = MACD_inputs[1]
    signal_period = MACD_inputs[2]
    #MACD INDICATOR
    data = data.copy()
    ema_fast = data['Close'].ewm(span=fast_period, adjust=False).mean()
    ema_slow = data['Close'].ewm(span=slow_period, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
    data['macd_histogram'] = macd_line - signal_line
    data['macd_line'] = macd_line
    data['signal_line'] = signal_line

    # DEMA CLOSE
  
    data["EMA_0"]=data.Close.ewm(span=5).mean()
    data["EMA"]=data.Close.ewm(span=ema).mean()


    #SUPERTREND
    supert = supertrend(data, lookback=28, multiplier=4)
    data["supertrend"]=supert["supertrend"]
    data["sup_bul_bear"]=np.where(data["supertrend"]>data["Close"],-1,1)
    data["sp_change"]=np.where(data["sup_bul_bear"]!=data["sup_bul_bear"].shift(),1,0)

    #CONDITIONS
    data["bullish"]=np.where(data["EMA_0"]>data["EMA"],True,False)
    data["cond_signal_long"]=np.where((data["macd_line"]>0)&(data["macd_line"].shift()<0)&data["bullish"],True,False)
    data["cond_signal_short"]=False

    data = data.dropna().reset_index(drop=True)
    data["position"]=0
    data["position_enter_price"]=0.0
    data["position_enter_price"] = data["position_enter_price"].astype(float)
    data["unrealized_PL"]=0.0
    data["unrealized_PL"] = data["unrealized_PL"].astype(float)
    data["unrealized_PL_per"]=0.0
    data["out_by_sp"]=0
    data["out_by_st"]=0
    data["t"]=0

    t=1
    for i in range(data.shape[0]):
      if i == 0:
        data.loc[i,"position"] = 0
        continue

      #si estamos fuera
      if data.loc[ i-1,"position"] == 0:
        #Evalue si hay que entrar en la posicion
        if t >0:
          t+=1
        data.loc[i,"t"]=t
        #Evalue si hay que entrar en la posicion
        if (data.loc[ i,"cond_signal_long"] == True)&(t>21):#21
          t=1
          data.loc[i,"position"] = 1
          data.loc[i,"position_enter_price"] = data.loc[i,"Close"]
        
        elif (data.loc[ i,"cond_signal_short"] == True):
          pass
        else:
          continue
      #Si estamos dentro
      else:
        enter_price = data.loc[i-1,"position_enter_price"]
        close_price = data.loc[i,"Close"]
        data.loc[i,"position_enter_price"] = enter_price

        if (data.loc[i-1,"position"] == 1):

          data.loc[i,"unrealized_PL"] = close_price-enter_price
          data.loc[i,"unrealized_PL_per"] = round((100*(close_price-enter_price)/enter_price),2)
          
          #Evalue si hay que salir o mantener la posicion
          if (data.loc[i,"macd_line"] < 0)|(data.loc[i,"bullish"]==False):
            data.loc[i,"position"] = 0
            data.loc[i,"out_by_st"] = 1
          else:
            if (data.loc[ i,"Close"] < data.loc[i,"supertrend"])&(data.loc[i,"sp_change"]==1):
                data.loc[i,"position"] = 0
                data.loc[i,"out_by_sp"] = 1
                t=1
            else:
              data.loc[i,"position"] = 1
        
        elif (data.loc[i-1,"position"] == -1):
          
          pass


    previous_row=(data.iloc[-2,:]).to_dict()
    current_row=(data.iloc[-1,:]).to_dict()

    data_to_show=data[["Date","Close","Low","High","cond_signal_long","position", "unrealized_PL", "unrealized_PL_per"]].tail(20)
    print(data_to_show)
    print('------->')

    print('Position to take:',current_row["position"])

    return [current_row["position"],current_row["Close"],current_row["unrealized_PL_per"],data]
   

def reg_lineal_slope(data,params):
    
    data = data.copy()

    reg_window = params[0]
    day_in = params[1]
  
    
    #index_of_strategy = f"{kvo}_{ema}"
 
    print(f"-----Regresion Lineal Slope reg{reg_window} confirmation day{day_in} - TrendFollowing ----")


   

    #LINEAR REGRESSION
    window_size = reg_window
    slopes = []
    predicted_values = []
    for i in range(len(data)):
        if i >= window_size - 1:
            x = data['Close'].iloc[i - window_size + 1:i + 1]
            if len(x) > 1:
                model = sm.OLS(x, sm.add_constant(np.arange(len(x)))).fit()
                slope = model.params[1]  # Slope of the regression line
                predicted_value = model.fittedvalues.iloc[-1]  # Predicted value
                slopes.append(slope)
                predicted_values.append(predicted_value)
            else:
                slopes.append(np.nan)
                predicted_values.append(np.nan)
        else:
            slopes.append(np.nan)
            predicted_values.append(np.nan)

    # Calculate the fitted values
    data['Slope'] = slopes

    

    #CONDITIONS
  
    data["cond_signal_long"]=np.where((data["Slope"] > 0)&(data["Slope"].shift(day_in) > 0),True,False)
    data["cond_signal_short"]=False

    data = data.dropna().reset_index(drop=True)
    data["position"]=0
    data["position_enter_price"]=0.0
    data["position_enter_price"] = data["position_enter_price"].astype(float)
    data["unrealized_PL"]=0.0
    data["unrealized_PL"] = data["unrealized_PL"].astype(float)
    data["unrealized_PL_per"]=0.0


    for i in range(data.shape[0]):
      if i == 0:
        data.loc[i,"position"] = 0
        continue

      #si estamos fuera
      if data.loc[ i-1,"position"] == 0:
        #Evalue si hay que entrar en la posicion
        if (data.loc[ i,"cond_signal_long"] == True):
          data.loc[i,"position"] = 1
          data.loc[i,"position_enter_price"] = data.loc[i,"Close"]
        elif (data.loc[ i,"cond_signal_short"] == True):
          pass
        else:
          continue
      #Si estamos dentro
      else:
        enter_price = data.loc[i-1,"position_enter_price"]
        close_price = data.loc[i,"Close"]
        data.loc[i,"position_enter_price"] = enter_price

        if (data.loc[i-1,"position"] == 1):

          data.loc[i,"unrealized_PL"] = close_price-enter_price
          data.loc[i,"unrealized_PL_per"] = round((100*(close_price-enter_price)/enter_price),2)
          
          #Evalue si hay que salir o mantener la posicion
          if (data.loc[i,"Slope"] < 0):
            data.loc[i,"position"] = 0
          else:
            data.loc[i,"position"] = 1
        
        elif (data.loc[i-1,"position"] == -1):
          
          pass


    previous_row=(data.iloc[-2,:]).to_dict()
    current_row=(data.iloc[-1,:]).to_dict()

    data_to_show=data[["Date","Close","Low","High","Slope","cond_signal_long","position", "unrealized_PL", "unrealized_PL_per"]].tail(20)
    print(data_to_show)
    print('------->')

    print('Position to take:',current_row["position"])

    return [current_row["position"],current_row["Close"],current_row["unrealized_PL_per"],data]
   

#CROSS STRATEGIES

def BondsRallying_v2(data, params):
    
    #["IEF",[7,14,28,56],7,10,5]

    bonds_SYMBOL = params[0]
    days_back1 = params[2][0]
    days_back2 = params[2][1]
    days_back3 = params[2][2]
    days_back4 = params[2][3]
    ma_bonds = params[1]
    sl = -params[3]
    tp = params[4]

    
    first_date_data = data.head(1)["Date"].item()
    last_date_data = data.tail(1)["Date"].item()

    
    start = first_date_data.strftime('%Y-%m-%d')
    end = (last_date_data + timedelta(days=1)).strftime('%Y-%m-%d')
    

    print(start)
    print(end)


    print(bonds_SYMBOL,start, end)

    data_bonds=download_data(bonds_SYMBOL)
    data_bonds=data_bonds.reset_index(drop=False)

    print(data_bonds)
    
    
    data_bonds["Close_B"] = data_bonds["Close"]
    data_bonds["Date_B"] = data_bonds["Date"]

    data=data.copy()

    data= pd.merge(data[["Date","Close"]], data_bonds[["Date_B","Close_B"]], left_on="Date", right_on="Date_B")

   
    print(f"----- SEC BondsRallying {bonds_SYMBOL}_[{days_back1},{days_back2},{days_back3},{days_back4}]_ma{ma_bonds}_sl{sl}_tp{tp} - CrossAsset ---")
    
    #EMA
    data["MA_B"]=data.Close_B.rolling(ma_bonds).mean()

    #CONDS
    data["Bonds_7daysback"]=data.Close_B.shift(days_back1)
    data["Bonds_14daysback"]=data.Close_B.shift(days_back2)
    data["Bonds_28daysback"]=data.Close_B.shift(days_back3)
    data["Bonds_56daysback"]=data.Close_B.shift(days_back4)

    data["Bonds_MA_7db"]=data.MA_B.shift(days_back1)
    data["Bonds_MA_14db"]=data.MA_B.shift(days_back2)
    data["Bonds_MA_28db"]=data.MA_B.shift(days_back3)
    data["Bonds_MA_56db"]=data.MA_B.shift(days_back4)

    data["Bonds_MA_ou"]=np.where(data["Close_B"]>data["MA_B"],3,-3)
    data["Bonds_7db_MA_ou"]=np.where(data["Bonds_7daysback"]>data["Bonds_MA_7db"],3,-3)
    data["Bonds_14db_MA_ou"]=np.where(data["Bonds_14daysback"]>data["Bonds_MA_14db"],2,-2)
    data["Bonds_28db_MA_ou"]=np.where(data["Bonds_28daysback"]>data["Bonds_MA_28db"],1,-1)
    data["Bonds_56db_MA_ou"]=np.where(data["Bonds_56daysback"]>data["Bonds_MA_56db"],1,-1)

    data["sumBonds"]=data["Bonds_MA_ou"]+data["Bonds_7db_MA_ou"]+data["Bonds_14db_MA_ou"]+data["Bonds_28db_MA_ou"]+data["Bonds_56db_MA_ou"]

    data = data.dropna().reset_index(drop=True)
    data["position"]=0
    data["position_enter_price"]=0.0
    data["position_enter_price"] = data["position_enter_price"].astype(float)
    data["unrealized_PL"]=0.0
    data["unrealized_PL"] = data["unrealized_PL"].astype(float)
    data["unrealized_PL_per"]=0.0

    
    for i in range(data.shape[0]):
      if i == 0:
        data.loc[i,"position"] = 0
        continue
     
      #si estamos fuera
      if data.loc[i-1,"position"] == 0:
        #Evalue si hay que entrar en la posicion
        if ((data.loc[i,"sumBonds"] > 4)):
          data.loc[i,"position"] = 1
          data.loc[i,"position_enter_price"] = data.loc[i,"Close"]
        else:
          continue
      #Si estamos dentro
      else:
        enter_price = data.loc[i-1,"position_enter_price"]
        close_price = data.loc[i,"Close"]
        data.loc[i,"position_enter_price"] = enter_price
        data.loc[i,"unrealized_PL"] = close_price-enter_price
        data.loc[i,"unrealized_PL_per"] = round((100*(close_price-enter_price)/enter_price),2)
        #Evalue si hay que salir o mantener la posicion
        if (((data.loc[i,"unrealized_PL_per"]>tp)|(data.loc[ i,"unrealized_PL_per"]<sl))):
          data.loc[i,"position"] = 0
        else:
          data.loc[i,"position"] = 1


    previous_row=(data.iloc[-2,:]).to_dict()
    current_row=(data.iloc[-1,:]).to_dict()

    data_to_show=data[["Date","Close","Close_B","MA_B","sumBonds","position","unrealized_PL_per"]].tail(15)
    print(data_to_show)
    print('------->')
    print('Position to take:',current_row["position"])

    return [current_row["position"],current_row["Close"],current_row["unrealized_PL_per"],data]



#combined strategies


def zs_cross_dema_combox2(data,params):
    
    data = data.copy()
    dema1 = params[0]
    dema2 = params[1]
    zscore_period = params[2]
    smaz = params[3]
    rsi = params[4]
    rsi_in = params[5]

    #DOBLE DEMA
    
    data["EMA1"]=data.Close.ewm(span=dema1).mean()
    data['DEMA_EMA1'] = data.EMA1.ewm(span=dema1).mean()
    data['DEMA1'] = 2 * data['EMA1'] - data['DEMA_EMA1']

    data["EMA2"]=data.Close.ewm(span=dema2).mean()
    data['DEMA_EMA2'] = data.EMA2.ewm(span=dema2).mean()
    data['DEMA2'] = 2 * data['EMA2'] - data['DEMA_EMA2']

    #ZSCORE CALCULATION

    data["ma"] = data["Close"].rolling(window=zscore_period).mean()
    data["stdev"] = data["Close"].rolling(window=zscore_period).std()
    data['zscore'] = (data['Close'] - data["ma"]) / (data["stdev"])

    #DEMA SCORE

    data["zEMA1"]=data['zscore'].ewm(span=smaz).mean()
    data['zDEMA_EMA1'] = data.zEMA1.ewm(span=smaz).mean()
    data['zDEMA'] = 2 * data['zEMA1'] - data['zDEMA_EMA1']

    window_size=3
    slopes = []
    for i in range(window_size-1, len(data)):
        x = np.arange(i-window_size+1, i+1)
        y = data["zDEMA"].values[i-window_size+1:i+1]
        slope, _ = np.polyfit(x, y, 1)
        slopes.append(slope)

    data['zdema_slope'] = np.nan
    data.loc[window_size-1:, 'zdema_slope'] = slopes



    #RSI INDICATOR
    serie = data.copy()
    serie["change"]=serie["Close"].diff()
    serie["changeup"] = np.where(serie["change"]>0,serie["change"],0)
    serie["changedown"] = np.where(serie["change"]<0,serie["change"],0)
    avg_up = serie["changeup"].rolling(rsi).mean()
    avg_down = serie["changedown"].rolling(rsi).mean().abs()
    data["rsi"] = round(((100 * avg_up) / (avg_up + avg_down)),2)

    
   
    #CONDITIONS
  
    data["cond_signal_long1"]=np.where(((data["DEMA1"]>data["DEMA2"])&(data["zDEMA"]>1))|
                                      ((data["DEMA1"]>data["DEMA2"])&(data["zDEMA"]<1)&(data["zdema_slope"]>0)),True,False)
    data["cond_signal_long2"]=np.where((data["cond_signal_long1"]!=True)&
                                       (data["rsi"]<rsi_in),True,False) 
    data["cond_signal_long"]=np.where((data["cond_signal_long1"])|(data["cond_signal_long2"]), True, False)
    
    data["cond_signal_short"]=False

    data["cond_out_long"]=np.where((data["cond_signal_long"]!=True)|
                                   ((data["cond_signal_long"]!=True)&(data["Close"]>data["High"].shift())), True, False)
    data["cond_out_short"]=False


    data = data.dropna().reset_index(drop=True)
    data["position"]=0
    data["position_enter_price"]=0
    data["position_enter_price"] = data["position_enter_price"].astype(float)
    data["unrealized_PL"]=0
    data["unrealized_PL"] = data["unrealized_PL"].astype(float)
    data["unrealized_PL_per"]=0
    data["unrealized_PL_per"] = data["unrealized_PL_per"].astype(float)
    data["out_by_sp"]=0
    data["out_by_ema"]=0
    data["t"]=0


    t=1
    for i in range(data.shape[0]):
      if i == 0:
        data.loc[i,"position"] = 0
        continue

      #si estamos fuera
      if data.loc[ i-1,"position"] == 0:
        if t >0:
          t+=1
        data.loc[i,"t"]=t

        #Evalue si hay que entrar en la posicion
        if (data.loc[ i,"cond_signal_long"] == True)&(t>16):#16
          data.loc[i,"position"] = 1
          data.loc[i,"position_enter_price"] = data.loc[i,"Close"]
        elif (data.loc[ i,"cond_signal_short"] == True):
          pass
        else:
          continue
      #Si estamos dentro
      else:
        enter_price = data.loc[i-1,"position_enter_price"]
        close_price = data.loc[i,"Close"]
        data.loc[i,"position_enter_price"] = enter_price

        if (data.loc[i-1,"position"] == 1):

          data.loc[i,"unrealized_PL"] = close_price-enter_price
          data.loc[i,"unrealized_PL_per"] = round((100*(close_price-enter_price)/enter_price),2)
          
          #Evalue si hay que salir o mantener la posicion
        if (data.loc[i,"cond_out_long"]):
            data.loc[i,"position"] = 0
        else:
            data.loc[i,"position"] = 1
        

    current_row=(data.iloc[-1,:]).to_dict()

    data_to_show=data[["Date","Close","High",
                       "DEMA1","DEMA2","zDEMA","zdema_slope","rsi",
                       "cond_signal_long1","cond_signal_long2","position"]].tail(20)
    print(data_to_show)
    print('------->')
    print('Position to take:',current_row["position"])
    return [current_row["position"], current_row["Close"], current_row["unrealized_PL_per"], data]
  

def trendZpull(data,params):

    data = data.copy()

    zscore_period = params[0]
    z_lvl = params[1]
    supertnd_look_back = params[2]
    supertnd_mult = params[3]
    
    

    print(f"----- zscore_period{zscore_period}_z_lvl{z_lvl}_supertnd_look_back{supertnd_look_back}_supertnd_mult{supertnd_mult} - TrendFollowing ----")

    data['zscore'] = zscore(data=data, window=zscore_period, serie="Close")
    supert = supertrend(data, lookback=supertnd_look_back, multiplier=supertnd_mult)
    data["supertrend"]=supert["supertrend"]
    
    #CONDITIONS
    data["cond_signal_long1"] = np.where(((data["zscore"]>z_lvl)&(data["zscore"].shift()<z_lvl)),True,False)
    data["cond_signal_long2"] = np.where((data["Close"]>data["supertrend"]),True,False)
    data["cond_signal_long"]=np.where(data["cond_signal_long1"]|data["cond_signal_long2"], True, False)

    data["cond_signal_short"]=False

    data = data.dropna().reset_index(drop=True)
    data["position"]=0
    data["position_enter_price"]=0.0
    data["position_enter_price"] = data["position_enter_price"].astype(float)
    data["unrealized_PL"]=0.0
    data["unrealized_PL"] = data["unrealized_PL"].astype(float)
    data["unrealized_PL_per"]=0.0

    for i in range(data.shape[0]):
      if i == 0:
        data.loc[i,"position"] = 0
        continue

      #si estamos fuera
      if data.loc[ i-1,"position"] == 0:
        #Evalue si hay que entrar en la posicion
        if (data.loc[ i,"cond_signal_long"] == True):
          data.loc[i,"position"] = 1
          data.loc[i,"position_enter_price"] = data.loc[i,"Close"]
        elif (data.loc[ i,"cond_signal_short"] == True):
          pass
        else:
          continue
      #Si estamos dentro
      else:
        enter_price = data.loc[i-1,"position_enter_price"]
        close_price = data.loc[i,"Close"]
        data.loc[i,"position_enter_price"] = enter_price

        if (data.loc[i-1,"position"] == 1):

          data.loc[i,"unrealized_PL"] = close_price-enter_price
          data.loc[i,"unrealized_PL_per"] = round((100*(close_price-enter_price)/enter_price),2)
          
          #Evalue si hay que salir o mantener la posicion
          cond_out_1=((data.loc[ i,"cond_signal_long1"] == False)&(data.loc[ i,"cond_signal_long2"] == False)&(data.loc[ i,"Close"] > data.loc[ i-1,"High"]))
          cond_out_2=((data.loc[ i,"Close"] < data.loc[ i,"supertrend"])&(data.loc[ i-1,"supertrend"]>data.loc[ i-1,"Close"]))
          if cond_out_1|cond_out_2:
            data.loc[i,"position"] = 0
          else:
            data.loc[i,"position"] = 1
        
        elif (data.loc[i-1,"position"] == -1):
          
          pass

    print(data.tail(20))

    #previous_row=(data.iloc[-2,:]).to_dict()
    current_row=(data.iloc[-1,:]).to_dict()

    data_to_show=data[["Date","Close","Low","High","cond_signal_long","position", "unrealized_PL", "unrealized_PL_per"]].tail(20)
    print(data_to_show)
    print('------->')

    print('Position to take:',current_row["position"])

    return [current_row["position"],current_row["Close"],current_row["unrealized_PL_per"],data]




strategy_functions={
    "MeanRev_BollingerBands": bollinger_bands,
    "MeanRev_MFI":money_flow_index,
    "MeanRev_LowestLow":lowest_low,
    "MeanRev_WeakRSI":rsi_weakness,
    "MeanRev_PullBackRSI":trend_pull_back_rsi,
    "MeanRev_BuyWeakness":buy_weakness,
    "CrossAssets_BondsRallying":BondsRallying_v2,
    "Momentum_MACDHist":macd_hist,
    "MeanRev_RegresRSIL":regression_rsi,
    "TrendFollowing_KVOBull":kvo_bull,
    "TrendFollowing_GoldCross":golden_cross,
    "MeanRev_RegresRSIS":regression_rsi_short,
    "Momentum_ZscoreBull":zscore_bull,
    "TrendFollowing_MACDSlope":macd_slope,
    "MeanRev_BuyWeaknessX":buy_weakness_x,
    "TrendFollowing_RegresLin":reg_lineal_slope,
    "Momentum_KVOdema":kvo_dema,
    "Momentum_RSIStrength":rsi_stremgth,
    "TrendFollowing_KVOBullSPT":kvo_bull_spt,
    "TrendFollowing_MACDSlopeSPT":macd_slope_spt,
    "Combo_ZCrossDema":zs_cross_dema_combox2,
    "Momentum_Zpullback":zs_pull,
    "Combo_TrendZpull":trendZpull,

}