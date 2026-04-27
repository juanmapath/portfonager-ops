import sys
from pathlib import Path
from django.utils import timezone

import os
import django

root_directory = Path(__file__).resolve().parent.parent.parent.parent
bot_directory = root_directory / "bot"
if str(root_directory) not in sys.path:
    sys.path.append(str(root_directory))
if str(bot_directory) not in sys.path:
    sys.path.append(str(bot_directory))

#os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
#django.setup()

from apps.botops.models import GeneralSettings, Bot, BotAsset
from apps.botops.ops.tgrm import send_to_telegram
from apps.botops.ops.bot_catalog import bots_functions

def run_bot(family_id, bot_id, current_hour=None, force_operate=None):
    """
    Centralized function to execute a bot.
    - current_hour: used to determine if it's the 'last' hour of operation.
    - force_operate: if True/False, overrides the 'last' hour logic.
    """
    if current_hour is None:
        current_hour = timezone.localtime().hour
        
    general_settings = GeneralSettings.objects.get(id=1)
    summer = general_settings.summer
    start_hour = general_settings.start_hour
    end_hour = general_settings.end_hour
        
    # Validation logic (only if not forced)
    if force_operate is None:
        current_weekday = timezone.localtime().weekday()
        if current_weekday >= 5:
            return "Skipped: Weekend"
            
        if not (start_hour <= current_hour <= end_hour):
            return f"Skipped: Outside hours ({current_hour})"
        
    try:
        bot_obj = Bot.objects.get(id=bot_id, family__id=family_id)
    except Bot.DoesNotExist:
        return f"Error: Bot {bot_id} not found"
        
    assets_to_trade = BotAsset.objects.filter(bot__family__id=family_id, bot__id=bot_id, operate=True)
    type_strategy = bot_obj.strategy_type

    # Determine operate hour based on summer setting
    if summer:
        last = bot_obj.summer_operate_hour
    else:
        last = bot_obj.winter_operate_hour
    
    apiToken = bot_obj.tg_key1
    chatID = bot_obj.tg_key2
    message = ""
    
    # Determine operation mode
    should_operate = force_operate if force_operate is not None else (current_hour == last)
    
    if type_strategy in bots_functions:
        for asset in assets_to_trade:
            message += bots_functions[type_strategy](asset, operate=should_operate)
        
        if message and apiToken and chatID:
            send_to_telegram(message,apiToken,chatID)
            return "Success"
        return "No message generated or credentials missing"
    
    return f"Strategy {type_strategy} not found in catalog"


def run_bot_force(family_id, bot_id, operate=False):
    """
    Force executes a bot without applying any timezone, weekend, or schedule checks.
    Used for manual triggering from API endpoints.
    """
    try:
        bot_obj = Bot.objects.get(id=bot_id, family__id=family_id)
    except Bot.DoesNotExist:
        return f"Error: Bot {bot_id} not found"
        
    assets_to_trade = BotAsset.objects.filter(bot__family__id=family_id, bot__id=bot_id, operate=True)
    type_strategy = bot_obj.strategy_type
    
    apiToken = bot_obj.tg_key1
    chatID = bot_obj.tg_key2
    message = ""
    
    if type_strategy in bots_functions:
        for asset in assets_to_trade:
            message += bots_functions[type_strategy](asset, operate=operate)
        
        if message and apiToken and chatID:
            send_to_telegram(message,apiToken,chatID)
            return "Success"
        return "No message generated or credentials missing"
    
    return f"Strategy {type_strategy} not found in catalog"



if __name__ == "__main__":
    
    run_bot_force(1,8)