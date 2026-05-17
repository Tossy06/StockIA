import json
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from . import services


@login_required
def lista_view(request):
    ventas = services.listar_ventas()
    return render(request, "ventas/lista.html", {"ventas": ventas})


@login_required
def form_view(request):
    productos = services.listar_productos_activos()

    if request.method == "POST":
        try:
            lineas_json = request.POST.get("lineas", "[]")
            lineas = json.loads(lineas_json)
            if not lineas:
                messages.error(request, "Agrega al menos un producto a la venta.")
                return render(request, "ventas/form.html", {"productos": productos})
            venta = services.registrar_venta(lineas)
            messages.success(request, f"Venta #{venta.pk} registrada por ${venta.total}.")
            return redirect("ventas:lista")
        except ValueError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f"Error al registrar la venta: {e}")

    return render(request, "ventas/form.html", {"productos": productos})
