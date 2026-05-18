from datetime import timedelta
from django.utils import timezone
from django.db.models import Sum
from apps.catalogo.models import Producto
from apps.ventas.models import Venta
from .models import GraficaDashboard, VistaDashboard

LIMITE_GRAFICAS = 10
LIMITE_VISTAS   = 20

QUERY_EXTRACTORS = {
    "obtener_top_productos": lambda r: (
        [p["nombre"] for p in r],
        [int(p["total_vendido"]) for p in r],
    ),
    "obtener_ventas_por_periodo": lambda r: (
        [str(p["fecha__date"]) for p in r],
        [float(p["total"]) for p in r],
    ),
    "obtener_ingresos": lambda r: (
        [r.get("periodo", "")],
        [float(r.get("total", 0))],
    ),
    "obtener_stock_critico": lambda r: (
        [p["nombre"] for p in r],
        [int(p["stock_actual"]) for p in r],
    ),
}

GRAFICAS_DEFAULT = [
    {
        "titulo": "Top 5 más vendidos (mes)",
        "tipo": "bar",
        "query_key": "obtener_top_productos",
        "query_params": {"limite": 5, "periodo": "mes"},
    },
    {
        "titulo": "Ventas últimos 7 días",
        "tipo": "line",
        "query_key": "ventas_recientes",
        "query_params": {"dias": 7},
    },
    {
        "titulo": "Estado del inventario",
        "tipo": "doughnut",
        "query_key": "estado_stock",
        "query_params": {},
    },
]


def _ventas_recientes(dias: int = 7, usuario=None):
    hoy   = timezone.now().date()
    inicio = hoy - timedelta(days=dias - 1)
    qs = Venta.objects.filter(fecha__date__range=[str(inicio), str(hoy)])
    if usuario is not None:
        qs = qs.filter(usuario=usuario)
    rows = qs.values("fecha__date").annotate(total=Sum("total")).order_by("fecha__date")
    ventas_dict = {str(r["fecha__date"]): float(r["total"]) for r in rows}
    labels, datos = [], []
    for i in range(dias):
        dia = inicio + timedelta(days=i)
        labels.append(dia.strftime("%d/%m"))
        datos.append(ventas_dict.get(str(dia), 0))
    return labels, datos


def _estado_stock(usuario=None):
    qs = Producto.objects.filter(activo=True)
    if usuario is not None:
        qs = qs.filter(usuario=usuario)
    prods   = list(qs)
    normal  = sum(1 for p in prods if p.estado_stock == "normal")
    bajo    = sum(1 for p in prods if p.estado_stock == "bajo")
    critico = sum(1 for p in prods if p.estado_stock == "critico")
    return ["Normal", "Bajo", "Crítico"], [normal, bajo, critico]


CUSTOM_RESOLVERS = {
    "ventas_recientes": lambda p, u: _ventas_recientes(p.get("dias", 7), usuario=u),
    "estado_stock":     lambda p, u: _estado_stock(usuario=u),
}


def obtener_resumen_dashboard(usuario) -> dict:
    hoy          = timezone.now()
    inicio_dia   = hoy.replace(hour=0, minute=0, second=0, microsecond=0)
    inicio_semana = inicio_dia - timedelta(days=hoy.weekday())
    inicio_mes   = hoy.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    def _sum(qs):
        return qs.aggregate(t=Sum("total"))["t"] or 0

    prods = list(Producto.objects.filter(activo=True, usuario=usuario))
    return {
        "ingresos_dia":     _sum(Venta.objects.filter(fecha__gte=inicio_dia, usuario=usuario)),
        "ingresos_semana":  _sum(Venta.objects.filter(fecha__gte=inicio_semana, usuario=usuario)),
        "ingresos_mes":     _sum(Venta.objects.filter(fecha__gte=inicio_mes, usuario=usuario)),
        "stock_normal":     sum(1 for p in prods if p.estado_stock == "normal"),
        "stock_bajo":       sum(1 for p in prods if p.estado_stock == "bajo"),
        "stock_critico":    sum(1 for p in prods if p.estado_stock == "critico"),
        "total_productos":  len(prods),
        "ultimas_ventas":   Venta.objects.filter(usuario=usuario).prefetch_related("lineas__producto").order_by("-fecha")[:10],
    }


