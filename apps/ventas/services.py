from django.db import transaction
from apps.catalogo.models import Producto
from .models import Venta, LineaVenta


def registrar_venta(lineas: list[dict], usuario) -> Venta:
    with transaction.atomic():
        venta = Venta.objects.create(usuario=usuario)
        total = 0
        for linea in lineas:
            producto = Producto.objects.select_for_update().get(
                pk=linea["producto_id"], usuario=usuario
            )
            if producto.stock_actual < linea["cantidad"]:
                raise ValueError(f"Stock insuficiente para {producto.nombre}")
            producto.stock_actual -= linea["cantidad"]
            producto.save()
            LineaVenta.objects.create(
                venta=venta,
                producto=producto,
                cantidad=linea["cantidad"],
                precio_unitario=producto.precio_unitario,
            )
            total += producto.precio_unitario * linea["cantidad"]
        venta.total = total
        venta.save()
        return venta


def listar_ventas(usuario):
    return Venta.objects.filter(usuario=usuario).prefetch_related("lineas__producto").order_by("-fecha")


def listar_productos_activos(usuario):
    return Producto.objects.filter(activo=True, usuario=usuario).select_related("categoria")
