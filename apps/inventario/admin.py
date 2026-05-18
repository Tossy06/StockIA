from django.contrib import admin
from .models import GraficaDashboard, VistaDashboard


@admin.register(GraficaDashboard)
class GraficaDashboardAdmin(admin.ModelAdmin):
    list_display = ("titulo", "usuario", "fuente", "tipo", "query_key", "creado_en")
    list_filter = ("fuente", "tipo", "usuario")
    search_fields = ("titulo", "query_key")
    readonly_fields = ("creado_en",)


@admin.register(VistaDashboard)
class VistaDashboardAdmin(admin.ModelAdmin):
    list_display = ("nombre", "usuario", "creado_en")
    list_filter = ("usuario",)
    readonly_fields = ("creado_en",)
