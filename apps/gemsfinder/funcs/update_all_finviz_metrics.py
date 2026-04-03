import os
import sys
import time
from pathlib import Path

# Setup Django environment for standalone script
root_dir = Path(__file__).resolve().parent.parent.parent.parent
sys.path.append(str(root_dir))

this_dir = Path(__file__).resolve().parent
sys.path.append(str(this_dir))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
import django
django.setup()

# Import models and scraper function after Django is setup
from apps.botops.models import AssetSeries
from apps.gemsfinder.funcs.scrappers import update_finviz_metrics_series

def run_update():
    assets = AssetSeries.objects.all()
    total_assets = assets.count()
    
    if total_assets == 0:
        print("No AssetSeries instances found in the database. Exiting.")
        return

    print(f"Starting to update Finviz metrics for {total_assets} assets...")
    print("-" * 50)
    
    for i, asset in enumerate(assets, start=1):
        ticker = asset.ticker
        print(f"[{i}/{total_assets}] Processing {ticker}...")
        
        success, _ = update_finviz_metrics_series(ticker)
        
        if success:
            print(f"    ✔ Successfully updated data for {ticker}")
        else:
            print(f"    ✖ Failed to update data for {ticker}")
            
        # Add a sleep interval between requests to be polite to the Finviz API
        # and prevent being rate-limited.
        if i < total_assets:
            time.sleep(2)
            
    print("-" * 50)
    print("Update process completed.")

if __name__ == "__main__":
    run_update()
