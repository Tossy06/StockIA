import json
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from . import services


@login_required
def chat_view(request):
    historial = services.obtener_historial(request.user)
    return render(request, "inteligencia/chat.html", {"historial": historial})


@login_required
@require_POST
def mensaje_view(request):
    try:
        datos = json.loads(request.body)
        texto = datos.get("texto", "").strip()
        if not texto:
            return JsonResponse({"error": "Mensaje vacío."}, status=400)
        respuesta = services.enviar_mensaje(request.user, texto)
        return JsonResponse(respuesta)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def limpiar_view(request):
    from .models import Conversacion
    Conversacion.objects.filter(usuario=request.user).delete()
    return redirect("inteligencia:chat")
