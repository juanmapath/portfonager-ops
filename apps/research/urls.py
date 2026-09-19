from django.urls import path
from apps.research.views import (
    ScreenerSummaryView,
    ScreenerRefreshView,
    ScreenerTimeSeriesView
)

urlpatterns = [
    path('screener/summary/', ScreenerSummaryView.as_view(), name='screener_summary'),
    path('screener/refresh/', ScreenerRefreshView.as_view(), name='screener_refresh'),
    path('screener/timeseries/', ScreenerTimeSeriesView.as_view(), name='screener_timeseries'),
]
