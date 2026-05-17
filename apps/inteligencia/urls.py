from django.urls import path
from . import views

app_name = "inteligencia"

urlpatterns = [
    path("", views.chat_view, name="chat"),
    path("mensaje/", views.mensaje_view, name="mensaje"),
    path("limpiar/", views.limpiar_view, name="limpiar"),
]
