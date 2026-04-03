from django.urls import path
from .views import TacticListView, SelectedAssetListView, CompetitorAssetListView

urlpatterns = [
    path('tactics/', TacticListView.as_view(), name='tactic-list'),
    path('assets/', SelectedAssetListView.as_view(), name='selected-asset-list'),
    path('competitors/', CompetitorAssetListView.as_view(), name='competitor-asset-list'),
]
