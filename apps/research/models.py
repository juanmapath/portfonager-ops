from django.db import models

class SectorScreenerCache(models.Model):
    key = models.CharField(max_length=100, unique=True, default="default_screener")
    last_updated = models.DateTimeField(auto_now=True)
    tickers_list = models.JSONField(default=list, blank=True)
    summary_data = models.JSONField(null=True, blank=True)
    daily_prices = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f"SectorScreenerCache ({self.key}) - {self.last_updated}"
