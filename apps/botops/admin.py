from django.contrib import admin
from .models import Family, Bot, BotAsset, AssetSeries, Broker, GeneralSettings, Transaction, PortfolioHistory

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'date', 'bot', 'assetbot', 'capital', 'add_withdraw', 'previous_capital_added', 'posterior_capital_added')
    search_fields = ('bot__name', 'assetbot__asset')
    list_filter = ('date', 'add_withdraw', 'bot')

@admin.register(Family)
class FamilyAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'active', 'folder')
    search_fields = ('name', 'folder')
    list_filter = ('active',)

@admin.register(Bot)
class BotAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'family', 'strategy_type', 'active','cap_no_asignado', 'execute_minute', 'summer_operate_hour', 'winter_operate_hour')
    search_fields = ('name', 'folder', 'family__name')
    list_filter = ('active', 'family')

@admin.register(BotAsset)
class BotAssetAdmin(admin.ModelAdmin):
    list_display = ('id', 'asset','bot', 'operate', 'broker', 'qty_open', 'cap_to_trade', 'cap_value_in_trade', 'pnl_un')
    search_fields = ('asset', 'broker', 'bot__name')
    list_filter = ('operate', 'broker', 'bot__name', 'bot__family')

@admin.register(AssetSeries)
class AssetSeriesAdmin(admin.ModelAdmin):
    list_display = ('id', 'ticker', 'ochl_last_update')
    search_fields = ('ticker',)

@admin.register(Broker)
class BrokerAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'coms')
    search_fields = ('name',)

    
@admin.register(GeneralSettings)
class GeneralSettingsAdmin(admin.ModelAdmin):
    list_display = ('id', 'summer', 'start_hour', 'end_hour')
    search_fields = ('summer', 'start_hour', 'end_hour')

@admin.register(PortfolioHistory)
class PortfolioHistoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'date', 'bot', 'capital', 'log_cum_sum', 'ret_cums', 'cagr', 'spy_price', 'spy_ret', 'spy_log_cum_sum', 'qqq_price', 'qqq_ret', 'qqq_log_cum_sum')
    list_editable = ('capital', 'log_cum_sum', 'ret_cums', 'cagr', 'spy_price', 'spy_ret', 'spy_log_cum_sum', 'qqq_price', 'qqq_ret', 'qqq_log_cum_sum')
    search_fields = ('bot__name',)
    list_filter = ('date', 'bot')
    ordering = ('-date',)
