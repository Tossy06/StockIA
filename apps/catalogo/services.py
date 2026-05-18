from django.db.models import Count
from .models import Categoria, Producto


def listar_categorias(usuario):
    return Categoria.objects.filter(usuario=usuario).order_by("nombre")


def listar_categorias_con_conteo(usuario):
    return (
        Categoria.objects
        .filter(usuario=usuario)
        .annotate(num_productos=Count("producto"))
        .order_by("nombre")
    )


def listar_productos(usuario):
    return Producto.objects.select_related("categoria").filter(usuario=usuario)


def obtener_producto(producto_id: int, usuario) -> Producto:
    return Producto.objects.select_related("categoria").get(pk=producto_id, usuario=usuario)


def crear_producto(datos: dict, usuario) -> Producto:
    p = Producto(
        usuario=usuario,
        nombre=datos["nombre"],
        categoria_id=datos["categoria_id"],
        precio_unitario=datos["precio_unitario"],
        stock_actual=datos["stock_actual"],
        stock_minimo=datos["stock_minimo"],
    )
    if datos.get("imagen"):
        p.imagen = datos["imagen"]
    p.save()
    return p


def actualizar_producto(producto_id: int, datos: dict, usuario) -> Producto:
    producto = Producto.objects.get(pk=producto_id, usuario=usuario)
    producto.nombre = datos["nombre"]
    producto.categoria_id = datos["categoria_id"]
    producto.precio_unitario = datos["precio_unitario"]
    producto.stock_actual = datos["stock_actual"]
    producto.stock_minimo = datos["stock_minimo"]
    if datos.get("borrar_imagen") and producto.imagen:
        producto.imagen.delete(save=False)
        producto.imagen = None
    if datos.get("imagen"):
        producto.imagen = datos["imagen"]
    producto.save()
    return producto


def eliminar_producto(producto_id: int, usuario):
    Producto.objects.filter(pk=producto_id, usuario=usuario).delete()


def crear_categoria(nombre: str, usuario) -> Categoria:
    return Categoria.objects.create(nombre=nombre, usuario=usuario)


def renombrar_categoria(categoria_id: int, nombre: str, usuario) -> Categoria:
    cat = Categoria.objects.get(pk=categoria_id, usuario=usuario)
    cat.nombre = nombre
    cat.save()
    return cat


def eliminar_categoria(categoria_id: int, usuario):
    Categoria.objects.filter(pk=categoria_id, usuario=usuario).delete()
