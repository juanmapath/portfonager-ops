import sys
from pathlib import Path
from datetime import datetime, timedelta
import numpy as np
from django.utils import timezone
from django.db.models import Sum, Q

root_directory = Path(__file__).resolve().parent.parent.parent.parent
if str(root_directory) not in sys.path:
    sys.path.append(str(root_directory))

import django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
try:
    django.setup()

except Exception:
    pass

from apps.botops.models import Bot, BotAsset, PortfolioHistory
from apps.botops.ops.bot_catalog import check_last_ohlc_and_download_data

def fetch_latest_price(symbol):
    try:
        df = check_last_ohlc_and_download_data(symbol, None, None)
        if df is not None and not df.empty:
            return float(df['Close'].iloc[-1])
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
    return None


def calculate_log_return(current_val, prev_val):
    if not prev_val or prev_val <= 0 or current_val <= 0:
        return 0.0
    return float(np.log(current_val / prev_val))

def calculate_cagr(start_date, current_date, ret_cums):
    if not start_date or not current_date:
        return 0.0
    days_diff = (current_date - start_date).days
    if days_diff > 0:
        return float(((1 + ret_cums/100)**(365.25/days_diff) - 1) * 100)
    return 0.0

def process_bot_history(bot, date_today, spy_price, qqq_price, cap_total):
    last_record = PortfolioHistory.objects.filter(bot=bot).order_by('-date').first()
    
    spy_ret = 0.0
    qqq_ret = 0.0
    spy_log_cum_sum = 0.0
    spy_ret_cums = 0.0
    qqq_log_cum_sum = 0.0
    qqq_ret_cums = 0.0
    log_cum_sum = 0.0
    ret_cums = 0.0
    cagr = 0.0
    
    if last_record and last_record.capital > 0:
        chg_log = calculate_log_return(cap_total, last_record.capital)
        log_cum_sum = last_record.log_cum_sum + chg_log
        ret_cums = 100 * (np.exp(log_cum_sum) - 1)
        
        if last_record.spy_price and spy_price:
            spy_ret = calculate_log_return(spy_price, last_record.spy_price)
            spy_log_cum_sum = last_record.spy_log_cum_sum + spy_ret
            spy_ret_cums = 100 * (np.exp(spy_log_cum_sum) - 1)
        else:
            spy_log_cum_sum = last_record.spy_log_cum_sum
            spy_ret_cums = last_record.spy_ret_cums

        if last_record.qqq_price and qqq_price:
            qqq_ret = calculate_log_return(qqq_price, last_record.qqq_price)
            qqq_log_cum_sum = last_record.qqq_log_cum_sum + qqq_ret
            qqq_ret_cums = 100 * (np.exp(qqq_log_cum_sum) - 1)
        else:
            qqq_log_cum_sum = last_record.qqq_log_cum_sum
            qqq_ret_cums = last_record.qqq_ret_cums
            
        first_record = PortfolioHistory.objects.filter(bot=bot).order_by('date').first()
        if first_record:
            cagr = calculate_cagr(first_record.date, date_today, ret_cums)
            
    PortfolioHistory.objects.create(
        date=date_today,
        bot=bot,
        capital=cap_total,
        log_cum_sum=log_cum_sum,
        ret_cums=ret_cums,
        cagr=cagr,
        spy_price=spy_price,
        spy_ret=spy_ret,
        spy_log_cum_sum=spy_log_cum_sum,
        spy_ret_cums=spy_ret_cums,
        qqq_price=qqq_price,
        qqq_ret=qqq_ret,
        qqq_log_cum_sum=qqq_log_cum_sum,
        qqq_ret_cums=qqq_ret_cums
    )

def all_bots_hist():
    date_today = timezone.now().date()
    if PortfolioHistory.objects.filter(date=date_today, bot=None).exists():
        print(f"History for {date_today} already computed. Skipping.")
        return
        
    spy_price = fetch_latest_price("SPY")
    qqq_price = fetch_latest_price("QQQ")
    
    print(f"[{date_today}] SPY: {spy_price}, QQQ: {qqq_price}")

    queryset = BotAsset.objects.all()
    aggs = queryset.aggregate(
        cap_to_add_sum=Sum('cap_to_add'),
        cap_value_in_trade_sum=Sum('cap_value_in_trade', filter=~Q(qty_open=0)),
        cap_to_trade_sum=Sum('cap_to_trade', filter=Q(qty_open=0))
    )
    
    cap_to_add_sum = aggs['cap_to_add_sum'] or 0.0
    cap_value_in_trade_sum = aggs['cap_value_in_trade_sum'] or 0.0
    cap_to_trade_sum = aggs['cap_to_trade_sum'] or 0.0
    
    cap_no_asignado_sum = Bot.objects.aggregate(
        cap_no_asignado_sum=Sum('cap_no_asignado')
    )['cap_no_asignado_sum'] or 0.0
    
    total_cap_value = cap_value_in_trade_sum + cap_no_asignado_sum + cap_to_trade_sum + cap_to_add_sum
    
    process_bot_history(None, date_today, spy_price, qqq_price, total_cap_value)
    print(f"Global History saved. Total Cap: {total_cap_value}")
    
    bots = Bot.objects.filter(active=True)
    for bot in bots:
        bot_aggs = BotAsset.objects.filter(bot=bot).aggregate(
            cap_to_add_sum=Sum('cap_to_add'),
            cap_value_in_trade_sum=Sum('cap_value_in_trade', filter=~Q(qty_open=0)),
            cap_to_trade_sum=Sum('cap_to_trade', filter=Q(qty_open=0))
        )
        b_cap_to_add = bot_aggs['cap_to_add_sum'] or 0.0
        b_cap_in_trade = bot_aggs['cap_value_in_trade_sum'] or 0.0
        b_cap_to_trade = bot_aggs['cap_to_trade_sum'] or 0.0
        
        bot_total_cap = b_cap_in_trade + b_cap_to_trade + b_cap_to_add + bot.cap_no_asignado
        
        process_bot_history(bot, date_today, spy_price, qqq_price, bot_total_cap)
        print(f"Bot '{bot.name}' History saved. Total Cap: {bot_total_cap}")

if __name__ == '__main__':
    all_bots_hist()
