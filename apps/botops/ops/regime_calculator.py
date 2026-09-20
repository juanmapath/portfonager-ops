"""
regime_calculator.py — Cálculo de Regímenes Macro y Apalancamiento Dinámico

Clasifica el estado del mercado en 8 regímenes basados en:
- Risk Ratio (HYG/LQD) Z-Score slope
- Dollar Index (DXY) Z-Score slope  
- VIX nivel (> 20 = alta volatilidad)

El apalancamiento se modula dinámicamente según el Profit Factor histórico
de la serie de velas descargada (4,000 velas) para el régimen activo hoy,
replicando fielmente la lógica de xmain.py desde el Día 1.
"""
import pandas as pd
import numpy as np
from datetime import timedelta
from django.utils import timezone


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_rolling_slope(series, window=10):
    """Calcula la pendiente de regresión lineal rolling."""
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


def _get_zscore(series, window=60):
    """Z-score rolling de una serie."""
    r = series.rolling(window=window)
    return (series - r.mean()) / r.std(ddof=0)


# ---------------------------------------------------------------------------
# Régimen Macro con Caché en DB (AssetSeries) y memoria
# ---------------------------------------------------------------------------

_macro_df_cache = {
    "df": None,
    "date": None,
}

def get_macro_regimes_df(apiToken, chatID, cache_minutes=15):
    """
    Descarga y calcula la serie histórica completa de los 8 regímenes macro
    para todas las velas disponibles (HYG, LQD, DXY, VIX).
    
    Retorna un DataFrame con ['date_str', 'Date', 'Regime', 'VIX', 'Slope_Risk', 'Slope_DXY'].
    Usa caché en memoria y AssetSeries para evitar descargas redundantes.
    """
    from apps.botops.models import AssetSeries
    from apps.botops.ops.bot_catalog import check_last_ohlc_and_download_data

    today_str = pd.Timestamp.today().strftime('%Y-%m-%d')
    now = timezone.now()

    # 1. Caché en memoria
    if _macro_df_cache["df"] is not None and _macro_df_cache["date"] == today_str:
        return _macro_df_cache["df"]

    tickers_macro = {
        "HYG": "HYG",
        "LQD": "LQD",
        "DXY": "DX-Y.NYB",
        "VIX": "^VIX",
    }
    
    dfs = {}
    for name, ticker in tickers_macro.items():
        df = check_last_ohlc_and_download_data(ticker, apiToken, chatID)
        if df is None or df.empty:
            print(f"[RegimeCalc] WARNING: No data for {ticker}.")
            return None
        df = df.copy()
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.sort_values("Date").reset_index(drop=True)
        dfs[name] = df
    
    # Merge por fecha (string YYYY-MM-DD) para alinear series
    df_master = dfs["VIX"][["Date", "Close"]].rename(columns={"Close": "VIX"})
    df_master["date_str"] = df_master["Date"].dt.strftime('%Y-%m-%d')
    
    for name in ["HYG", "LQD", "DXY"]:
        tmp = dfs[name][["Date", "Close"]].copy()
        tmp["date_str"] = tmp["Date"].dt.strftime('%Y-%m-%d')
        tmp = tmp.rename(columns={"Close": name})
        df_master = df_master.merge(tmp[["date_str", name]], on="date_str", how="left")
    
    df_master.dropna(inplace=True)
    df_master.reset_index(drop=True, inplace=True)
    
    if len(df_master) < 50:
        print("[RegimeCalc] WARNING: Insufficient macro data.")
        return None
    
    # Calcular indicadores macro — idéntico a xmain.py
    df_master["Z_Risk"] = _get_zscore(df_master["HYG"] / df_master["LQD"], window=48)
    df_master["Z_DXY"] = _get_zscore(df_master["DXY"], window=48)
    df_master["Slope_Risk"] = _get_rolling_slope(df_master["Z_Risk"], window=3)
    df_master["Slope_DXY"] = _get_rolling_slope(df_master["Z_DXY"], window=3)
    
    cond_risk_on = np.where(df_master["Slope_Risk"] > 0, 1, 0)
    cond_dxy_strong = np.where(df_master["Slope_DXY"] > 0, 1, 0)
    cond_vix_high = np.where(df_master["VIX"] > 20, 1, 0)
    
    regimes_list = []
    for r_on, dxy_str, vix_hi in zip(cond_risk_on, cond_dxy_strong, cond_vix_high):
        regimes_list.append(f"R_{r_on}_{dxy_str}_{vix_hi}")
        
    df_master["Regime"] = regimes_list
    
    # Guardar en caché de memoria
    _macro_df_cache["df"] = df_master
    _macro_df_cache["date"] = today_str
    
    # Guardar estado actual en AssetSeries
    try:
        macro_series, _ = AssetSeries.objects.get_or_create(ticker="MACRO_REGIME")
        macro_series.fin_metrics_series = {
            "regime": regimes_list[-1],
            "risk_on": int(cond_risk_on[-1]),
            "dxy_strong": int(cond_dxy_strong[-1]),
            "vix_high": int(cond_vix_high[-1]),
            "calculated_at": str(now)
        }
        macro_series.ochl_last_update = now
        macro_series.save()
    except Exception as e:
        print(f"[RegimeCalc] Error saving to AssetSeries: {e}")
        
    return df_master


