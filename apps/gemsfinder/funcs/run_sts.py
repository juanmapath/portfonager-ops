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
from apps.botops.models import AssetSeries
from apps.gemsfinder.funcs.scrappers import scrap_finviz_screener, scrap_finviz_screener_costum, update_finviz_metrics_series

def safe_float(value):
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def compute_trends(fin_series):
    def extract_metric(series, key, index):
        try:
            if not series or key not in series: return None
            val_list = series[key]
            if index >= len(val_list): return None
            val = str(val_list[index]).replace(",", "")
            return float(val) if val else None
        except (IndexError, ValueError, TypeError):
            return None

    # We use index 1 (latest FY), index 2 (1 year prior), index 4 (3 years prior)
    rev_1 = extract_metric(fin_series, "Total Revenue", 1)
    rev_2 = extract_metric(fin_series, "Total Revenue", 2)
    rev_4 = extract_metric(fin_series, "Total Revenue", 4)
    
    op_m_1 = extract_metric(fin_series, "Operating Margin", 1)
    op_m_4 = extract_metric(fin_series, "Operating Margin", 4)
    
    ebitda_1 = extract_metric(fin_series, "EBITDA", 1)
    ebitda_2 = extract_metric(fin_series, "EBITDA", 2)
    
    rev_accel = np.nan
    if rev_1 and rev_2 and rev_4 and rev_2 > 0 and rev_4 > 0:
        yoy = (rev_1 / rev_2) - 1
        cagr3 = (rev_1 / rev_4) ** (1/3) - 1
        rev_accel = yoy - cagr3
        
    margin_expansion = np.nan
    if op_m_1 is not None and op_m_4 is not None:
        margin_expansion = op_m_1 - op_m_4
        
    ebitda_growth = np.nan
    if ebitda_1 and ebitda_2 and ebitda_2 > 0:
        ebitda_growth = (ebitda_1 / ebitda_2) - 1
        
    return rev_accel, margin_expansion, ebitda_growth


def total_portfolio_score(scores: dict, tactic: GemScrapperTactics):
    # Overall Weights
    overall = tactic.overall_weights or {}
    w_val = float(overall.get("value", 0.4))
    w_qual = float(overall.get("quality", 0.4))
    w_trend = float(overall.get("trend", 0.2))

    # Metric Groups Weights from DB
    val_w = tactic.value_weights or {"price_per_earnings": 1, "price_per_book": 1, "price_per_cash": 1, "price_per_fcf": 2}
    qual_w = tactic.quality_weights or {"roic": 2, "roa": 1, "roe": 1, "quick_ratio": 1, "oper_margin": 2, "profit_margin": 1, "insider_ownership": 1, "insider_trans": 1}
    trend_w = tactic.trend_weights or {"rev_accel": 2, "margin_expansion": 1, "ebitda_growth": 1} 

    # Normalize group weights
    val_tot = sum(float(v) for v in val_w.values()) or 1
    val_w = {k: float(v)/val_tot for k, v in val_w.items()}
    
    qual_tot = sum(float(v) for v in qual_w.values()) or 1
    qual_w = {k: float(v)/qual_tot for k, v in qual_w.items()}

    trend_tot = sum(float(v) for v in trend_w.values()) or 1
    trend_w = {k: float(v)/trend_tot for k, v in trend_w.items()} if trend_w else {}

    # Compute Group Scores
    val_score = sum((scores.get(f"{k}_score") or 0) * val_w.get(k, 0) for k in val_w)
    qual_score = sum((scores.get(f"{k}_score") or 0) * qual_w.get(k, 0) for k in qual_w)
    trend_score = sum((scores.get(f"{k}_score") or 0) * trend_w.get(k, 0) for k in trend_w)

    total = w_val * val_score + w_qual * qual_score + w_trend * trend_score
    return round(total, 4)


