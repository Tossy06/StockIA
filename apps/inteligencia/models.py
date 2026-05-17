from django.db import models
from django.contrib.auth.models import User


class Conversacion(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Conversación"
        verbose_name_plural = "Conversaciones"
        ordering = ["-creada_en"]

    def __str__(self):
        return f"Conversación {self.pk} — {self.usuario.username}"


class Mensaje(models.Model):
    class Rol(models.TextChoices):
        USUARIO = "usuario", "Usuario"
        ASISTENTE = "asistente", "Asistente"

    conversacion = models.ForeignKey(
        Conversacion, on_delete=models.CASCADE, related_name="mensajes"
    )
    rol = models.CharField(max_length=20, choices=Rol.choices)
    contenido = models.TextField()
    tipo_respuesta = models.CharField(max_length=20, default="texto")
    datos_grafica = models.JSONField(null=True, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Mensaje"
        verbose_name_plural = "Mensajes"
        ordering = ["creado_en"]

    def __str__(self):
        return f"{self.rol}: {self.contenido[:50]}"
