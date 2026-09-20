from rest_framework import serializers
from .models import Family, Bot, BotAsset, AssetSeries, Broker, TradeHistory

class BrokerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Broker
        fields = '__all__'

class TradeHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = TradeHistory
        fields = '__all__'

class BotAssetSerializer(serializers.ModelSerializer):
    trade_histories = TradeHistorySerializer(many=True, read_only=True)

    class Meta:
        model = BotAsset
        fields = '__all__'

class BotSerializer(serializers.ModelSerializer):
    assets = BotAssetSerializer(many=True, read_only=True)

    class Meta:
        model = Bot
        fields = '__all__'

class FamilySerializer(serializers.ModelSerializer):
    bots = BotSerializer(many=True, read_only=True)

    class Meta:
        model = Family
        fields = '__all__'

class AssetSeriesSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetSeries
        fields = '__all__'

