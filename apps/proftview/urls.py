from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    BotAssetViewSet, BotViewSet, FamilyViewSet, BrokerViewSet, 
    BotAssetAggregatedView, AddCapitalToBotNoAsignView, AddRemoveCapitalToAssetView,
    LoginView, VerifyTokenView, PortfolioHistoryView, ClosePositionView
)

router = DefaultRouter()
router.register(r'assets', BotAssetViewSet)
router.register(r'bots', BotViewSet)
router.register(r'families', FamilyViewSet)
router.register(r'brokers', BrokerViewSet)

urlpatterns = [
    path('assets/aggregated/', BotAssetAggregatedView.as_view(), name='asset-aggregated'),
    path('assets/add-remove-capital/', AddRemoveCapitalToAssetView.as_view(), name='add-remove-capital'),
    path('bot/add-capital/', AddCapitalToBotNoAsignView.as_view(), name='add-capital-to-bot'),
    path('assets/close-position/', ClosePositionView.as_view(), name='close-position'),
    path('history/', PortfolioHistoryView.as_view(), name='portfolio-history'),
    path('auth/login/', LoginView.as_view(), name='auth-login'),
    path('auth/verify/', VerifyTokenView.as_view(), name='auth-verify'),
    path('', include(router.urls)),
]
