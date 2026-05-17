import os
import django

if not django.conf.settings.configured:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
    django.setup()

from django.db.models import Sum, F
from django.utils import timezone
from apps.catalogo.models import Producto
from apps.ventas.models import Venta, LineaVenta


def obtener_stock_critico() -> list[dict]:
    productos = Producto.objects.filter(activo=True)
    return [
        {
            "nombre": p.nombre,
            "stock_actual": p.stock_actual,
            "stock_minimo": p.stock_minimo,
        }
        for p in productos if p.estado_stock == "critico"
    ]


def obtener_ventas_por_periodo(inicio: str, fin: str) -> list[dict]:
    return list(
        Venta.objects.filter(fecha__date__range=[inicio, fin])
        .values("fecha__date")
        .annotate(total=Sum("total"))
        .order_by("fecha__date")
    )


def obtener_top_productos(limite: int = 5, periodo: str = "mes") -> list[dict]:
    hoy = timezone.now()
    if periodo == "dia":
        desde = hoy.replace(hour=0, minute=0, second=0, microsecond=0)
    elif periodo == "semana":
        desde = hoy - timezone.timedelta(days=hoy.weekday())
        desde = desde.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        desde = hoy.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return list(
        LineaVenta.objects.filter(venta__fecha__gte=desde)
        .values(nombre=F("producto__nombre"))
        .annotate(total_vendido=Sum("cantidad"))
        .order_by("-total_vendido")[:limite]
    )


def obtener_ingresos(periodo: str = "mes") -> dict:
    hoy = timezone.now()
    if periodo == "dia":
        desde = hoy.replace(hour=0, minute=0, second=0, microsecond=0)
    elif periodo == "semana":
        desde = hoy - timezone.timedelta(days=hoy.weekday())
        desde = desde.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        desde = hoy.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    total = Venta.objects.filter(fecha__gte=desde).aggregate(t=Sum("total"))["t"] or 0
    return {"periodo": periodo, "total": float(total)}


def obtener_resumen_negocio() -> dict:
    productos = list(Producto.objects.filter(activo=True))
    return {
        "total_productos": len(productos),
        "stock_normal": sum(1 for p in productos if p.estado_stock == "normal"),
        "stock_bajo": sum(1 for p in productos if p.estado_stock == "bajo"),
        "stock_critico": sum(1 for p in productos if p.estado_stock == "critico"),
        "ingresos_hoy": obtener_ingresos("dia")["total"],
        "ingresos_mes": obtener_ingresos("mes")["total"],
        "top_productos": obtener_top_productos(5, "mes"),
    }


HERRAMIENTAS_MAP = {
    "obtener_stock_critico": obtener_stock_critico,
    "obtener_ventas_por_periodo": obtener_ventas_por_periodo,
    "obtener_top_productos": obtener_top_productos,
    "obtener_ingresos": obtener_ingresos,
    "obtener_resumen_negocio": obtener_resumen_negocio,
}


def ejecutar_herramienta(nombre: str, argumentos: dict):
    fn = HERRAMIENTAS_MAP.get(nombre)
    if fn is None:
        return {"error": f"Herramienta '{nombre}' no encontrada."}
    return fn(**argumentos)
