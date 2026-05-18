import json
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from . import services


@login_required
def chat_view(request):
    historial_raw = services.obtener_historial(request.user)
    # Pre-serializar datos_grafica a JSON válido para evitar repr de Python en el template
    historial = [
        {
            "pk": m.pk,
            "rol": m.rol,
            "contenido": m.contenido,
            "tipo_respuesta": m.tipo_respuesta,
            "datos_grafica": m.datos_grafica,
            "datos_grafica_json": json.dumps(m.datos_grafica, default=str) if m.datos_grafica else "null",
        }
        for m in historial_raw
    ]
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
def historial_view(request):
    mensajes = services.obtener_historial(request.user)
    return JsonResponse({
        "mensajes": [
            {
                "rol": m.rol,
                "contenido": m.contenido,
                "tipo_respuesta": m.tipo_respuesta,
                "datos_grafica": m.datos_grafica,
            }
            for m in mensajes
        ]
    })


@login_required
@require_POST
def limpiar_view(request):
    from .models import Conversacion
    Conversacion.objects.filter(usuario=request.user).delete()
    if request.headers.get('Accept') == 'application/json':
        return JsonResponse({"ok": True})
    return redirect("inteligencia:chat")
