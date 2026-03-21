import numpy as np
import pandas as pd
import decimal

def MACD(serie, fast_period=28, slow_period=56, signal_period=14):

      ema_fast = serie.ewm(span=fast_period, adjust=False).mean()
      ema_slow = serie.ewm(span=slow_period, adjust=False).mean()
      macd_line = ema_fast - ema_slow
      signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
      macd_histogram = macd_line - signal_line
      return [macd_line, signal_line, macd_histogram]


def ATR(data, window):
    
    serie = data.copy()
  
    serie['High-Low'] = serie['High'] - serie['Low']
    serie['High-PrevClose'] = abs(serie['High'] - serie['Close'].shift(1))
    serie['Low-PrevClose'] = abs(serie['Low'] - serie['Close'].shift(1))
    serie['TR'] = serie[['High-Low', 'High-PrevClose', 'Low-PrevClose']].max(axis=1)
    serie['ATR'] = serie['TR'].rolling(window=window).mean()

    return serie['ATR']


def RSI(data, window=14):

    serie = data.copy()
    serie["change"]=serie.Close.diff()
    serie["changeup"] = np.where(serie["change"]>0,serie["change"],0)
    serie["changedown"] = np.where(serie["change"]<0,serie["change"],0)
    avg_up = serie["changeup"].rolling(window).mean()
    avg_down = serie["changedown"].rolling(window).mean().abs()
    serie["rsi"] = round(((100 * avg_up) / (avg_up + avg_down)),2)

    return serie["rsi"]
  

