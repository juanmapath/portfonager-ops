from django.contrib import admin
from apps.gemsfinder.models import GemScrapperTactics, ScrapingSession, SelectedAsset, CompetitorAsset

@admin.register(GemScrapperTactics)
class GemScrapperTacticsAdmin(admin.ModelAdmin):
    list_display = ('name', 'active', 'market_cap_category')
    search_fields = ('name',)
    list_filter = ('active', 'market_cap_category')

@admin.register(ScrapingSession)
class ScrapingSessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'tactic', 'date_executed', 'status')
    list_filter = ('status', 'tactic')

@admin.register(SelectedAsset)
class SelectedAssetAdmin(admin.ModelAdmin):
    list_display = ('ticker', 'company_name', 'session', 'score', 'industry')
    search_fields = ('ticker', 'company_name')
    list_filter = ('session__tactic', 'sector', 'industry')

""" @admin.register(CompetitorAsset)
class CompetitorAssetAdmin(admin.ModelAdmin):
    list_display = ('ticker', 'target_asset', 'company_name')
    search_fields = ('ticker', 'company_name')
 """