from django.db import models
from django.contrib.auth.models import User
from cryptography.fernet import Fernet


class PerfilTendero(models.Model):

    class Proveedor(models.TextChoices):
        CLAUDE = "claude", "Claude (Anthropic)"
        GEMINI = "gemini", "Gemini (Google)"
        GROQ = "groq", "Groq"
        OLLAMA = "ollama", "Ollama (Local)"

    usuario = models.OneToOneField(User, on_delete=models.CASCADE)
    proveedor = models.CharField(
        max_length=20, choices=Proveedor.choices, default=Proveedor.GEMINI
    )
    api_key_cifrada = models.BinaryField(null=True, blank=True)

    class Meta:
        verbose_name = "Perfil Tendero"
        verbose_name_plural = "Perfiles Tenderos"

    def __str__(self):
        return self.usuario.username

    def guardar_api_key(self, api_key_texto: str, fernet: Fernet):
        self.api_key_cifrada = fernet.encrypt(api_key_texto.encode())
        self.save()

    def obtener_api_key(self, fernet: Fernet) -> str | None:
        if not self.api_key_cifrada:
            return None
        return fernet.decrypt(bytes(self.api_key_cifrada)).decode()

    def tiene_api_key(self) -> bool:
        return bool(self.api_key_cifrada)