def supertrend(data, lookback=28, multiplier=2):

    data=data.copy()
    #high=data["High"]
    #low=data["Low"]
    #close=data["Close"]

    # ATR
    data["atr"] = ATR(data, window=lookback)
    
    # H/L AVG AND BASIC UPPER & LOWER BAND
    data["hl_avg"] = (data.High + data.Low) / 2
    data["upper_band"] = (data.hl_avg + multiplier * data.atr)#.dropna().reset_index(drop=True)
    data["lower_band"] = (data.hl_avg - multiplier * data.atr)#.dropna().reset_index(drop=True)
    data["final_upper"] = 0.0
    data["final_upper"] =data["final_upper"].astype(float)
    data["final_lower"] = 0.0
    data["final_lower"] =data["final_lower"].astype(float)


    # FINAL UPPER BAND
    #final_bands = pd.DataFrame(columns = ['upper', 'lower'])
    #final_bands.iloc[:,0] = [x for x in upper_band - upper_band]
    #final_bands.iloc[:,1] = final_bands.iloc[:,0]
    #print(final_bands.describe())
    #print(data.shape)
    lastindex_data=data.shape[0]
    #print(data.lower_band.dropna())
    inindex_final_band=data.lower_band.dropna().index.to_list()[0]
    
    #print("inindex_final_band",inindex_final_band)
    

    for i in range(inindex_final_band, lastindex_data):
        if i == inindex_final_band:
            data.loc[i,"final_upper"] = data.loc[i,"upper_band"]
        else:
            if (data.loc[i,"upper_band"] < data.loc[i-1,"final_upper"]) | (data.loc[i-1,"Close"] > data.loc[i-1,"final_upper"]):
                data.loc[i,"final_upper"] = data.loc[i,"upper_band"]
            else:
                data.loc[i,"final_upper"] = data.loc[i-1,"final_upper"]

    # FINAL LOWER BAND
    for i in range(inindex_final_band, lastindex_data):
        if i == inindex_final_band:
            data.loc[i,"final_lower"] = data.loc[i,"lower_band"]
        else:
            if (data.loc[i,"lower_band"] > data.loc[i-1,"final_lower"]) | (data.loc[i-1,"Close"] < data.loc[i-1,"final_lower"]):
                data.loc[i,"final_lower"] = data.loc[i,"lower_band"]
            else:
                data.loc[i,"final_lower"] = data.loc[i-1,"final_lower"]
    #print(data.dropna())
    #print("final_b")
    #print(data[["final_upper","final_lower"]])
    #print(data[["final_upper","final_lower"]].describe())

    # SUPERTREND

    #print(data)

    data["supertrend"]=0.0
    data["supertrend"] =data["supertrend"].astype(float)

    #supertrend = pd.DataFrame(columns = [f'supertrend'])
    #supertrend.iloc[:,0] = [x for x in final_bands['upper'] - final_bands['upper']]

    """
    data["supertrend"]=np.where((data["supertrend"].shift()==data["final_upper"].shift())
                                &(data["Close"]<data["final_upper"]),
                                data["final_upper"],data["supertrend"])
    
    data["supertrend"]=np.where((data["supertrend"].shift()==data["final_upper"].shift())
                                &(data["Close"]>data["final_upper"]),
                                data["final_lower"],data["supertrend"])
    
    data["supertrend"]=np.where((data["supertrend"].shift()==data["final_lower"].shift())
                                &(data["Close"]>data["final_lower"]),
                                data["final_lower"],data["supertrend"])
    
    data["supertrend"]=np.where((data["supertrend"].shift()==data["final_lower"].shift())
                                &(data["Close"]<data["final_lower"]),
                                data["final_upper"],data["supertrend"])
    
    
    """
    #print(data[["Close","final_upper","final_lower"]].replace(0, None).dropna())

    for i in range(inindex_final_band, lastindex_data):
        if i == inindex_final_band:
            if data.loc[i, "Close"] > data.loc[i-1, "Close"]:
              data.loc[i, "supertrend"] = data.loc[i,"final_lower"]
            else:
              data.loc[i, "supertrend"] = data.loc[i,"final_upper"]

        elif (data.loc[i-1, "supertrend"] == data.loc[i-1,"final_upper"] and data.loc[i,"Close"] < data.loc[i,"final_upper"]):
            data.loc[i, "supertrend"] = data.loc[i,"final_upper"]
        elif (data.loc[i-1, "supertrend"] == data.loc[i-1,"final_upper"] and data.loc[i,"Close"] > data.loc[i,"final_upper"]):
            data.loc[i, "supertrend"] = data.loc[i,"final_lower"]
        elif (data.loc[i-1, "supertrend"] == data.loc[i-1,"final_lower"] and data.loc[i,"Close"] > data.loc[i,"final_lower"]):
            data.loc[i, "supertrend"] = data.loc[i,"final_lower"]
        elif (data.loc[i-1, "supertrend"] == data.loc[i-1,"final_lower"] and data.loc[i,"Close"] < data.loc[i,"final_lower"]):
            data.loc[i, "supertrend"] = data.loc[i,"final_upper"]
    #"""

    #supertrend = supertrend.set_index(upper_band.index)
    #supertrend = supertrend.dropna()[1:].reset_index(drop=True)
    #print(data)

  

    data["st_up"]=np.where(data["supertrend"]<data["Close"],data["supertrend"],None)
    data["st_d"]=np.where(data["supertrend"]>data["Close"],data["supertrend"],None)

    # ST UPTREND/DOWNTREND

    #print(data)

    return data[["supertrend","st_up","st_d"]]


def dema(data, window, serie="Close"):

    data=data.copy()

    data["EMA"]=data[serie].ewm(span=window).mean()
    data["DEMA_EMA"] = data["EMA"].ewm(span=window).mean()
    data["DEMA" ]= 2 * data["EMA"] - data["DEMA_EMA"]
    return data["DEMA"]


def slope(data, window, serie="Close"):
    data=data.copy()
    window_size=window
    slopes = []
    for i in range(window_size-1, len(data)):
        x = np.arange(i-window_size+1, i+1)
        y = data[serie].values[i-window_size+1:i+1]
        slope, _ = np.polyfit(x, y, 1)
        slopes.append(slope)

    data['slope'] = np.nan
    data.loc[window_size-1:, 'slope'] = slopes
    
    return data['slope']



def zscore(data, window, serie="Close"):
    data=data.copy()
    data["ma"] = data[serie].rolling(window=window).mean()
    data["stdev"] = data[serie].rolling(window=window).std()
    data['zscore'] = (data[serie] - data["ma"]) / (data["stdev"])
    return data["zscore"]



def round_down(value, decimals):
    with decimal.localcontext() as ctx:
        d = decimal.Decimal(value)
        ctx.rounding = decimal.ROUND_DOWN        
        return float(round(d, int(decimals)))

