"""
Serializers for forecasting API responses.
"""
from rest_framework import serializers
from .models import ForecastRun, ForecastPoint


class ForecastPointSerializer(serializers.ModelSerializer):
    class Meta:
        model = ForecastPoint
        fields = [
            "month",
            "point",
            "lower_80",
            "upper_80",
            "lower_95",
            "upper_95",
        ]


class ForecastRunSerializer(serializers.ModelSerializer):
    points = ForecastPointSerializer(many=True, read_only=True)
    stale = serializers.BooleanField(default=False)

    class Meta:
        model = ForecastRun
        fields = [
            "id",
            "created_at",
            "model_version",
            "origin",
            "stale",
            "points",
        ]


class LatestForecastResponseSerializer(serializers.Serializer):
    """Structured response schema for GET /api/forecast/latest/"""
    run_id = serializers.IntegerField(allow_null=True)
    created_at = serializers.DateTimeField(allow_null=True)
    model_version = serializers.CharField()
    origin = serializers.CharField()
    stale = serializers.BooleanField()
    source = serializers.CharField()
    points = ForecastPointSerializer(many=True)