def get_current_regime(apiToken, chatID):
    """Retorna únicamente el string del régimen actual de hoy."""
    df_macro = get_macro_regimes_df(apiToken, chatID)
    if df_macro is not None and not df_macro.empty:
        return df_macro["Regime"].iloc[-1]
    return "default"


# ---------------------------------------------------------------------------
# Cálculo Dinámico de Apalancamiento sobre la Serie Histórica (Opción A)
# ---------------------------------------------------------------------------

def calculate_dynamic_leverage_from_series(data_st_list, downloaded_df, apiToken, chatID, max_leverage):
    """
    Opción A:
    1. Obtiene la serie histórica de regímenes macro (HYG/LQD, DXY, VIX).
    2. Combina las señales históricas de las estrategias evaluadas.
    3. Extrae todos los trades históricos completados sobre las 4,000 velas descargadas.
    4. Identifica el régimen de hoy y calcula el Profit Factor (PF) histórico de ese régimen.
    5. Aplica la regla matemática de xmain.py para determinar el apalancamiento efectivo:
       - PF >= 2.5 (y >= 3 trades): 100% de max_leverage
       - PF >= 1.5 (y >= 3 trades): 75% de max_leverage
       - PF < 1.5 o < 3 trades: 1.0x (plano, sin apalancamiento / circuit breaker)

    Returns:
        tuple: (effective_leverage: float, current_regime: str, running_pf: float, n_trades: int)
    """
    df_macro = get_macro_regimes_df(apiToken, chatID)
    if df_macro is None or df_macro.empty:
        return 1.0, "default", 1.0, 0

    current_regime = df_macro["Regime"].iloc[-1]

    if not data_st_list or downloaded_df is None or downloaded_df.empty:
        return 1.0, current_regime, 1.0, 0

    # 1. Combinar posiciones históricas de todas las estrategias (MultiStrategy o OneStrategy)
    # Cada data_st tiene la columna 'position' (1, -1, 0)
    pos_dfs = []
    for d in data_st_list:
        if d is not None and 'position' in d.columns:
            pos_dfs.append(d['position'].fillna(0).astype(int))

    if not pos_dfs:
        return 1.0, current_regime, 1.0, 0

    sum_pos = sum(pos_dfs)
    combined_pos = np.where(sum_pos > 0, 1, np.where(sum_pos < 0, -1, 0))

    df_trades = pd.DataFrame({
        'Date': pd.to_datetime(downloaded_df['Date']),
        'Close': downloaded_df['Close'].astype(float),
        'position': combined_pos
    })
    df_trades['date_str'] = df_trades['Date'].dt.strftime('%Y-%m-%d')

    # 2. Alinear con regímenes por fecha
    merged = df_trades.merge(df_macro[['date_str', 'Regime']], on='date_str', how='left')
    merged['Regime'] = merged['Regime'].ffill().bfill().fillna('default')

    # 3. Extraer trades históricos completados
    completed_trades = []
    in_position = False
    entry_price = 0.0
    entry_regime = 'default'
    current_side = 0

    for i in range(len(merged)):
        pos = merged['position'].iloc[i]
        price = merged['Close'].iloc[i]
        regime = merged['Regime'].iloc[i]

        if not in_position and pos != 0:
            in_position = True
            current_side = pos
            entry_price = price
            entry_regime = regime
        elif in_position:
            if pos != current_side:
                # Trade completado
                if entry_price > 0:
                    if current_side == 1:
                        pnl_ret = (price - entry_price) / entry_price
                    else:
                        pnl_ret = (entry_price - price) / entry_price
                    
                    completed_trades.append({
                        'regime': entry_regime,
                        'pnl': pnl_ret,
                    })

                if pos != 0:
                    current_side = pos
                    entry_price = price
                    entry_regime = regime
                else:
                    in_position = False

    # 4. Filtrar trades históricos para el régimen actual de hoy
    matching_trades = [t for t in completed_trades if t['regime'] == current_regime]
    n_trades = len(matching_trades)

    if n_trades >= 3:
        gains = sum(t['pnl'] for t in matching_trades if t['pnl'] > 0)
        losses = sum(abs(t['pnl']) for t in matching_trades if t['pnl'] <= 0)
        
        if losses > 0:
            running_pf = gains / losses
        elif gains > 0:
            running_pf = float('inf')
        else:
            running_pf = 1.0

        if running_pf >= 2.5:
            leverage_mult = 1.0
        elif running_pf >= 1.5:
            leverage_mult = 0.75
        else:
            leverage_mult = 0.0
    else:
        running_pf = 1.0
        leverage_mult = 0.0

    effective_leverage = round(1.0 + leverage_mult * (max_leverage - 1.0), 2)

    pf_display = f"{running_pf:.2f}" if running_pf != float('inf') else "Inf"
    print(f"[DynLeverage HotCalc] Today's Regime '{current_regime}': {n_trades} hist trades, "
          f"PF={pf_display}, mult={leverage_mult} -> Effective Leverage: {effective_leverage}x")

    return effective_leverage, current_regime, running_pf, n_trades
