import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
from django.utils import timezone
from apps.research.models import SectorScreenerCache
from scipy.stats import spearmanr

TICKERS_CONFIG = {
    # GICS Sectors
    "XLK": {"name": "Tecnología", "alias": "TECH", "category": "GICS Sectors", "color": "#7b61ff"},
    "XLF": {"name": "Finanzas", "alias": "FINANZAS", "category": "GICS Sectors", "color": "#00ff94"},
    "XLV": {"name": "Salud", "alias": "SALUD", "category": "GICS Sectors", "color": "#00d4ff"},
    "XLY": {"name": "Consumo Discrecional", "alias": "CONS. DISC", "category": "GICS Sectors", "color": "#ffb800"},
    "XLC": {"name": "Comunicaciones", "alias": "COMUNIC", "category": "GICS Sectors", "color": "#e040fb"},
    "XLI": {"name": "Industriales", "alias": "INDUSTRIA", "category": "GICS Sectors", "color": "#2979ff"},
    "XLP": {"name": "Consumo Básico", "alias": "CONS. BÁS", "category": "GICS Sectors", "color": "#76ff03"},
    "XLE": {"name": "Energía", "alias": "ENERGÍA", "category": "GICS Sectors", "color": "#ff6d00"},
    "XLU": {"name": "Utilities", "alias": "UTILITIES", "category": "GICS Sectors", "color": "#ffd600"},
    "XLRE": {"name": "Bienes Raíces", "alias": "INMOBIL", "category": "GICS Sectors", "color": "#ff4081"},
    "XLB": {"name": "Materiales Básicos", "alias": "MATERIALES", "category": "GICS Sectors", "color": "#18ffff"},
    # Cap Sizes
    "MDY": {"name": "S&P MidCap 400", "alias": "MID CAP", "category": "Cap Sizes", "color": "#ffab00"},
    "IWM": {"name": "Russell 2000", "alias": "SMALL CAP", "category": "Cap Sizes", "color": "#00e676"},
    # Market & Macro
    "SPY": {"name": "S&P 500 (Benchmark)", "alias": "S&P 500", "category": "Market & Macro", "color": "#ffffff"},
    "SMH": {"name": "Semiconductores", "alias": "SEMIS", "category": "Market & Macro", "color": "#00e5ff"},
    "GLD": {"name": "Oro", "alias": "ORO", "category": "Market & Macro", "color": "#ffd700"},
    "TLT": {"name": "Bonos Tesoro 20+A", "alias": "BONOS 20A", "category": "Market & Macro", "color": "#3d5afe"},
    "HYG": {"name": "Bonos Alto Rendimiento", "alias": "HIGH YIELD", "category": "Market & Macro", "color": "#ff3d00"},
}

TICKER_LIST = list(TICKERS_CONFIG.keys())
BENCHMARK_TICKER = "SPY"

def sanitize_val(val):
    if val is None or pd.isna(val) or np.isinf(val):
        return None
    return round(float(val), 2)


