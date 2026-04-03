from rest_framework import generics, permissions
from .models import GemScrapperTactics, SelectedAsset, CompetitorAsset
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
