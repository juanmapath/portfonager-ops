from rest_framework import viewsets
from rest_framework.permissions import AllowAny
from .models import BacktestResult
from .serializers import BacktestResultSerializer

class BacktestResultViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows backtest results to be viewed.
    """
    serializer_class = BacktestResultSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        queryset = BacktestResult.objects.all().order_by('-created_at')
        bot_asset_id = self.request.query_params.get('bot_asset')
        period = self.request.query_params.get('period')
        
        if bot_asset_id:
            queryset = queryset.filter(bot_asset_id=bot_asset_id)
        if period:
            queryset = queryset.filter(period=period)
            
        return queryset