def compute_quant_analytics(close_df, callan_quarters, rolling_returns):
    """
    Computes:
    1. Historical Rank Transition Matrices (Markov Chain on Terciles)
    2. Spearman Rank Information Coefficient (IC) Grid & t-stats across lookback and forward windows
    3. Quantitative regime classification & badges for each ticker
    """
    gics_tickers = [t for t in TICKER_LIST if TICKERS_CONFIG[t].get("category") == "GICS Sectors" and t in close_df.columns]
    if len(gics_tickers) < 6:
        gics_tickers = [t for t in TICKER_LIST if t in close_df.columns]

    df_sectors = close_df[gics_tickers].dropna(how="all").ffill()

    lookback_days = {"1M": 21, "3M": 63, "6M": 126, "1Y": 252}
    forward_days = {"1M": 21, "3M": 63, "6M": 126, "1Y": 252}

    # 1. Transition Matrices
    transition_matrices = {}
    for l_key, l_days in lookback_days.items():
        transition_matrices[l_key] = {}
        past_ret = df_sectors.pct_change(l_days)

        for f_key, f_days in forward_days.items():
            fwd_ret = df_sectors.pct_change(f_days).shift(-f_days)
            transitions = []
            step = max(21, min(l_days, f_days))

            for i in range(l_days, len(df_sectors) - f_days, step):
                p = past_ret.iloc[i].dropna()
                f = fwd_ret.iloc[i].dropna()
                common = p.index.intersection(f.index)
                if len(common) >= 6:
                    rank_p = p[common].rank(ascending=False)
                    rank_f = f[common].rank(ascending=False)
                    total_n = len(common)
                    top_cutoff = max(2, int(total_n / 3.0))
                    bot_cutoff = total_n - top_cutoff + 1

                    for sec in common:
                        rp = rank_p[sec]
                        rf = rank_f[sec]
                        sp = 1 if rp <= top_cutoff else (3 if rp >= bot_cutoff else 2)
                        sf = 1 if rf <= top_cutoff else (3 if rf >= bot_cutoff else 2)
                        transitions.append((sp, sf))

            if transitions:
                ct = pd.crosstab(
                    pd.Series([x[0] for x in transitions], name='from'),
                    pd.Series([x[1] for x in transitions], name='to'),
                    normalize='index'
                ).reindex(index=[1, 2, 3], columns=[1, 2, 3], fill_value=0.0)
                matrix_pct = (ct * 100.0).round(1).values.tolist()
            else:
                matrix_pct = [[33.3, 33.3, 33.3], [33.3, 33.3, 33.3], [33.3, 33.3, 33.3]]

            transition_matrices[l_key][f_key] = {
                "lookback": l_key,
                "forward": f_key,
                "matrix": matrix_pct,
                "top_stay": matrix_pct[0][0],
                "bot_stay": matrix_pct[2][2],
                "reversal": matrix_pct[2][0],
                "sample_count": len(transitions)
            }

    # 2. Rank IC Grid
    ic_grid = []
    for l_key, l_days in lookback_days.items():
        for f_key, f_days in forward_days.items():
            past = df_sectors.pct_change(l_days)
            fwd = df_sectors.pct_change(f_days).shift(-f_days)
            ics = []
            for i in range(l_days, len(df_sectors) - f_days, 21):
                p = past.iloc[i].dropna()
                f = fwd.iloc[i].dropna()
                common = p.index.intersection(f.index)
                if len(common) >= 5:
                    c, _ = spearmanr(p[common], f[common])
                    if not np.isnan(c):
                        ics.append(c)
            s = pd.Series(ics)
            mean_ic = float(s.mean()) if len(s) > 0 else 0.0
            std_ic = float(s.std()) if len(s) > 0 else 0.0
            t_stat = float(mean_ic / (std_ic / np.sqrt(len(s)))) if len(s) > 0 and std_ic > 0 else 0.0

            if t_stat > 1.5:
                interp = "Momentum Positivo (Inercia)"
            elif t_stat < -1.5:
                interp = "Reversión a la Media (Rotación)"
            else:
                interp = "Ruido / Neutral"

            ic_grid.append({
                "lookback": l_key,
                "forward": f_key,
                "mean_ic": round(mean_ic, 4),
                "std_ic": round(std_ic, 4),
                "t_stat": round(t_stat, 2),
                "interpretation": interp
            })

    # 3. Sector Regimes
    sector_streaks = {t: {"top_count": 0, "bot_count": 0, "last_ranks": []} for t in TICKER_LIST}
    recent_quarters = callan_quarters[:6] if callan_quarters else []
    for q_col in recent_quarters:
        for r_item in q_col.get("rankings", []):
            tk = r_item["ticker"]
            rnk = r_item["rank"]
            if tk in sector_streaks and isinstance(rnk, (int, float)):
                sector_streaks[tk]["last_ranks"].append(rnk)
                if rnk <= 3:
                    sector_streaks[tk]["top_count"] += 1
                elif rnk >= 7:
                    sector_streaks[tk]["bot_count"] += 1

    all_3m = {t: rolling_returns[t].get("3M") for t in TICKER_LIST if rolling_returns[t].get("3M") is not None}
    all_6m = {t: rolling_returns[t].get("6M") for t in TICKER_LIST if rolling_returns[t].get("6M") is not None}
    all_1m = {t: rolling_returns[t].get("1M") for t in TICKER_LIST if rolling_returns[t].get("1M") is not None}

    sorted_3m = sorted(all_3m.items(), key=lambda x: x[1], reverse=True)
    rank_3m_map = {t: idx + 1 for idx, (t, _) in enumerate(sorted_3m)}

    sorted_6m = sorted(all_6m.items(), key=lambda x: x[1], reverse=True)
    rank_6m_map = {t: idx + 1 for idx, (t, _) in enumerate(sorted_6m)}

    sector_regimes = {}
    for ticker in TICKER_LIST:
        r3 = rank_3m_map.get(ticker, 99)
        r6 = rank_6m_map.get(ticker, 99)
        ret1m = all_1m.get(ticker, 0) or 0
        ret3m = all_3m.get(ticker, 0) or 0

        streak_info = sector_streaks.get(ticker, {"top_count": 0, "bot_count": 0})
        top_streak = streak_info["top_count"]
        bot_streak = streak_info["bot_count"]

        # Acceleration: 1M vs monthly average of 3M
        accel = ret1m - (ret3m / 3.0) if ret3m else ret1m

        if r3 <= 3 or r6 <= 3:
            if top_streak >= 4 or (top_streak >= 2 and accel < -2.5):
                badge = "RIESGO DE AGOTAMIENTO"
                badge_type = "exhaustion"
                desc = "Líder extendido (>3 trimestres en top o desaceleración aguda). Riesgo de rotación."
            else:
                badge = "PERSISTENCIA ALTA"
                badge_type = "momentum"
                desc = "Líder con inercia de flujo institucional positiva y momentum confirmado."
        elif r3 >= 7 or r6 >= 7:
            if bot_streak >= 3 and accel > 1.5:
                badge = "CANDIDATO A REBOTE"
                badge_type = "reversal"
                desc = "Sobreventa extrema con catalizador de rebote contrarian de corto plazo."
            elif ret1m < -1.0:
                badge = "EN DETERIORO"
                badge_type = "downtrend"
                desc = "Rezagado en caída continua sin catalizadores de giro."
            else:
                badge = "CONSOLIDACIÓN"
                badge_type = "base"
                desc = "En formación de base tras período de rezago."
        else:
            badge = "ESTABLE / NEUTRAL"
            badge_type = "neutral"
            desc = "Rendimiento promedio alineado al mercado general."

        sector_regimes[ticker] = {
            "badge": badge,
            "badge_type": badge_type,
            "description": desc,
            "rank_3m": r3,
            "rank_6m": r6,
            "top_streak": top_streak,
            "bot_streak": bot_streak,
            "acceleration": round(accel, 2)
        }

    return {
        "transition_matrices": transition_matrices,
        "ic_grid": ic_grid,
        "sector_regimes": sector_regimes
    }


