from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    path("", RedirectView.as_view(url="/identidad/login/"), name="home"),
    path("admin/", admin.site.urls),
    path("identidad/", include("apps.identidad.urls")),
    path("inventario/", include("apps.inventario.urls")),
    path("catalogo/", include("apps.catalogo.urls")),
    path("ventas/", include("apps.ventas.urls")),
    path("inteligencia/", include("apps.inteligencia.urls")),
]
