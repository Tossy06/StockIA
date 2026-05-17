from django.contrib import admin
from .models import Categoria, Producto


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ["nombre"]
    search_fields = ["nombre"]


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ["nombre", "categoria", "precio_unitario", "stock_actual", "stock_minimo", "activo"]
    list_filter = ["categoria", "activo"]
    search_fields = ["nombre"]
    list_editable = ["stock_actual", "activo"]
