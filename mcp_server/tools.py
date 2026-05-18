import os
import django

if not django.conf.settings.configured:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
    django.setup()

from django.db.models import Sum, F
from django.utils import timezone
from apps.catalogo.models import Producto
from apps.ventas.models import Venta, LineaVenta


def obtener_stock_critico(usuario=None) -> list[dict]:
    qs = Producto.objects.filter(activo=True)
    if usuario is not None:
        qs = qs.filter(usuario=usuario)
    return [
        {
            "nombre": p.nombre,
            "stock_actual": p.stock_actual,
            "stock_minimo": p.stock_minimo,
        }
        for p in qs if p.estado_stock == "critico"
    ]


def obtener_ventas_por_periodo(inicio: str, fin: str, usuario=None) -> list[dict]:
    qs = Venta.objects.filter(fecha__date__range=[inicio, fin])
    if usuario is not None:
        qs = qs.filter(usuario=usuario)
    return list(
        qs.values("fecha__date")
        .annotate(total=Sum("total"))
        .order_by("fecha__date")
    )


def obtener_top_productos(limite=5, periodo: str = "mes", usuario=None) -> list[dict]:
    limite = int(limite)
    hoy = timezone.now()
    if periodo == "dia":
        desde = hoy.replace(hour=0, minute=0, second=0, microsecond=0)
    elif periodo == "semana":
        desde = hoy - timezone.timedelta(days=hoy.weekday())
        desde = desde.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        desde = hoy.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    qs = LineaVenta.objects.filter(venta__fecha__gte=desde)
    if usuario is not None:
        qs = qs.filter(venta__usuario=usuario)
    return list(
        qs.values(nombre=F("producto__nombre"))
        .annotate(total_vendido=Sum("cantidad"))
        .order_by("-total_vendido")[:limite]
    )


def obtener_ingresos(periodo: str = "mes", usuario=None) -> dict:
    hoy = timezone.now()
    if periodo == "dia":
        desde = hoy.replace(hour=0, minute=0, second=0, microsecond=0)
    elif periodo == "semana":
        desde = hoy - timezone.timedelta(days=hoy.weekday())
        desde = desde.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        desde = hoy.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    qs = Venta.objects.filter(fecha__gte=desde)
    if usuario is not None:
        qs = qs.filter(usuario=usuario)
    total = qs.aggregate(t=Sum("total"))["t"] or 0
    return {"periodo": periodo, "total": float(total)}


def obtener_resumen_negocio(usuario=None) -> dict:
    qs = Producto.objects.filter(activo=True)
    if usuario is not None:
        qs = qs.filter(usuario=usuario)
    productos = list(qs)
    return {
        "total_productos": len(productos),
        "stock_normal": sum(1 for p in productos if p.estado_stock == "normal"),
        "stock_bajo": sum(1 for p in productos if p.estado_stock == "bajo"),
        "stock_critico": sum(1 for p in productos if p.estado_stock == "critico"),
        "ingresos_hoy": obtener_ingresos("dia", usuario)["total"],
        "ingresos_mes": obtener_ingresos("mes", usuario)["total"],
        "top_productos": obtener_top_productos(5, "mes", usuario),
    }


HERRAMIENTAS_MAP = {
    "obtener_stock_critico": obtener_stock_critico,
    "obtener_ventas_por_periodo": obtener_ventas_por_periodo,
    "obtener_top_productos": obtener_top_productos,
    "obtener_ingresos": obtener_ingresos,
    "obtener_resumen_negocio": obtener_resumen_negocio,
}


def ejecutar_herramienta(nombre: str, argumentos: dict, usuario=None):
    fn = HERRAMIENTAS_MAP.get(nombre)
    if fn is None:
        return {"error": f"Herramienta '{nombre}' no encontrada."}
    return fn(usuario=usuario, **(argumentos or {}))