def update_screener_data():
    """
    Downloads historical data for the 18 ETFs starting from 1999 (to cover year 2000 to present),
    computes returns by periods (years 2000-2026, quarters, bimonthly, months, rolling),
    builds ranking tables, and saves to SectorScreenerCache.
    """
    print("[ScreenerEngine] Starting batch download of ETFs from 1999 to present...")
    raw_df = yf.download(TICKER_LIST, start="1999-01-01", interval="1d", auto_adjust=True, progress=False)

    if isinstance(raw_df.columns, pd.MultiIndex):
        close_df = raw_df["Close"].copy()
    else:
        close_df = raw_df.copy()

    # Fill forward then backward for valid data periods
    close_df.index = pd.to_datetime(close_df.index)
    close_df.sort_index(inplace=True)

    last_date = close_df.index[-1].strftime("%Y-%m-%d")
    current_prices = {t: sanitize_val(close_df[t].dropna().iloc[-1]) if t in close_df.columns and not close_df[t].dropna().empty else None for t in TICKER_LIST}

    # 1. Rolling Returns
    rolling_returns = {}
    current_year = close_df.index[-1].year
    prev_year_data = close_df[close_df.index.year < current_year]
    ytd_base_price = prev_year_data.iloc[-1] if len(prev_year_data) > 0 else close_df.iloc[0]

    def get_pct(series, offset):
        s_clean = series.dropna()
        if len(s_clean) > offset:
            p_end = s_clean.iloc[-1]
            p_start = s_clean.iloc[-(offset + 1)]
            if p_start > 0:
                return ((p_end / p_start) - 1.0) * 100.0
        return None

    for ticker in TICKER_LIST:
        if ticker not in close_df.columns:
            continue
        s = close_df[ticker]
        s_clean = s.dropna()
        ytd_val = None
        if not s_clean.empty and ticker in ytd_base_price and pd.notna(ytd_base_price[ticker]) and ytd_base_price[ticker] > 0:
            ytd_val = ((s_clean.iloc[-1] / ytd_base_price[ticker]) - 1.0) * 100.0

        rolling_returns[ticker] = {
            "1D": sanitize_val(get_pct(s, 1)),
            "1W": sanitize_val(get_pct(s, 5)),
            "1M": sanitize_val(get_pct(s, 21)),
            "3M": sanitize_val(get_pct(s, 63)),
            "6M": sanitize_val(get_pct(s, 126)),
            "YTD": sanitize_val(ytd_val),
            "1Y": sanitize_val(get_pct(s, 252)),
            "3Y": sanitize_val(get_pct(s, 252 * 3)),
            "5Y": sanitize_val(get_pct(s, 252 * 5)),
            "10Y": sanitize_val(get_pct(s, 252 * 10)),
        }

    # 2. Calendar Years Returns (From 2000 to Current Year)
    yearly_df = close_df.resample('YE').last()
    yearly_pct = yearly_df.pct_change() * 100.0

    # Collect all available years >= 2000
    available_years = [y.year for y in yearly_df.index if 2000 <= y.year < current_year]
    all_past_years = sorted(available_years, reverse=True)  # 2025, 2024, ..., 2000

    yearly_returns = {t: {} for t in TICKER_LIST}
    for ticker in TICKER_LIST:
        if ticker in close_df.columns:
            yearly_returns[ticker][f"{current_year}_YTD"] = rolling_returns[ticker]["YTD"]
            for y in all_past_years:
                ts = [d for d in yearly_df.index if d.year == y]
                if ts and ticker in yearly_pct.columns:
                    val = yearly_pct.loc[ts[0], ticker]
                    yearly_returns[ticker][str(y)] = sanitize_val(val)

    # 3. Calendar Quarters Returns (All Quarters from 2000 to Present)
    quarterly_df = close_df.resample('QE').last()
    quarterly_pct = quarterly_df.pct_change() * 100.0
    quarter_dates = [qd for qd in sorted(quarterly_df.index, reverse=True) if qd.year >= 2000]
    quarter_keys = []
    quarterly_returns = {t: {} for t in TICKER_LIST}

    for qd in quarter_dates:
        q_label = f"{qd.year}_Q{qd.quarter}"
        quarter_keys.append(q_label)
        for ticker in TICKER_LIST:
            if ticker in quarterly_pct.columns:
                val = quarterly_pct.loc[qd, ticker]
                quarterly_returns[ticker][q_label] = sanitize_val(val)

    # 4. Monthly Returns (Last 24 months)
    monthly_df = close_df.resample('ME').last()
    monthly_pct = monthly_df.pct_change() * 100.0
    month_dates = sorted(monthly_df.index, reverse=True)[:24]
    month_keys = []
    monthly_returns = {t: {} for t in TICKER_LIST}

    for md in month_dates:
        m_label = md.strftime("%Y-%m")
        month_keys.append(m_label)
        for ticker in TICKER_LIST:
            if ticker in monthly_pct.columns:
                val = monthly_pct.loc[md, ticker]
                monthly_returns[ticker][m_label] = sanitize_val(val)

    # 5. Bi-monthly (Bimestres) Returns (All Bimestres from 2000 to Present)
    bimonthly_keys = []
    bimonthly_returns = {t: {} for t in TICKER_LIST}

    for byear in range(current_year, 1999, -1):
        for bnum in range(6, 0, -1):
            b_key = f"{byear}_B{bnum}"
            end_month = bnum * 2
            start_month = end_month - 2

            end_candidates = close_df[(close_df.index.year == byear) & (close_df.index.month <= end_month) & (close_df.index.month >= end_month - 1)]
            if end_candidates.empty:
                continue
            p_end = end_candidates.iloc[-1]

            if start_month == 0:
                prev_year_candidates = close_df[close_df.index.year < byear]
                p_start = prev_year_candidates.iloc[-1] if len(prev_year_candidates) > 0 else close_df.iloc[0]
            else:
                prev_candidates = close_df[(close_df.index.year == byear) & (close_df.index.month <= start_month)]
                p_start = prev_candidates.iloc[-1] if len(prev_candidates) > 0 else close_df.iloc[0]

            bimonthly_keys.append(b_key)
            for ticker in TICKER_LIST:
                if ticker in close_df.columns:
                    p0 = p_start[ticker]
                    p1 = p_end[ticker]
                    if pd.notna(p0) and pd.notna(p1) and p0 > 0:
                        ret = ((p1 / p0) - 1.0) * 100.0
                        bimonthly_returns[ticker][b_key] = sanitize_val(ret)
                    else:
                        bimonthly_returns[ticker][b_key] = None

    # 6. Spreads vs Benchmark (SPY)
    spreads_vs_benchmark = {t: {} for t in TICKER_LIST}
    spy_rolling = rolling_returns.get(BENCHMARK_TICKER, {})
    spy_yearly = yearly_returns.get(BENCHMARK_TICKER, {})

    for ticker in TICKER_LIST:
        for rk, rval in rolling_returns[ticker].items():
            spy_val = spy_rolling.get(rk)
            spread = (rval - spy_val) if (rval is not None and spy_val is not None) else None
            spreads_vs_benchmark[ticker][f"rolling_{rk}"] = sanitize_val(spread)

        for yk, yval in yearly_returns[ticker].items():
            spy_val = spy_yearly.get(yk)
            spread = (yval - spy_val) if (yval is not None and spy_val is not None) else None
            spreads_vs_benchmark[ticker][f"yearly_{yk}"] = sanitize_val(spread)

    # 7. Callan Periodic Table Matrix (Heatmap Rankings per period)
    def build_callan_columns(period_type, period_keys, return_dict, label_formatter):
        cols = []
        for pk in period_keys:
            valid_rankings = []
            unranked = []
            for ticker in TICKER_LIST:
                ret = return_dict[ticker].get(pk)
                item = {
                    "ticker": ticker,
                    "alias": TICKERS_CONFIG[ticker]["alias"],
                    "name": TICKERS_CONFIG[ticker]["name"],
                    "category": TICKERS_CONFIG[ticker]["category"],
                    "color": TICKERS_CONFIG[ticker]["color"],
                    "return": ret
                }
                if ret is not None:
                    valid_rankings.append(item)
                else:
                    unranked.append(item)

            # Sort valid returns descending
            valid_rankings.sort(key=lambda x: -x["return"])
            for rank_idx, item in enumerate(valid_rankings, 1):
                item["rank"] = rank_idx

            for item in unranked:
                item["rank"] = "-"

            # Combine active followed by unranked if any
            cols.append({
                "period_key": pk,
                "label": label_formatter(pk),
                "rankings": valid_rankings + unranked,
                "active_count": len(valid_rankings)
            })
        return cols

    year_keys_ordered = [f"{current_year}_YTD"] + [str(y) for y in all_past_years]
    callan_years = build_callan_columns(
        "years", year_keys_ordered, yearly_returns,
        lambda k: f"{current_year} (YTD)" if "_YTD" in k else k
    )

    callan_quarters = build_callan_columns(
        "quarters", quarter_keys, quarterly_returns,
        lambda k: k.replace("_", " ")
    )

    callan_bimonthly = build_callan_columns(
        "bimonthly", bimonthly_keys, bimonthly_returns,
        lambda k: k.replace("_B", " Bim ")
    )

    callan_months = build_callan_columns(
        "months", month_keys, monthly_returns,
        lambda k: k
    )

    # Compute Quantitative Analytics (Transition Matrices, Rank IC Grid, Sector Regimes)
    quant_data = compute_quant_analytics(close_df, callan_quarters, rolling_returns)

    # Combine ticker records for screener table
    tickers_data = []
    for ticker in TICKER_LIST:
        tickers_data.append({
            "ticker": ticker,
            "alias": TICKERS_CONFIG[ticker]["alias"],
            "name": TICKERS_CONFIG[ticker]["name"],
            "category": TICKERS_CONFIG[ticker]["category"],
            "color": TICKERS_CONFIG[ticker]["color"],
            "last_price": current_prices.get(ticker),
            "rolling": rolling_returns[ticker],
            "yearly": yearly_returns[ticker],
            "quarterly": quarterly_returns[ticker],
            "bimonthly": bimonthly_returns[ticker],
            "monthly": monthly_returns[ticker],
            "spreads": spreads_vs_benchmark[ticker],
            "regime": quant_data["sector_regimes"].get(ticker, {
                "badge": "ESTABLE / NEUTRAL",
                "badge_type": "neutral",
                "description": "Régimen promedio de mercado.",
                "rank_3m": 99,
                "rank_6m": 99,
                "top_streak": 0,
                "bot_streak": 0,
                "acceleration": 0.0
            }),
        })

    summary_payload = {
        "last_updated": timezone.now().isoformat(),
        "last_market_date": last_date,
        "benchmark": BENCHMARK_TICKER,
        "tickers": tickers_data,
        "periods": {
            "rolling": ["1D", "1W", "1M", "3M", "6M", "YTD", "1Y", "3Y", "5Y", "10Y"],
            "yearly": year_keys_ordered,
            "quarterly": quarter_keys,
            "bimonthly": bimonthly_keys,
            "monthly": month_keys,
        },
        "callan_matrix": {
            "years": callan_years,
            "quarters": callan_quarters,
            "bimonthly": callan_bimonthly,
            "months": callan_months,
        },
        "quant_analytics": {
            "transition_matrices": quant_data["transition_matrices"],
            "ic_grid": quant_data["ic_grid"],
        }
    }

    # Store full daily prices for timeseries
    # Format: dates list and prices dict
    daily_prices_payload = {
        "dates": [d.strftime("%Y-%m-%d") for d in close_df.index],
        "prices": {t: [sanitize_val(v) for v in close_df[t].values] for t in TICKER_LIST if t in close_df.columns}
    }

    cache_obj, _ = SectorScreenerCache.objects.get_or_create(key="default_screener")
    cache_obj.tickers_list = TICKER_LIST
    cache_obj.summary_data = summary_payload
    cache_obj.daily_prices = daily_prices_payload
    cache_obj.save()

    print(f"[ScreenerEngine] Successfully updated screener data. Total years: {len(year_keys_ordered)}. Last market date: {last_date}")
    return summary_payload


