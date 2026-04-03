from django.db import models

class GemScrapperTactics(models.Model):
    name = models.CharField(max_length=255)
    active = models.BooleanField(default=True)
    params = models.JSONField(null=True, blank=True)
    market_cap_category = models.CharField(max_length=255, default="all")
    overall_weights = models.JSONField(null=True, blank=True)
    value_weights = models.JSONField(null=True, blank=True)
    quality_weights = models.JSONField(null=True, blank=True)
    trend_weights = models.JSONField(null=True, blank=True) # New field

    def __str__(self):
        return self.name


class ScrapingSession(models.Model):
    tactic = models.ForeignKey(GemScrapperTactics, on_delete=models.CASCADE, related_name='sessions')
    date_executed = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=50, default="completed") # processing, completed, failed

    def __str__(self):
        return f"{self.tactic.name} - {self.date_executed.strftime('%Y-%m-%d %H:%M')}"


class SelectedAsset(models.Model):
    session = models.ForeignKey(ScrapingSession, on_delete=models.CASCADE, related_name='assets')
    ticker = models.CharField(max_length=255)
    company_name = models.CharField(max_length=255)
    sector = models.CharField(max_length=255, null=True, blank=True)
    industry = models.CharField(max_length=255, null=True, blank=True)
    country = models.CharField(max_length=255, null=True, blank=True)
    market_cap = models.CharField(max_length=255, null=True, blank=True)
    
    score = models.FloatField(default=0.0, null=True, blank=True)
    raw_metrics = models.JSONField(null=True, blank=True) # Stores PE, ROA, ROE, P/FCF, industry_averages, etc.

    def __str__(self):
        return f"{self.ticker} ({self.session.date_executed.strftime('%Y-%m-%d')})"


class CompetitorAsset(models.Model):
    target_asset = models.ForeignKey(SelectedAsset, on_delete=models.CASCADE, related_name='competitors')
    ticker = models.CharField(max_length=255)
    company_name = models.CharField(max_length=255)
    raw_metrics = models.JSONField(null=True, blank=True) # ALL detailed metrics (ROE, PE, etc) specifically for this competitor

    def __str__(self):
        return f"Competitor: {self.ticker} of {self.target_asset.ticker}"