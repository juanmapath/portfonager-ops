from rest_framework import serializers
from .models import GemScrapperTactics, ScrapingSession, SelectedAsset, CompetitorAsset

class GemScrapperTacticsSerializer(serializers.ModelSerializer):
    latest_session_id = serializers.SerializerMethodField()

    class Meta:
        model = GemScrapperTactics
        fields = [
            'id', 'name', 'active', 'params', 'market_cap_category',
            'overall_weights', 'value_weights', 'quality_weights', 'trend_weights',
            'latest_session_id'
        ]

    def get_latest_session_id(self, obj):
        # Obtener el ID de la sesión más reciente para esta táctica
        latest_session = obj.sessions.order_by('-date_executed').first()
        return latest_session.id if latest_session else None

class SelectedAssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = SelectedAsset
        fields = '__all__'

class CompetitorAssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompetitorAsset
        fields = '__all__'
