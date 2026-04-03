import sys
import time
import os 
import json
import requests
from pathlib import Path
from datetime import datetime

import pandas as pd
import numpy as np
from numpy import clip

root_dir = Path(__file__).resolve().parent.parent.parent.parent
sys.path.append(str(root_dir))

this_dir = Path(__file__).resolve().parent
sys.path.append(str(this_dir))

# Configurar Django para usar ORM en script independiente
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
import django
django.setup()

from apps.gemsfinder.models import GemScrapperTactics, ScrapingSession, SelectedAsset, CompetitorAsset
from apps.gemsfinder.funcs.scrappers import scrap_finviz_screener, scrap_finviz_screener_costum

def safe_float(value):
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def score_metrics_all(metrics: dict, market_cap_category: str) -> dict:
    thresholds = {
        "large": {
            "price_per_earnings": (10, 40),
            "price_per_fcf": (10, 40),
            "price_per_book": (1, 6),
            "price_per_cash": (2, 15),
            "roa": (2, 15),
            "roe": (5, 25),
            "quick_ratio": (0.8, 2.5),
            "oper_margin": (5, 25),
            "profit_margin": (5, 25),
            "insider_ownership": (0.5, 5),
        },
        "mid": {
            "price_per_earnings": (8, 35),
            "price_per_fcf": (8, 35),
            "price_per_book": (0.8, 5),
            "price_per_cash": (1.5, 12),
            "roa": (3, 18),
            "roe": (7, 28),
            "quick_ratio": (0.8, 2.5),
            "oper_margin": (5, 20),
            "profit_margin": (5, 20),
            "insider_ownership": (1, 10),
        },
        "small": {
            "price_per_earnings": (6, 30),
            "price_per_fcf": (6, 30),
            "price_per_book": (0.5, 4),
            "price_per_cash": (1, 10),
            "roa": (4, 20),
            "roe": (10, 35),
            "quick_ratio": (0.6, 2.5),
            "oper_margin": (3, 18),
            "profit_margin": (3, 18),
            "insider_ownership": (2, 15),
        },
        "all": {
            "price_per_earnings": (8, 35),
            "price_per_fcf": (8, 35),
            "price_per_book": (0.8, 5),
            "price_per_cash": (1.5, 12),
            "roa": (3, 18),
            "roe": (7, 28),
            "quick_ratio": (0.8, 2.5),
            "oper_margin": (5, 20),
            "profit_margin": (5, 20),
            "insider_ownership": (1, 10),
        },
    }

    def score_val_metric(value, best, worst):
        val = safe_float(value)
        if val is None:
            return 0
        return clip((worst - val) / (worst - best), 0, 1)

    def score_growth_metric(value, worst, best):
        val = safe_float(value)
        if val is None:
            return 0
        return clip((val - worst) / (best - worst), 0, 1)

    if market_cap_category not in thresholds:
        market_cap_category = "all"

    t = thresholds[market_cap_category]
    scores = {}

    for metric, value in metrics.items():
        if metric in t:
            best, worst = t[metric]
            if "price" in metric:
                scores[metric] = round(score_val_metric(value, best, worst), 3)
            else:
                scores[metric] = round(score_growth_metric(value, worst, best), 3)
        else:
            scores[metric] = None

    return scores


def total_portfolio_score(scores: dict, tactic: GemScrapperTactics):
    # Overall Weights
    overall = tactic.overall_weights or {}
    w_val = float(overall.get("value", 0.4))
    w_qual = float(overall.get("quality", 0.4))
    w_trend = float(overall.get("trend", 0.2))

    # Metric Groups Weights from DB
    val_w = tactic.value_weights or {"price_per_earnings": 1, "price_per_book": 1, "price_per_cash": 1, "price_per_fcf": 2}
    qual_w = tactic.quality_weights or {"roa": 1, "roe": 1, "quick_ratio": 1, "oper_margin": 2, "profit_margin": 1, "insider_ownership": 1, "insider_trans": 1}
    trend_w = tactic.trend_weights or {} 

    # Normalize group weights
    val_tot = sum(float(v) for v in val_w.values()) or 1
    val_w = {k: float(v)/val_tot for k, v in val_w.items()}
    
    qual_tot = sum(float(v) for v in qual_w.values()) or 1
    qual_w = {k: float(v)/qual_tot for k, v in qual_w.items()}

    trend_tot = sum(float(v) for v in trend_w.values()) or 1
    trend_w = {k: float(v)/trend_tot for k, v in trend_w.items()} if trend_w else {}

    # Compute Group Scores
    val_score = sum((scores.get(k) or 0) * val_w.get(k, 0) for k in val_w)
    qual_score = sum((scores.get(k) or 0) * qual_w.get(k, 0) for k in qual_w)
    trend_score = sum((scores.get(k) or 0) * trend_w.get(k, 0) for k in trend_w)

    total = w_val * val_score + w_qual * qual_score + w_trend * trend_score
    return round(total, 4)


