from django.utils import timezone
from django.db.models import Sum, F
from apps.catalogo.models import Producto
from apps.ventas.models import Venta, LineaVenta


def obtener_resumen_dashboard() -> dict:
    hoy = timezone.now()
    inicio_dia = hoy.replace(hour=0, minute=0, second=0, microsecond=0)
    inicio_semana = inicio_dia - timezone.timedelta(days=hoy.weekday())
    inicio_mes = hoy.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    ingresos_dia = Venta.objects.filter(fecha__gte=inicio_dia).aggregate(
        total=Sum("total"))["total"] or 0
    ingresos_semana = Venta.objects.filter(fecha__gte=inicio_semana).aggregate(
        total=Sum("total"))["total"] or 0
    ingresos_mes = Venta.objects.filter(fecha__gte=inicio_mes).aggregate(
        total=Sum("total"))["total"] or 0

    productos = Producto.objects.filter(activo=True)
    stock_normal = sum(1 for p in productos if p.estado_stock == "normal")
    stock_bajo = sum(1 for p in productos if p.estado_stock == "bajo")
    stock_critico = sum(1 for p in productos if p.estado_stock == "critico")

    top_productos = (
        LineaVenta.objects
        .values(nombre=F("producto__nombre"))
        .annotate(total_vendido=Sum("cantidad"))
        .order_by("-total_vendido")[:5]
    )

    ultimas_ventas = Venta.objects.prefetch_related("lineas__producto").order_by("-fecha")[:10]

    return {
        "ingresos_dia": ingresos_dia,
        "ingresos_semana": ingresos_semana,
        "ingresos_mes": ingresos_mes,
        "stock_normal": stock_normal,
        "stock_bajo": stock_bajo,
        "stock_critico": stock_critico,
        "top_productos": list(top_productos),
        "ultimas_ventas": ultimas_ventas,
    }


def obtener_productos_por_estado(estado: str):
    return [p for p in Producto.objects.filter(activo=True) if p.estado_stock == estado]
