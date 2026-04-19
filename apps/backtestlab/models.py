from django.db import models
from django.utils import timezone
from apps.botops.models import BotAsset

class BacktestResult(models.Model):
    bot_asset = models.ForeignKey(BotAsset, on_delete=models.CASCADE, related_name='backtests')
    period = models.CharField(max_length=20) # e.g. 'all', '5y', '1y', '1q'
    created_at = models.DateTimeField(default=timezone.now)
    
    # Store aggregated scalar metrics
    metrics = models.JSONField(null=True, blank=True)
    
    # Store distributions and raw result metrics like arrays of trade returns
    distributions = models.JSONField(null=True, blank=True)
    
    # Equity curve representations
    equity_curve = models.JSONField(null=True, blank=True)
    bh_curve = models.JSONField(null=True, blank=True)
    drawdown_curve = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f"{self.bot_asset.bot.name} - {self.bot_asset.asset} - {self.period} - {self.created_at.date()}"
