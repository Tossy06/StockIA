import json
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from . import services


@login_required
def dashboard_view(request):
    resumen  = services.obtener_resumen_dashboard(request.user)
    graficas = services.obtener_graficas_dashboard(request.user)
    return render(request, "inventario/dashboard.html", {
        "resumen":  resumen,
        "graficas": graficas,
        "graficas_json": json.dumps(graficas, default=str),
    })


@login_required
@require_POST
def crear_grafica_view(request):
    try:
        data = json.loads(request.body)
        resultado, error = services.crear_grafica_ia(request.user, data)
        if error:
            return JsonResponse({"error": error}, status=400)
        return JsonResponse(resultado)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@require_POST
def eliminar_grafica_view(request, pk):
    eliminada = services.eliminar_grafica(request.user, pk)
    if not eliminada:
        return JsonResponse({"error": "Gráfica no encontrada."}, status=404)
    return JsonResponse({"ok": True})


@login_required
@require_POST
def guardar_vista_view(request):
    try:
        data     = json.loads(request.body)
        graficas = data.get("graficas", [])
        vista    = services.guardar_vista_dashboard(request.user, graficas)
        return JsonResponse({"pk": vista.pk, "nombre": vista.nombre})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def historial_vistas_view(request):
    vistas = services.obtener_vistas_historial(request.user)
    return JsonResponse({
        "vistas": [
            {
                "pk":        v.pk,
                "nombre":    v.nombre,
                "creado_en": v.creado_en.strftime("%d/%m/%Y %H:%M"),
                "graficas":  v.graficas,
            }
            for v in vistas
        ]
    })
