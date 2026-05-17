from django.contrib import admin
from .models import Venta, LineaVenta


class LineaVentaInline(admin.TabularInline):
    model = LineaVenta
    extra = 0
    readonly_fields = ["precio_unitario"]


@admin.register(Venta)
class VentaAdmin(admin.ModelAdmin):
    list_display = ["pk", "fecha", "total"]
    readonly_fields = ["fecha", "total"]
    inlines = [LineaVentaInline]
