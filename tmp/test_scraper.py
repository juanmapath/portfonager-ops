import sys
import os
import pandas as pd

# Add the project root to sys.path
sys.path.append(r'c:\Users\juanm\WorkSpace\portfonager-ops')

from apps.gemsfinder.funcs.scrappers import scrap_finviz_screener_costum

if __name__ == "__main__":
    # Sample filters
    params = {
        "ROIC": "o10",
        "PEG": "u2",
    }
    
    print("Starting test scrap...")
    df = scrap_finviz_screener_costum(params, top=True)
    
    if not df.empty:
        print("\nScraping successful!")
        print(f"Number of rows: {len(df)}")
        print("\nColumns:")
        print(df.columns.tolist())
        print("\nFirst 5 rows:")
        print(df.head())
    else:
        print("\nScraping failed or no results.")
