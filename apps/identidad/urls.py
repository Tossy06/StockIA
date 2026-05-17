from django.urls import path
from . import views

app_name = "identidad"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("registro/", views.registro_view, name="registro"),
    path("configuracion/", views.configuracion_view, name="configuracion"),
]
