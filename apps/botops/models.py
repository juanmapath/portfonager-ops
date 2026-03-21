from django.db import models
from django.utils import timezone

class Family(models.Model):
    name = models.CharField(max_length=255)
    active = models.BooleanField(default=True)
    folder = models.CharField(max_length=255)

    def __str__(self):
        return self.name

class StrategyType(models.TextChoices):
    one_strategy = 'OneStrategy', 'OneStrategy'
    multi_strategy = 'MultiStrategy', 'MultiStrategy'
    follow_price = 'FollowPrice', 'FollowPrice'
    signal_dollar = 'SignalDollar', 'SignalDollar'
    signal_options = 'SignalOptions', 'SignalOptions'

class Bot(models.Model):
    family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name='bots')
    name = models.CharField(max_length=255)
    strategy_type = models.CharField(
        max_length=20,
        choices=StrategyType.choices,
        default=StrategyType.one_strategy
    )
    folder = models.CharField(max_length=255)
    execute_minute = models.IntegerField(default=55)
    summer_operate_hour = models.IntegerField(default=14)
    winter_operate_hour = models.IntegerField(default=13)
    active = models.BooleanField(default=True)
    capital_active = models.FloatField(default=0.0)
    cap_value = models.FloatField(default=0.0)
    cap_ingresado = models.FloatField(default=0.0)
    cap_no_asignado = models.FloatField(default=0.0)
    cap_to_add = models.FloatField(default=0.0)
    cap_retirado = models.FloatField(default=0.0)
    pnl_real = models.FloatField(default=0.0)
    pnl_unreal = models.FloatField(default=0.0)
    rets = models.FloatField(default=0.0)
    tg_key1 = models.CharField(max_length=255, null=True, blank=True)
    tg_key2 = models.CharField(max_length=255, null=True, blank=True)
    tp = models.FloatField(default=0.0)
    sl = models.FloatField(default=0.0)

    def __str__(self):
        return self.name

class Broker(models.Model):
    name = models.CharField(max_length=255)
    coms = models.FloatField(default=1)
    def __str__(self):
        return self.name

class BotAsset(models.Model):
    bot = models.ForeignKey(Bot, on_delete=models.CASCADE, related_name='assets')
    operate = models.BooleanField(default=True)
    asset = models.CharField(max_length=255)
    params1 = models.CharField(max_length=255, null=True, blank=True)
    params2 = models.CharField(max_length=255, null=True, blank=True)
    params3 = models.CharField(max_length=255, null=True, blank=True)
    alloc = models.FloatField(default=0.0)
    broker = models.ForeignKey(Broker, on_delete=models.CASCADE, related_name='assets',default=1)
    position = models.IntegerField(default=0)
    qty_open = models.FloatField(default=0.0)
    cap_to_trade = models.FloatField(default=0.0)
    cap_to_add = models.FloatField(default=0.0)
    cap_value_in_trade = models.FloatField(default=0.0)
    op_price = models.FloatField(default=0.0)
    last_price = models.FloatField(default=0.0)
    pnl_un = models.FloatField(default=0.0)
    capAdded = models.FloatField(default=0.0)
    PNL = models.FloatField(default=0.0)
    trades = models.FloatField(default=0.0)
    coms = models.FloatField(default=0.0)
    created_date = models.DateField(default=timezone.now, null=True, blank=True)
    updated_date = models.DateField(null=True, blank=True)
    stats1 = models.JSONField(null=True, blank=True)
    stats2 = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f"{self.bot.name} - {self.asset} - {self.id}"


class AssetSeries(models.Model):
    ticker = models.CharField(max_length=255)
    ochl = models.JSONField(null=True, blank=True)
    ochl_last_update = models.DateTimeField(null=True, blank=True)
    ochl_history = models.JSONField(null=True, blank=True)

class GeneralSettings(models.Model):
    summer = models.BooleanField(default=True)
    start_hour = models.IntegerField(default=8)
    end_hour = models.IntegerField(default=16)
    
class Transaction(models.Model):
    bot = models.ForeignKey(Bot, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    assetbot = models.ForeignKey(BotAsset, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    previous_capital_added = models.FloatField(default=0.0, null=True, blank=True)
    posterior_capital_added = models.FloatField(default=0.0, null=True, blank=True)
    capital = models.FloatField(default=0.0)
    add_withdraw = models.IntegerField(default=1)
    date = models.DateField(null=True, blank=True)
    broker = models.ForeignKey(Broker, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')

    def __str__(self):
        return f"{self.date} - {self.capital}"
