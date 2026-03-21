from rest_framework import serializers
from apps.botops.models import Family, Bot, Broker, BotAsset

class FamilySerializer(serializers.ModelSerializer):
    class Meta:
        model = Family
        fields = '__all__'

class BotSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bot
        fields = '__all__'

class BrokerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Broker
        fields = '__all__'

class BotAssetSerializer(serializers.ModelSerializer):
    # Optional: Include nested or related data for clarity
    bot_name = serializers.ReadOnlyField(source='bot.name')
    family_name = serializers.ReadOnlyField(source='bot.family.name')
    broker_name = serializers.ReadOnlyField(source='broker.name')

    class Meta:
        model = BotAsset
        fields = '__all__'
