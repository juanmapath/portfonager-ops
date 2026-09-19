from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from apps.research.services.screener_engine import (
    get_screener_summary,
    update_screener_data,
    get_screener_timeseries
)

class ScreenerSummaryView(APIView):
    """
    Returns precalculated returns by periods, rankings, and Callan matrix.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, format=None):
        try:
            data = get_screener_summary()
            return Response(data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"error": f"Failed to retrieve screener summary: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ScreenerRefreshView(APIView):
    """
    Triggers batch download from Yahoo Finance, recalculates all metrics,
    updates DB cache, and returns the refreshed summary payload.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request, format=None):
        try:
            refreshed_data = update_screener_data()
            return Response(
                {
                    "success": True,
                    "message": "Screener data refreshed successfully from Yahoo Finance.",
                    "data": refreshed_data
                },
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {"success": False, "error": f"Failed to refresh screener data: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ScreenerTimeSeriesView(APIView):
    """
    Returns normalized timeseries and relative strength ratios for charting.
    Query params:
    - tickers: comma-separated list of tickers (e.g. 'XLK,XLF,XLE,SMH')
    - range: 1M, 3M, 6M, YTD, 1Y, 3Y (default: 1Y)
    - benchmark: SPY (default: SPY)
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, format=None):
        try:
            tickers_param = request.query_params.get('tickers', '')
            range_param = request.query_params.get('range', '1Y')
            benchmark_param = request.query_params.get('benchmark', 'SPY')

            selected_tickers = [t.strip().upper() for t in tickers_param.split(',') if t.strip()]
            data = get_screener_timeseries(
                selected_tickers=selected_tickers,
                range_str=range_param,
                benchmark=benchmark_param
            )
            return Response(data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"error": f"Failed to retrieve timeseries: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