def get_screener_summary():
    try:
        cache_obj = SectorScreenerCache.objects.filter(key="default_screener").first()
        if cache_obj and cache_obj.summary_data:
            return cache_obj.summary_data
    except Exception as e:
        print(f"[ScreenerEngine] Cache read error: {e}")

    return update_screener_data()


def get_screener_timeseries(selected_tickers=None, range_str="1Y", benchmark="SPY"):
    cache_obj = SectorScreenerCache.objects.filter(key="default_screener").first()
    if not cache_obj or not cache_obj.daily_prices:
        update_screener_data()
        cache_obj = SectorScreenerCache.objects.filter(key="default_screener").first()

    if not cache_obj or not cache_obj.daily_prices:
        return {"dates": [], "series": []}

    dates = cache_obj.daily_prices["dates"]
    prices_dict = cache_obj.daily_prices["prices"]

    if not dates:
        return {"dates": [], "series": []}

    df = pd.DataFrame(prices_dict, index=pd.to_datetime(dates))
    df.sort_index(inplace=True)

    last_dt = df.index[-1]
    if range_str == "1M":
        start_dt = last_dt - pd.DateOffset(months=1)
    elif range_str == "3M":
        start_dt = last_dt - pd.DateOffset(months=3)
    elif range_str == "6M":
        start_dt = last_dt - pd.DateOffset(months=6)
    elif range_str == "YTD":
        start_dt = pd.Timestamp(year=last_dt.year, month=1, day=1)
    elif range_str == "1Y":
        start_dt = last_dt - pd.DateOffset(years=1)
    elif range_str == "3Y":
        start_dt = last_dt - pd.DateOffset(years=3)
    elif range_str == "5Y":
        start_dt = last_dt - pd.DateOffset(years=5)
    elif range_str == "10Y":
        start_dt = last_dt - pd.DateOffset(years=10)
    elif range_str == "MAX":
        start_dt = pd.Timestamp("2000-01-01")
    else:
        start_dt = last_dt - pd.DateOffset(years=1)

    df_filtered = df[df.index >= start_dt].copy()
    if df_filtered.empty:
        df_filtered = df.copy()

    # Downsample if range is long to keep chart performance super fast
    # If more than 500 rows, resample to weekly or bi-weekly
    if len(df_filtered) > 600:
        step = max(1, len(df_filtered) // 350)
        df_filtered = df_filtered.iloc[::step].copy()

    if not selected_tickers:
        selected_tickers = ["XLK", "XLF", "XLE", "SMH", "SPY"]

    tickers_to_include = list(set(selected_tickers + [benchmark]))
    valid_tickers = [t for t in tickers_to_include if t in df_filtered.columns]

    normalized_df = pd.DataFrame(index=df_filtered.index)
    for t in valid_tickers:
        s = df_filtered[t].dropna()
        if not s.empty and s.iloc[0] > 0:
            p0 = s.iloc[0]
            normalized_df[t] = (df_filtered[t] / p0) * 100.0
            normalized_df[f"{t}_pct"] = ((df_filtered[t] / p0) - 1.0) * 100.0

    if benchmark in normalized_df.columns:
        benchmark_norm = normalized_df[benchmark]
        for t in valid_tickers:
            if t != benchmark and t in normalized_df.columns:
                ratio = (normalized_df[t] / benchmark_norm) * 100.0
                normalized_df[f"{t}_ratio_{benchmark}"] = ratio

    records = []
    for dt, row in normalized_df.iterrows():
        pt = {"date": dt.strftime("%Y-%m-%d")}
        for col in normalized_df.columns:
            val = row[col]
            pt[col] = sanitize_val(val)
        records.append(pt)

    return {
        "range": range_str,
        "benchmark": benchmark,
        "start_date": df_filtered.index[0].strftime("%Y-%m-%d"),
        "end_date": df_filtered.index[-1].strftime("%Y-%m-%d"),
        "data": records
    }