def compare_industry(industry):
    industry_filter_parse = industry.lower().replace(" ","").replace("&","").replace("-","")
    filters_list = {"Industry": industry_filter_parse}

    df_compare = scrap_finviz_screener_costum(filters_list, True)
    if df_compare is False or df_compare.empty:
        return pd.DataFrame()

    columns_to_convert = ['price_per_fcf', 'price_per_earnings', 'price_per_book', 'price_per_sales', 'roe', 'oper_margin', 'debt_to_quity', 'sales_growth_qoq', 'sales_growth_yoy']
    for col in columns_to_convert:
        if col in df_compare.columns:
            df_compare[col] = pd.to_numeric(df_compare[col], errors='coerce')
    
    # Calculate industry medians
    df_cleaned = df_compare.dropna(subset=[col for col in ['price_per_fcf', 'price_per_earnings', 'price_per_book', 'roe', 'oper_margin', 'debt_to_quity'] if col in df_compare.columns]).copy()
    if df_cleaned.empty:
        return df_cleaned

    df_cleaned["priceToSales_avg"] = df_cleaned.get("price_per_sales", pd.Series(dtype=float)).median()
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
        asset_df['price_per_sales'] = asset_df.get('price_per_sales', pd.Series(dtype=float)).replace("-", np.nan)
        asset_df['price_per_cash'] = asset_df['price_per_cash'].replace("-", np.nan)
        asset_df['price_per_fcf'] = asset_df['price_per_fcf'].replace("-", np.nan)
        asset_df['roa'] = asset_df['roa'].replace("-",  np.nan)   
        asset_df['roe'] = asset_df['roe'].replace("-",  np.nan)
        asset_df['roic'] = asset_df.get('roic', pd.Series(dtype=float)).replace("-",  np.nan)
        asset_df['quick_ratio'] = asset_df['quick_ratio'].replace("-",  np.nan)
        asset_df['oper_margin'] = asset_df['oper_margin'].replace("-",  np.nan)
        asset_df['profit_margin'] = asset_df['profit_margin'].replace("-",  np.nan)
        asset_df['earnings_date'] = asset_df.get('earnings_date', pd.Series(dtype=str)).replace("-",  np.nan)
        asset_df['insider_ownership'] = asset_df.get('insider_ownership', pd.Series(dtype=float)).replace("-",  np.nan)
        asset_df['insider_trans'] = asset_df.get('insider_trans', pd.Series(dtype=float)).replace("-",  np.nan)

        asset_df['total_score'] = 0.0
        asset_df["priceToSales_avg"] = 0.0
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
            cols_to_update = ["priceToSales_avg", "priceToFCF_avg", "priceToEarn_avg", "priceToBook_avg", "roe_avg", "oper_margin_avg", "debt_equity_avg", "sales_growth_qoq_avg", "sales_growth_yoy_avg"]
            first_index = compare_asset_df.index[0]
            values_to_assign = compare_asset_df.loc[first_index, cols_to_update]

            industry_mask = asset_df["industry"] == industry
            for col in cols_to_update:
                asset_df.loc[industry_mask, col] = values_to_assign[col]

        # Combinar competidores
        competitors_pool = pd.concat(competitor_dfs, ignore_index=True) if competitor_dfs else pd.DataFrame()

        # ====================
        # TREND METRICS (Only for asset_df to preserve requests)
        # ====================
        print("Fetching Financial Statements for Trend Analysis...")
        asset_df["rev_accel"] = np.nan
        asset_df["margin_expansion"] = np.nan
        asset_df["ebitda_growth"] = np.nan
        
        for idx, row in asset_df.iterrows():
            ticker = row["ticker"]
            print(f"Scraping Trend Metrics for {ticker}...")
            success, merged_data = update_finviz_metrics_series(ticker)
            if success and merged_data:
                r_accel, m_exp, ebitda_g = compute_trends(merged_data)
                asset_df.at[idx, "rev_accel"] = r_accel
                asset_df.at[idx, "margin_expansion"] = m_exp
                asset_df.at[idx, "ebitda_growth"] = ebitda_g
            time.sleep(1.5)  # Rate limiting
            
        # ====================
        # CROSS-SECTIONAL RANKING (Percentiles)
        # ====================
        print("Scoring assets using cross-sectional percentiles...")
        if not competitors_pool.empty:
            full_universe = pd.concat([asset_df, competitors_pool]).drop_duplicates(subset=['ticker']).copy()
        else:
            full_universe = asset_df.copy()
            
        val_metrics = ["price_per_earnings", "price_per_book", "price_per_sales", "price_per_cash", "price_per_fcf"]
        qual_metrics = ["roa", "roe", "roic", "quick_ratio", "oper_margin", "profit_margin", "insider_ownership", "insider_trans"]
        trend_metrics = ["rev_accel", "margin_expansion", "ebitda_growth"]
        
        numeric_cols = val_metrics + qual_metrics + trend_metrics
        for col in numeric_cols:
            if col in full_universe.columns:
                full_universe[col] = pd.to_numeric(full_universe[col], errors='coerce')
            if col in asset_df.columns:
                asset_df[col] = pd.to_numeric(asset_df[col], errors='coerce')

        # Compute Value & Quality percentiles on full_universe 
        # (smaller is better for Value metrics -> ascending=False for rank)
        for col in val_metrics:
            if col in full_universe.columns:
                full_universe[f"{col}_score"] = full_universe[col].rank(pct=True, ascending=False)
        for col in qual_metrics:
            if col in full_universe.columns:
                full_universe[f"{col}_score"] = full_universe[col].rank(pct=True, ascending=True)
                
        # Map Value/Quality scores back to asset_df
        for col in val_metrics + qual_metrics:
            score_col = f"{col}_score"
            if score_col in full_universe.columns:
                score_map = full_universe.set_index('ticker')[score_col].to_dict()
                asset_df[score_col] = asset_df['ticker'].map(score_map)
                
        # Rank Trend ONLY within asset_df
        for col in trend_metrics:
            if col in asset_df.columns:
                asset_df[f"{col}_score"] = asset_df[col].rank(pct=True, ascending=True)

        # Score final assets & Save to DB
        selected_instances = []
        for index, row in asset_df.iterrows():
            ticker = row["ticker"]
            
            # Recolectar scores
            scores_map = {}
            for col in val_metrics + qual_metrics + trend_metrics:
                scores_map[f"{col}_score"] = row.get(f"{col}_score", 0.0)
            
            final_score = total_portfolio_score(scores_map, tactic)
            
            if final_score is None or pd.isna(final_score):
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
