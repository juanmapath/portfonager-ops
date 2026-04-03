import sys
from pathlib import Path
import pandas as pd

# Add the project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))

from apps.gemsfinder.funcs.run_sts import compare_industry

if __name__ == "__main__":
    industry = "Biotechnology"
    print(f"Testing compare_industry for: {industry}")
    
    df = compare_industry(industry)
    
    if not df.empty:
        print("\nTest successful!")
        print(f"Columns in result: {df.columns.tolist()}")
        print("\nIndustry Averages (Medians):")
        avg_cols = [col for col in df.columns if "_avg" in col]
        for col in avg_cols:
            print(f"{col}: {df[col].iloc[0]}")
    else:
        print("\nTest failed or no results.")
