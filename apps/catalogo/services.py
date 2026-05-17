from .models import Categoria, Producto


def listar_categorias():
    return Categoria.objects.all()


def listar_productos():
    return Producto.objects.select_related("categoria").all()


def obtener_producto(producto_id: int) -> Producto:
    return Producto.objects.select_related("categoria").get(pk=producto_id)


def crear_producto(datos: dict) -> Producto:
    return Producto.objects.create(
        nombre=datos["nombre"],
        categoria_id=datos["categoria_id"],
        precio_unitario=datos["precio_unitario"],
        stock_actual=datos["stock_actual"],
        stock_minimo=datos["stock_minimo"],
    )


def actualizar_producto(producto_id: int, datos: dict) -> Producto:
    producto = Producto.objects.get(pk=producto_id)
    producto.nombre = datos["nombre"]
    producto.categoria_id = datos["categoria_id"]
    producto.precio_unitario = datos["precio_unitario"]
    producto.stock_actual = datos["stock_actual"]
    producto.stock_minimo = datos["stock_minimo"]
    producto.save()
    return producto


def eliminar_producto(producto_id: int):
    Producto.objects.filter(pk=producto_id).delete()


def crear_categoria(nombre: str) -> Categoria:
    return Categoria.objects.create(nombre=nombre)
