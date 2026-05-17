from django.contrib import admin
from .models import Conversacion, Mensaje


class MensajeInline(admin.TabularInline):
    model = Mensaje
    extra = 0
    readonly_fields = ["rol", "contenido", "tipo_respuesta", "creado_en"]


@admin.register(Conversacion)
class ConversacionAdmin(admin.ModelAdmin):
    list_display = ["pk", "usuario", "creada_en"]
    readonly_fields = ["creada_en"]
    inlines = [MensajeInline]
