from django.db import models
from django.contrib.auth.models import User


class GraficaDashboard(models.Model):
    class Fuente(models.TextChoices):
        DEFAULT = "default", "Por defecto"
        IA = "ia", "Generada por IA"

    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name="graficas_dashboard")
    fuente = models.CharField(max_length=10, choices=Fuente.choices, default=Fuente.DEFAULT)
    titulo = models.CharField(max_length=200)
    tipo = models.CharField(max_length=20, default="bar")
    query_key = models.CharField(max_length=100, null=True, blank=True)
    query_params = models.JSONField(default=dict)
    labels = models.JSONField(null=True, blank=True)
    datos = models.JSONField(null=True, blank=True)
    orden = models.IntegerField(default=0)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["orden", "creado_en"]

    def __str__(self):
        return f"{self.titulo} ({self.fuente})"


class VistaDashboard(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name="vistas_dashboard")
    nombre = models.CharField(max_length=200)
    graficas = models.JSONField()
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado_en"]

    def __str__(self):
        return f"{self.nombre} — {self.usuario.username}"