def _resolver_datos(grafica: GraficaDashboard, usuario=None):
    key = grafica.query_key or ""

    if key in CUSTOM_RESOLVERS:
        try:
            return CUSTOM_RESOLVERS[key](grafica.query_params or {}, usuario)
        except Exception:
            pass

    if key:
        from mcp_server.tools import HERRAMIENTAS_MAP
        if key in HERRAMIENTAS_MAP:
            try:
                resultado = HERRAMIENTAS_MAP[key](usuario=usuario, **(grafica.query_params or {}))
                if key in QUERY_EXTRACTORS:
                    return QUERY_EXTRACTORS[key](resultado)
            except Exception:
                pass

    return list(grafica.labels or []), list(grafica.datos or [])


def _sincronizar_defaults(usuario):
    existing = set(
        GraficaDashboard.objects
        .filter(usuario=usuario, fuente=GraficaDashboard.Fuente.DEFAULT)
        .values_list("query_key", flat=True)
    )
    orden = GraficaDashboard.objects.filter(usuario=usuario).count()
    for cfg in GRAFICAS_DEFAULT:
        if cfg["query_key"] not in existing:
            GraficaDashboard.objects.create(
                usuario=usuario,
                fuente=GraficaDashboard.Fuente.DEFAULT,
                orden=orden,
                **cfg,
            )
            orden += 1


def obtener_graficas_dashboard(usuario) -> list[dict]:
    _sincronizar_defaults(usuario)
    result = []
    for g in GraficaDashboard.objects.filter(usuario=usuario):
        labels, datos = _resolver_datos(g, usuario)
        result.append({
            "pk":     g.pk,
            "titulo": g.titulo,
            "tipo":   g.tipo,
            "fuente": g.fuente,
            "labels": labels,
            "datos":  datos,
        })
    return result


def crear_grafica_ia(usuario, grafica_dict: dict):
    count = GraficaDashboard.objects.filter(usuario=usuario).count()
    if count >= LIMITE_GRAFICAS:
        return None, f"Dashboard lleno ({count}/{LIMITE_GRAFICAS}). Borra alguna para agregar más."

    g = GraficaDashboard.objects.create(
        usuario=usuario,
        fuente=GraficaDashboard.Fuente.IA,
        titulo=grafica_dict.get("titulo", "Análisis IA"),
        tipo=grafica_dict.get("tipo", "bar"),
        query_key=grafica_dict.get("query_key") or None,
        query_params=grafica_dict.get("query_params") or {},
        labels=grafica_dict.get("labels"),
        datos=grafica_dict.get("datos"),
        orden=count,
    )
    labels, datos = _resolver_datos(g, usuario)
    return {"pk": g.pk, "titulo": g.titulo, "tipo": g.tipo, "labels": labels, "datos": datos}, None


def eliminar_grafica(usuario, pk: int) -> bool:
    deleted, _ = GraficaDashboard.objects.filter(pk=pk, usuario=usuario).delete()
    return deleted > 0


def guardar_vista_dashboard(usuario, graficas_list: list) -> VistaDashboard:
    qs = VistaDashboard.objects.filter(usuario=usuario)
    if qs.count() >= LIMITE_VISTAS:
        qs.order_by("creado_en").first().delete()
    nombre = f"Vista {timezone.now().strftime('%d-%m-%Y %H:%M')}"
    return VistaDashboard.objects.create(usuario=usuario, nombre=nombre, graficas=graficas_list)


def obtener_vistas_historial(usuario):
    return list(VistaDashboard.objects.filter(usuario=usuario))


def obtener_productos_por_estado(estado: str):
    return [p for p in Producto.objects.filter(activo=True) if p.estado_stock == estado]
