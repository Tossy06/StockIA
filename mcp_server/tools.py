import os
import django

if not django.conf.settings.configured:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
    django.setup()

from django.db.models import Sum, F
from django.utils import timezone
from apps.catalogo.models import Producto, Categoria
from apps.ventas.models import Venta, LineaVenta


# ── HERRAMIENTAS DE CONSULTA ANALÍTICA ──────────────────────────────────────

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


# ── HERRAMIENTAS DE GESTIÓN DE INVENTARIO ───────────────────────────────────

def listar_productos(usuario=None) -> list[dict]:
    """Devuelve todos los productos activos del usuario con ID, nombre, categoría, precio y stock."""
    qs = Producto.objects.select_related("categoria").filter(activo=True)
    if usuario is not None:
        qs = qs.filter(usuario=usuario)
    return [
        {
            "id": p.pk,
            "nombre": p.nombre,
            "categoria": p.categoria.nombre,
            "precio_unitario": float(p.precio_unitario),
            "stock_actual": p.stock_actual,
            "stock_minimo": p.stock_minimo,
            "estado_stock": p.estado_stock,
        }
        for p in qs
    ]


def listar_categorias(usuario=None) -> list[dict]:
    """Devuelve todas las categorías del usuario."""
    qs = Categoria.objects.all()
    if usuario is not None:
        qs = qs.filter(usuario=usuario)
    return [{"id": c.pk, "nombre": c.nombre} for c in qs]


def crear_categoria(nombre: str, usuario=None) -> dict:
    """Crea una nueva categoría. Si ya existe con ese nombre, la retorna sin duplicar."""
    existing = Categoria.objects.filter(usuario=usuario, nombre__iexact=nombre).first()
    if existing:
        return {"id": existing.pk, "nombre": existing.nombre, "ya_existia": True}
    cat = Categoria.objects.create(nombre=nombre, usuario=usuario)
    return {"id": cat.pk, "nombre": cat.nombre, "ya_existia": False}


def crear_producto(
    nombre: str,
    categoria: str,
    precio_unitario: float,
    stock_actual: int = 0,
    stock_minimo: int = 5,
    usuario=None,
) -> dict:
    """Crea un nuevo producto. Si la categoría no existe, la crea automáticamente."""
    cat_qs = Categoria.objects.filter(usuario=usuario, nombre__iexact=categoria)
    if cat_qs.exists():
        cat = cat_qs.first()
        cat_creada = False
    else:
        cat = Categoria.objects.create(nombre=categoria, usuario=usuario)
        cat_creada = True

    p = Producto.objects.create(
        usuario=usuario,
        nombre=nombre,
        categoria=cat,
        precio_unitario=precio_unitario,
        stock_actual=stock_actual,
        stock_minimo=stock_minimo,
    )
    return {
        "id": p.pk,
        "nombre": p.nombre,
        "categoria": cat.nombre,
        "precio_unitario": float(p.precio_unitario),
        "stock_actual": p.stock_actual,
        "stock_minimo": p.stock_minimo,
        "categoria_creada": cat_creada,
    }


def eliminar_producto(producto_id: int, usuario=None) -> dict:
    """Elimina un producto por ID. Solo elimina productos que pertenecen al usuario."""
    try:
        p = Producto.objects.get(pk=producto_id, usuario=usuario)
        nombre = p.nombre
        p.delete()
        return {"ok": True, "mensaje": f"Producto '{nombre}' eliminado correctamente."}
    except Producto.DoesNotExist:
        return {"ok": False, "error": f"Producto con ID {producto_id} no encontrado o no te pertenece."}


def buscar_y_asignar_imagen(producto_id: int, usuario=None) -> dict:
    """Busca una imagen en internet usando el nombre del producto y la asigna automáticamente."""
    import urllib.request
    import urllib.parse
    from django.core.files.base import ContentFile

    try:
        producto = Producto.objects.get(pk=producto_id, usuario=usuario)
    except Producto.DoesNotExist:
        return {"ok": False, "error": f"Producto ID {producto_id} no encontrado o no te pertenece."}

    keyword = urllib.parse.quote(producto.nombre)
    url = f"https://loremflickr.com/400/400/{keyword}/all"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            content_type = resp.headers.get("Content-Type", "")
            if "image" not in content_type:
                return {"ok": False, "error": "No se encontró una imagen para ese producto."}
            data = resp.read()
        ext = "jpg" if "jpeg" in content_type else "png"
        filename = f"ai_{producto.pk}_{int(timezone.now().timestamp())}.{ext}"
        producto.imagen.save(filename, ContentFile(data), save=True)
        return {
            "ok": True,
            "mensaje": f"Imagen asignada a '{producto.nombre}' correctamente.",
            "producto_id": producto.pk,
            "url_imagen": producto.imagen.url,
        }
    except Exception as e:
        return {"ok": False, "error": f"No se pudo obtener la imagen: {str(e)}"}


# ── MAPA DE HERRAMIENTAS ─────────────────────────────────────────────────────

HERRAMIENTAS_MAP = {
    # Analíticas
    "obtener_stock_critico": obtener_stock_critico,
    "obtener_ventas_por_periodo": obtener_ventas_por_periodo,
    "obtener_top_productos": obtener_top_productos,
    "obtener_ingresos": obtener_ingresos,
    "obtener_resumen_negocio": obtener_resumen_negocio,
    # Gestión de inventario
    "listar_productos": listar_productos,
    "listar_categorias": listar_categorias,
    "crear_categoria": crear_categoria,
    "crear_producto": crear_producto,
    "eliminar_producto": eliminar_producto,
    "buscar_y_asignar_imagen": buscar_y_asignar_imagen,
}


def ejecutar_herramienta(nombre: str, argumentos: dict, usuario=None):
    fn = HERRAMIENTAS_MAP.get(nombre)
    if fn is None:
        return {"error": f"Herramienta '{nombre}' no encontrada."}
    return fn(usuario=usuario, **(argumentos or {}))