def compare_industry(industry):
    industry_filter_parse = industry.lower().replace(" ","").replace("&","").replace("-","")
    filters_list = {"Industry": industry_filter_parse}

    df_compare = scrap_finviz_screener_costum(filters_list, True)
    if df_compare is False or df_compare.empty:
        return pd.DataFrame()

    columns_to_convert = ['price_per_fcf', 'price_per_earnings', 'price_per_book', 'roe', 'oper_margin', 'debt_to_quity', 'sales_growth_qoq', 'sales_growth_yoy']
    for col in columns_to_convert:
        if col in df_compare.columns:
            df_compare[col] = pd.to_numeric(df_compare[col], errors='coerce')
    
    # Calculate industry medians
    df_cleaned = df_compare.dropna(subset=[col for col in ['price_per_fcf', 'price_per_earnings', 'price_per_book', 'roe', 'oper_margin', 'debt_to_quity'] if col in df_compare.columns]).copy()
    if df_cleaned.empty:
        return df_cleaned

    df_cleaned["priceToFCF_avg"] = df_cleaned.get("price_per_fcf", pd.Series(dtype=float)).median()
    df_cleaned["priceToEarn_avg"] = df_cleaned.get("price_per_earnings", pd.Series(dtype=float)).median()
    df_cleaned["priceToBook_avg"] = df_cleaned.get("price_per_book", pd.Series(dtype=float)).median()
    df_cleaned["roe_avg"] = df_cleaned.get("roe", pd.Series(dtype=float)).median()
    df_cleaned["oper_margin_avg"] = df_cleaned.get("oper_margin", pd.Series(dtype=float)).median()
    df_cleaned["debt_equity_avg"] = df_cleaned.get("debt_to_quity", pd.Series(dtype=float)).median()
    df_cleaned["sales_growth_qoq_avg"] = df_cleaned.get("sales_growth_qoq", pd.Series(dtype=float)).median()
    df_cleaned["sales_growth_yoy_avg"] = df_cleaned.get("sales_growth_yoy", pd.Series(dtype=float)).median()

    return df_cleaned


