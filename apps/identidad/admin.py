from django.contrib import admin
from .models import PerfilTendero


@admin.register(PerfilTendero)
class PerfilTenderoAdmin(admin.ModelAdmin):
    list_display = ["usuario", "tiene_api_key"]
    search_fields = ["usuario__username"]
