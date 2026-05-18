from django.urls import path
from . import views

app_name = "catalogo"

urlpatterns = [
    path("", views.lista_view, name="lista"),
    path("nuevo/", views.form_view, name="nuevo"),
    path("<int:producto_id>/", views.detalle_view, name="detalle"),
    path("<int:producto_id>/editar/", views.form_view, name="editar"),
    path("<int:producto_id>/eliminar/", views.eliminar_view, name="eliminar"),
    path("categorias/", views.categorias_lista_view, name="categorias"),
    path("categorias/nueva/", views.categoria_view, name="categoria_nueva"),
    path("categorias/<int:categoria_id>/editar/", views.categoria_editar_view, name="categoria_editar"),
    path("categorias/<int:categoria_id>/eliminar/", views.categoria_eliminar_view, name="categoria_eliminar"),
]