def run_st():
    tactics = GemScrapperTactics.objects.filter(active=True)
    if not tactics.exists():
        print("No active tactics found in DB.")
        return

    for tactic in tactics:
        print(f"--- Running Tactic: {tactic.name} ---")
        params = tactic.params
        
        # Create a DB scraping session
        session = ScrapingSession.objects.create(tactic=tactic)

        asset_df = scrap_finviz_screener_costum(params)
        if asset_df is False or asset_df.empty:
            print("No assets found or error in finviz scraping.")
            session.status = "failed"
            session.save()
            continue

        asset_df['price_per_earnings'] = asset_df['price_per_earnings'].replace("-", np.nan)
        asset_df['price_per_book'] = asset_df['price_per_book'].replace("-", np.nan)
        asset_df['price_per_cash'] = asset_df['price_per_cash'].replace("-", np.nan)
        asset_df['price_per_fcf'] = asset_df['price_per_fcf'].replace("-", np.nan)
        asset_df['roa'] = asset_df['roa'].replace("-",  np.nan)   
        asset_df['roe'] = asset_df['roe'].replace("-",  np.nan)
        asset_df['quick_ratio'] = asset_df['quick_ratio'].replace("-",  np.nan)
        asset_df['oper_margin'] = asset_df['oper_margin'].replace("-",  np.nan)
        asset_df['profit_margin'] = asset_df['profit_margin'].replace("-",  np.nan)   

        asset_df['total_score'] = 0.0
        asset_df["priceToFCF_avg"] = 0.0
        asset_df["priceToEarn_avg"] = 0.0
        asset_df["priceToBook_avg"] = 0.0
        asset_df["roe_avg"] = 0.0
        asset_df["oper_margin_avg"] = 0.0
        asset_df["debt_equity_avg"] = 0.0
        asset_df["sales_growth_qoq_avg"] = 0.0
        asset_df["sales_growth_yoy_avg"] = 0.0

        unique_industries = asset_df["industry"].dropna().unique()
        competitor_dfs = []

        # Iterate over industries to fetch competitor details
        for industry in unique_industries:
            time.sleep(1)
            print(f"Fetching competitors for Industry: {industry}")
            compare_asset_df = compare_industry(industry)
            
            if compare_asset_df.empty:
                continue

            competitor_dfs.append(compare_asset_df)

            # Assign medians back to the main dataframe
            cols_to_update = ["priceToFCF_avg", "priceToEarn_avg", "priceToBook_avg", "roe_avg", "oper_margin_avg", "debt_equity_avg", "sales_growth_qoq_avg", "sales_growth_yoy_avg"]
            first_index = compare_asset_df.index[0]
            values_to_assign = compare_asset_df.loc[first_index, cols_to_update]

            industry_mask = asset_df["industry"] == industry
            for col in cols_to_update:
                asset_df.loc[industry_mask, col] = values_to_assign[col]

        # Combine competitors into one mapping df (avoids duplicating API calls or loops)
        competitors_pool = pd.concat(competitor_dfs, ignore_index=True) if competitor_dfs else pd.DataFrame()

        # Score final assets & Save to DB
        selected_instances = []
        for index, row in asset_df.iterrows():
            ticker = row["ticker"]
            metrics_to_score = {
                "price_per_earnings": row.get("price_per_earnings"),
                "price_per_book": row.get("price_per_book"),
                "price_per_cash": row.get("price_per_cash"),
                "price_per_fcf": row.get("price_per_fcf"),
                "roa": row.get("roa"),
                "roe": row.get("roe"),
                "quick_ratio": row.get("quick_ratio"),
                "oper_margin": row.get("oper_margin"),
                "profit_margin": row.get("profit_margin"),
                "insider_ownership": row.get("insider_ownership"),
                "insider_trans": row.get("insider_trans"),
            }
            
            scores = score_metrics_all(metrics_to_score, tactic.market_cap_category or "all")
            final_score = total_portfolio_score(scores, tactic)
            
            if final_score is None:
                final_score = 0.0
                
            asset_df.at[index, 'total_score'] = final_score

            # Raw metrics map to store in JSON
            raw_metrics = {k: str(v) for k, v in row.to_dict().items() if pd.notnull(v)}
            
            sa = SelectedAsset(
                session=session,
                ticker=ticker,
                company_name=row.get("company_name", ""),
                sector=row.get("sector", ""),
                industry=row.get("industry", ""),
                country=row.get("country", ""),
                market_cap=row.get("marketCap", ""),
                score=final_score,
                raw_metrics=raw_metrics
            )
            selected_instances.append(sa)

        # Bulk create for efficiency
        created_assets = SelectedAsset.objects.bulk_create(selected_instances)

        # Now link Competitors to the correct SelectedAsset
        if not competitors_pool.empty:
            competitor_instances = []
            for asset in created_assets:
                # Find competitors in the same industry
                industry_comps = competitors_pool[competitors_pool['industry'] == asset.industry]
                for _, comp_row in industry_comps.iterrows():
                    # We store all the individual metrics for the competitor in the json
                    comp_raw_metrics = {k: str(v) for k, v in comp_row.to_dict().items() if pd.notnull(v)}
                    
                    ci = CompetitorAsset(
                        target_asset=asset,
                        ticker=comp_row.get('ticker', ''),
                        company_name=comp_row.get('company_name', ''),
                        raw_metrics=comp_raw_metrics
                    )
                    competitor_instances.append(ci)
            
            CompetitorAsset.objects.bulk_create(competitor_instances)
            print(f"Saved {len(competitor_instances)} competitor records for this tactic.")

        print(f"Session {session.id} Completed! Saved {len(created_assets)} assets to DB.")

    print("All tactics processing finished.")


def run_continous():
    print("----")
    print("Running DB-backed GemsFinder Process")
    print("----")
    check_hours_we = 12
    check_minute_we = 30
    
    while True:
        current_time = time.localtime()
        weekday = current_time.tm_wday 
        hour = int(current_time.tm_hour)
        minute = int(current_time.tm_min)
        
        # Corre semanalmente, ejemplo: Sábados (5) a las 12:30
        if weekday == 5:
            if (hour == check_hours_we) and (minute == check_minute_we):
                print("Iniciando análisis semanal...")
                run_st()
            
        time.sleep(60)


if __name__ == "__main__":
    run_st()
