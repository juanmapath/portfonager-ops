from rest_framework import serializers
from .models import BacktestResult

class BacktestResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = BacktestResult
        fields = '__all__'
