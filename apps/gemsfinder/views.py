from rest_framework import generics, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django_q.tasks import async_task
from .models import GemScrapperTactics, SelectedAsset, CompetitorAsset, ScrapingSession
from .serializers import (
    GemScrapperTacticsSerializer, 
    SelectedAssetSerializer, 
    CompetitorAssetSerializer
)

class TacticListView(generics.ListAPIView):
    """
    Lista todas las tácticas de scraping disponibles.
    Cada táctica incluye el ID de su última sesión de scraping.
    """
    queryset = GemScrapperTactics.objects.all()
    serializer_class = GemScrapperTacticsSerializer
    permission_classes = [permissions.AllowAny] 

class SelectedAssetListView(generics.ListAPIView):
    """
    Lista los activos seleccionados filtrados por ID de sesión.
    Se ordena por score descendente (mayor a menor).
    """
    serializer_class = SelectedAssetSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        queryset = SelectedAsset.objects.all().order_by('-score')
        session_id = self.request.query_params.get('session')
        
        if session_id:
            queryset = queryset.filter(session_id=session_id)
            
        return queryset

class CompetitorAssetListView(generics.ListAPIView):
    """
    Lista los activos competidores filtrados por el ID del activo seleccionado (target).
    """
    serializer_class = CompetitorAssetSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        queryset = CompetitorAsset.objects.all()
        target_id = self.request.query_params.get('target_asset')
        
        if target_id:
            queryset = queryset.filter(target_asset_id=target_id)
            
        return queryset


class RunScreenerView(APIView):
    """
    Manually triggers the GemsFinder screener script for all active tactics.
    Restricted to admin (staff) users only.
    The script runs asynchronously in the background via Django-Q.
    """
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, *args, **kwargs):
        active_tactics = GemScrapperTactics.objects.filter(active=True)
        if not active_tactics.exists():
            return Response(
                {"detail": "No active tactics found. Nothing to run."},
                status=status.HTTP_400_BAD_REQUEST
            )

        task_id = async_task('apps.gemsfinder.funcs.run_sts.run_st')

        return Response(
            {
                "detail": "GemsFinder screener has been queued successfully.",
                "task_id": task_id,
                "active_tactics": list(active_tactics.values_list('name', flat=True)),
            },
            status=status.HTTP_202_ACCEPTED
        )
