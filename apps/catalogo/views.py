import json
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from . import services


@login_required
def lista_view(request):
    qs = services.listar_productos(request.user)
    productos_list = list(qs)
    productos_json = json.dumps([
        {
            "pk": p.pk,
            "nombre": p.nombre,
            "categoria": p.categoria.nombre,
            "precio": str(p.precio_unitario),
            "stock_actual": p.stock_actual,
            "stock_minimo": p.stock_minimo,
            "estado_stock": p.estado_stock,
            "imagen_url": p.imagen.url if p.imagen else "",
        }
        for p in productos_list
    ], ensure_ascii=False)
    return render(request, "catalogo/lista.html", {
        "total": len(productos_list),
        "productos_json": productos_json,
    })


@login_required
def detalle_view(request, producto_id):
    try:
        producto = services.obtener_producto(producto_id, request.user)
    except Exception:
        messages.error(request, "Producto no encontrado.")
        return redirect("catalogo:lista")
    return render(request, "catalogo/detalle.html", {"producto": producto})


@login_required
def form_view(request, producto_id=None):
    categorias = services.listar_categorias(request.user)
    producto = None

    if producto_id:
        try:
            producto = services.obtener_producto(producto_id, request.user)
        except Exception:
            messages.error(request, "Producto no encontrado.")
            return redirect("catalogo:lista")

    if request.method == "POST":
        datos = {
            "nombre": request.POST.get("nombre"),
            "categoria_id": request.POST.get("categoria_id"),
            "precio_unitario": request.POST.get("precio_unitario"),
            "stock_actual": request.POST.get("stock_actual"),
            "stock_minimo": request.POST.get("stock_minimo"),
            "imagen": request.FILES.get("imagen"),
            "borrar_imagen": request.POST.get("borrar_imagen") == "1",
        }
        try:
            if producto_id:
                services.actualizar_producto(producto_id, datos, request.user)
                messages.success(request, "Producto actualizado.")
            else:
                services.crear_producto(datos, request.user)
                messages.success(request, "Producto creado.")
            return redirect("catalogo:lista")
        except Exception as e:
            messages.error(request, f"Error al guardar: {e}")

    return render(request, "catalogo/form.html", {
        "producto": producto,
        "categorias": categorias,
    })


@login_required
def eliminar_view(request, producto_id):
    if request.method == "POST":
        services.eliminar_producto(producto_id, request.user)
        messages.success(request, "Producto eliminado.")
    return redirect("catalogo:lista")


@login_required
@require_POST
def categoria_view(request):
    nombre = request.POST.get("nombre", "").strip()
    if not nombre:
        return JsonResponse({"error": "El nombre no puede estar vacío."}, status=400)
    cat = services.crear_categoria(nombre, request.user)
    return JsonResponse({"pk": cat.pk, "nombre": cat.nombre})


@login_required
def categorias_lista_view(request):
    categorias = services.listar_categorias_con_conteo(request.user)
    return render(request, "catalogo/categorias.html", {"categorias": categorias})


@login_required
@require_POST
def categoria_editar_view(request, categoria_id):
    nombre = request.POST.get("nombre", "").strip()
    if not nombre:
        return JsonResponse({"error": "El nombre no puede estar vacío."}, status=400)
    try:
        cat = services.renombrar_categoria(categoria_id, nombre, request.user)
        return JsonResponse({"pk": cat.pk, "nombre": cat.nombre})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=404)


@login_required
@require_POST
def categoria_eliminar_view(request, categoria_id):
    services.eliminar_categoria(categoria_id, request.user)
    return JsonResponse({"ok": True})
