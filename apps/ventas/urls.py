from django.urls import path
from . import views

app_name = "ventas"

urlpatterns = [
    path("", views.lista_view, name="lista"),
]
