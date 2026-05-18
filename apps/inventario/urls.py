from django.urls import path
from . import views

app_name = "inventario"

urlpatterns = [
    path("", views.dashboard_view, name="dashboard"),
    path("graficas/", views.crear_grafica_view, name="crear_grafica"),
    path("graficas/<int:pk>/eliminar/", views.eliminar_grafica_view, name="eliminar_grafica"),
    path("vistas/", views.guardar_vista_view, name="guardar_vista"),
    path("vistas/historial/", views.historial_vistas_view, name="historial_vistas"),
]
