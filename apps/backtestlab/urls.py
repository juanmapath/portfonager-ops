from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import BacktestResultViewSet

router = DefaultRouter()
router.register(r'results', BacktestResultViewSet, basename='backtest-results')

urlpatterns = [
    path('', include(router.urls)),
]
