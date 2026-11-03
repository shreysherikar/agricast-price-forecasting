from django.contrib import admin
from .models import ForecastRun, ForecastPoint

class ForecastPointInline(admin.TabularInline):
    model = ForecastPoint
    extra = 0
    readonly_fields = ("month", "point", "lower_80", "upper_80", "lower_95", "upper_95")

@admin.register(ForecastRun)
class ForecastRunAdmin(admin.ModelAdmin):
    list_display = ("id", "origin", "model_version", "created_at")
    list_filter = ("model_version", "origin", "created_at")
    search_fields = ("origin", "model_version")
    inlines = [ForecastPointInline]

@admin.register(ForecastPoint)
class ForecastPointAdmin(admin.ModelAdmin):
    list_display = ("id", "run", "month", "point", "lower_80", "upper_80", "lower_95", "upper_95")
    list_filter = ("month", "run__origin")
    search_fields = ("month",)
