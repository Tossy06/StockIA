from django.urls import path
from . import views

app_name = "catalogo"

urlpatterns = [
    path("", views.lista_view, name="lista"),
    path("nuevo/", views.form_view, name="nuevo"),
    path("<int:producto_id>/", views.detalle_view, name="detalle"),
    path("<int:producto_id>/editar/", views.form_view, name="editar"),
    path("<int:producto_id>/eliminar/", views.eliminar_view, name="eliminar"),
    path("categorias/nueva/", views.categoria_view, name="categoria_nueva"),
]
