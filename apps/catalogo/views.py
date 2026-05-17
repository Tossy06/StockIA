from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from . import services


@login_required
def lista_view(request):
    productos = services.listar_productos()
    return render(request, "catalogo/lista.html", {"productos": productos})


@login_required
def detalle_view(request, producto_id):
    try:
        producto = services.obtener_producto(producto_id)
    except Exception:
        messages.error(request, "Producto no encontrado.")
        return redirect("catalogo:lista")
    return render(request, "catalogo/detalle.html", {"producto": producto})


@login_required
def form_view(request, producto_id=None):
    categorias = services.listar_categorias()
    producto = None

    if producto_id:
        try:
            producto = services.obtener_producto(producto_id)
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
        }
        try:
            if producto_id:
                services.actualizar_producto(producto_id, datos)
                messages.success(request, "Producto actualizado.")
            else:
                services.crear_producto(datos)
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
        services.eliminar_producto(producto_id)
        messages.success(request, "Producto eliminado.")
    return redirect("catalogo:lista")


@login_required
def categoria_view(request):
    if request.method == "POST":
        nombre = request.POST.get("nombre", "").strip()
        if nombre:
            services.crear_categoria(nombre)
            messages.success(request, f"Categoría '{nombre}' creada.")
        return redirect("catalogo:lista")
    return render(request, "catalogo/lista.html")
