import json
import anthropic
from openai import OpenAI
from django.conf import settings
from cryptography.fernet import Fernet
from apps.identidad.models import PerfilTendero
from .models import Conversacion, Mensaje
from mcp_server.tools import ejecutar_herramienta

SYSTEM_PROMPT = """
Eres un asistente de inventario para una tienda de barrio colombiana.
Tienes acceso a los datos REALES del negocio a través de herramientas. Úsalas SIEMPRE antes de responder.
Responde SIEMPRE en español, en lenguaje simple y cercano que un tendero colombiano entienda.

━━ HERRAMIENTAS ANALÍTICAS (para consultar datos) ━━
- obtener_resumen_negocio: estado general de la tienda (productos, stock, ingresos).
  Úsala cuando pregunten cómo está el negocio o cuántos productos hay.
- obtener_stock_critico: productos con stock crítico (< 50% del mínimo).
- obtener_ingresos: ingresos totales del día/semana/mes.
- obtener_top_productos: los más vendidos del período.
- obtener_ventas_por_periodo: ventas entre dos fechas (formato YYYY-MM-DD).

━━ HERRAMIENTAS DE GESTIÓN (para administrar el inventario) ━━
CONSULTAR:
- listar_productos: muestra todos los productos con ID, nombre, categoría, precio y stock.
  Úsala cuando el usuario pregunte "¿qué tengo?", "mis productos", "lista de productos",
  o antes de eliminar/buscar imagen de un producto para obtener su ID.
- listar_categorias: muestra todas las categorías con sus IDs.
  Úsala antes de crear un producto para verificar si la categoría ya existe.

CREAR:
- crear_producto: crea un nuevo producto. Si la categoría no existe, la crea automáticamente.
  Datos necesarios: nombre, categoría, precio_unitario. Stock y stock_minimo son opcionales.
- crear_categoria: crea solo una categoría, sin producto.

ELIMINAR:
- eliminar_producto: elimina un producto por su ID.
  SIEMPRE llama listar_productos primero para ver el ID correcto, y confirma el nombre con el usuario.

IMAGEN:
- buscar_y_asignar_imagen: busca una foto del producto en internet y la asigna automáticamente.
  Requiere el ID del producto. Llama listar_productos primero si no conoces el ID.

━━ CÓMO ELEGIR tipo_respuesta ━━
- "grafica": el usuario pide ver algo visualmente. Señales: "muéstrame", "gráfica", "top", "tendencia",
  "cómo van", "cuáles son los más", "comparar", "distribución", "ver", "ponme una gráfica".
- "mixto": útil mostrar explicación + gráfica. Señales: preguntas que piden análisis Y visualización.
- "texto": respuesta sin visual. Señales: "cuánto", "qué pasó", "por qué", preguntas directas,
  operaciones de gestión (crear, eliminar, buscar imagen, listar).

━━ CÓMO ELEGIR modo_dashboard ━━
Usa "reemplazar" si el usuario quiere un PANEL COMPLETO con varias métricas.
Señales: "dashboard", "panel", "resumen completo", "todo de hoy/semana/mes",
  "análisis completo", "cómo va todo", "dame un resumen visual", "hazme un panel".
En este modo usa el campo "graficas" (ARRAY con 2 a 4 gráficas).

Usa "agregar" para UNA sola gráfica puntual (modo por defecto).
En este modo usa el campo "grafica" (SINGULAR).

━━ query_key ━━
Para herramientas analíticas: pon el nombre exacto de la herramienta usada.
  Opciones: obtener_stock_critico | obtener_ventas_por_periodo | obtener_top_productos | obtener_ingresos | obtener_resumen_negocio
Para herramientas de gestión o múltiples herramientas: pon null.

━━ ESTRUCTURA JSON — modo "agregar" (texto o gráfica única) ━━
{
  "tipo_respuesta": "grafica | mixto | texto",
  "modo_dashboard": "agregar",
  "grafica": {
    "tipo": "bar | line | pie | doughnut",
    "titulo": "título corto y claro",
    "labels": ["etiqueta1", "etiqueta2"],
    "datos": [0, 0],
    "query_key": "nombre_herramienta_o_null",
    "query_params": {}
  },
  "texto": "explicación breve para el tendero"
}

━━ ESTRUCTURA JSON — modo "reemplazar" (panel completo) ━━
{
  "tipo_respuesta": "grafica",
  "modo_dashboard": "reemplazar",
  "graficas": [
    { "tipo": "bar", "titulo": "...", "labels": [...], "datos": [...], "query_key": "...", "query_params": {} },
    { "tipo": "pie", "titulo": "...", "labels": [...], "datos": [...], "query_key": "...", "query_params": {} }
  ],
  "texto": "descripción breve del panel"
}

━━ CUANDO NO HAY DATOS ━━
Si una herramienta devuelve lista vacía [] o total 0:
- Responde con tipo_respuesta "texto". NO inventes cifras.
- Si no hay productos: ofrece ayuda para crear los primeros productos.
- Ejemplo: {"tipo_respuesta":"texto","modo_dashboard":"agregar","grafica":null,"texto":"Todavía no tienes productos registrados. ¿Quieres que te ayude a crear uno?"}

IMPORTANTE: No incluyas nada fuera del JSON. No uses markdown. Solo el objeto JSON válido.
""".strip()

# Herramientas en formato Anthropic
TOOLS_ANTHROPIC = [
    # ── Analíticas ──
    {
        "name": "obtener_stock_critico",
        "description": "Productos con stock crítico (por debajo del 50% del mínimo).",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "obtener_ingresos",
        "description": "Ingresos totales del período indicado.",
        "input_schema": {
            "type": "object",
            "properties": {
                "periodo": {"type": "string", "enum": ["dia", "semana", "mes"]}
            },
            "required": ["periodo"],
        },
    },
    {
        "name": "obtener_top_productos",
        "description": "Productos más vendidos del período.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limite": {"type": "integer", "description": "Cantidad de productos a retornar. Por defecto 5.", "default": 5},
                "periodo": {"type": "string", "enum": ["dia", "semana", "mes"]},
            },
            "required": [],
        },
    },
    {
        "name": "obtener_ventas_por_periodo",
        "description": "Ventas agrupadas por día entre dos fechas.",
        "input_schema": {
            "type": "object",
            "properties": {
                "inicio": {"type": "string", "description": "Fecha inicio YYYY-MM-DD."},
                "fin": {"type": "string", "description": "Fecha fin YYYY-MM-DD."},
            },
            "required": ["inicio", "fin"],
        },
    },
    {
        "name": "obtener_resumen_negocio",
        "description": "Snapshot completo del estado actual de la tienda: total productos, stock, ingresos y top ventas.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    # ── Gestión de inventario ──
    {
        "name": "listar_productos",
        "description": "Lista todos los productos del usuario con ID, nombre, categoría, precio y stock. Úsala para responder qué productos hay o para encontrar el ID antes de eliminar o asignar imagen.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "listar_categorias",
        "description": "Lista todas las categorías del usuario con ID y nombre. Úsala antes de crear un producto.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "crear_categoria",
        "description": "Crea una nueva categoría. Si ya existe con ese nombre no crea duplicados.",
        "input_schema": {
            "type": "object",
            "properties": {
                "nombre": {"type": "string", "description": "Nombre de la categoría."},
            },
            "required": ["nombre"],
        },
    },
    {
        "name": "crear_producto",
        "description": "Crea un nuevo producto en el inventario. Si la categoría no existe, la crea automáticamente.",
        "input_schema": {
            "type": "object",
            "properties": {
                "nombre": {"type": "string", "description": "Nombre del producto."},
                "categoria": {"type": "string", "description": "Nombre de la categoría del producto."},
                "precio_unitario": {"type": "number", "description": "Precio unitario en pesos colombianos."},
                "stock_actual": {"type": "integer", "description": "Cantidad actual en inventario. Por defecto 0.", "default": 0},
                "stock_minimo": {"type": "integer", "description": "Cantidad mínima antes de alertar stock bajo. Por defecto 5.", "default": 5},
            },
            "required": ["nombre", "categoria", "precio_unitario"],
        },
    },
    {
        "name": "eliminar_producto",
        "description": "Elimina un producto por su ID. Llama listar_productos primero para obtener el ID correcto.",
        "input_schema": {
            "type": "object",
            "properties": {
                "producto_id": {"type": "integer", "description": "ID numérico del producto a eliminar."},
            },
            "required": ["producto_id"],
        },
    },
    {
        "name": "buscar_y_asignar_imagen",
        "description": "Busca una foto del producto en internet y la asigna automáticamente. Requiere el ID del producto.",
        "input_schema": {
            "type": "object",
            "properties": {
                "producto_id": {"type": "integer", "description": "ID del producto al que asignar la imagen."},
            },
            "required": ["producto_id"],
        },
    },
]

# Herramientas en formato OpenAI (Groq, Gemini, Ollama)
TOOLS_OPENAI = [
    {
        "type": "function",
        "function": {
            "name": t["name"],
            "description": t["description"],
            "parameters": t["input_schema"],
        },
    }
    for t in TOOLS_ANTHROPIC
]

MODELOS = {
    "claude": "claude-sonnet-4-5",
    "gemini": "gemini-1.5-flash",
    "groq": "llama-3.3-70b-versatile",
    "ollama": "qwen2.5:7b",
}

BASE_URLS = {
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "groq": "https://api.groq.com/openai/v1",
    "ollama": "http://localhost:11434/v1",
}


def enviar_mensaje(usuario, texto_usuario: str) -> dict:
    fernet = Fernet(settings.FERNET_KEY)
    perfil, _ = PerfilTendero.objects.get_or_create(usuario=usuario)
    proveedor = perfil.proveedor

    api_key = perfil.obtener_api_key(fernet) if proveedor != "ollama" else "ollama"

    if proveedor != "ollama" and not api_key:
        return {
            "tipo_respuesta": "texto",
            "modo_dashboard": "agregar",
            "texto": (
                f"No tienes una API key configurada para {proveedor.capitalize()}. "
                "Ve a 'Mi cuenta' y agrega tu key."
            ),
            "grafica": None,
            "graficas": [],
        }

    conversacion, _ = Conversacion.objects.get_or_create(usuario=usuario)
    historial = list(conversacion.mensajes.order_by("creado_en").values("rol", "contenido"))

    Mensaje.objects.create(
        conversacion=conversacion,
        rol=Mensaje.Rol.USUARIO,
        contenido=texto_usuario,
    )

    mensajes_api = [
        {"role": "assistant" if m["rol"] == "asistente" else "user", "content": m["contenido"]}
        for m in historial
    ] + [{"role": "user", "content": texto_usuario}]

    if proveedor == "claude":
        respuesta_json = _llamar_claude(api_key, mensajes_api, usuario)
    else:
        respuesta_json = _llamar_openai_compat(proveedor, api_key, mensajes_api, usuario)

    tipo = respuesta_json.get("tipo_respuesta", "texto")
    modo = respuesta_json.get("modo_dashboard", "agregar")
    grafica = respuesta_json.get("grafica") or None
    graficas = respuesta_json.get("graficas") or []
    datos_guardar = graficas if graficas else grafica

    Mensaje.objects.create(
        conversacion=conversacion,
        rol=Mensaje.Rol.ASISTENTE,
        contenido=respuesta_json.get("texto", ""),
        tipo_respuesta=tipo,
        datos_grafica=datos_guardar,
    )

    return {
        "tipo_respuesta": tipo,
        "modo_dashboard": modo,
        "texto": respuesta_json.get("texto", ""),
        "grafica": grafica,
        "graficas": graficas,
    }


def _llamar_claude(api_key: str, mensajes: list, usuario=None) -> dict:
    client = anthropic.Anthropic(api_key=api_key)
    tool_choice = {"type": "any"}
    while True:
        respuesta = client.messages.create(
            model=MODELOS["claude"],
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            tools=TOOLS_ANTHROPIC,
            tool_choice=tool_choice,
            messages=mensajes,
        )
        tool_choice = {"type": "auto"}
        if respuesta.stop_reason == "tool_use":
            tool_results = []
            for bloque in respuesta.content:
                if bloque.type == "tool_use":
                    resultado = ejecutar_herramienta(bloque.name, bloque.input, usuario)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": bloque.id,
                        "content": json.dumps(resultado, ensure_ascii=False, default=str),
                    })
            mensajes = mensajes + [
                {"role": "assistant", "content": respuesta.content},
                {"role": "user", "content": tool_results},
            ]
            continue
        texto = "".join(b.text for b in respuesta.content if hasattr(b, "text"))
        return _parsear_json(texto)


def _llamar_openai_compat(proveedor: str, api_key: str, mensajes: list, usuario=None) -> dict:
    client = OpenAI(api_key=api_key, base_url=BASE_URLS[proveedor])
    modelo = MODELOS[proveedor]
    mensajes = [{"role": "system", "content": SYSTEM_PROMPT}] + mensajes
    primera_llamada = True

    while True:
        kwargs = {"model": modelo, "messages": mensajes, "tools": TOOLS_OPENAI}
        if primera_llamada:
            try:
                respuesta = client.chat.completions.create(**kwargs, tool_choice="required")
            except Exception:
                respuesta = client.chat.completions.create(**kwargs, tool_choice="auto")
        else:
            respuesta = client.chat.completions.create(**kwargs, tool_choice="auto")
        primera_llamada = False

        mensaje = respuesta.choices[0].message

        if mensaje.tool_calls:
            mensajes.append(mensaje)
            for tool_call in mensaje.tool_calls:
                args = json.loads(tool_call.function.arguments)
                resultado = ejecutar_herramienta(tool_call.function.name, args, usuario)
                mensajes.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(resultado, ensure_ascii=False, default=str),
                })
            continue

        return _parsear_json(mensaje.content or "")


def _parsear_json(texto: str) -> dict:
    import re
    texto = texto.strip()

    # 1. Extrae JSON de bloque markdown ```json ... ``` (Groq a veces lo incluye)
    m = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', texto)
    if m:
        texto = m.group(1).strip()

    # 2. Intento directo
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        pass

    # 3. Extrae el primer objeto JSON del texto
    inicio = texto.find("{")
    fin = texto.rfind("}") + 1
    if inicio != -1 and fin > inicio:
        try:
            return json.loads(texto[inicio:fin])
        except json.JSONDecodeError:
            pass

    # 4. Fallback
    texto_limpio = re.sub(r'<[^>]+>', '', texto).strip()
    return {
        "tipo_respuesta": "texto",
        "modo_dashboard": "agregar",
        "texto": texto_limpio or texto,
        "grafica": None,
    }


def obtener_historial(usuario) -> list:
    try:
        conversacion = Conversacion.objects.get(usuario=usuario)
        return list(conversacion.mensajes.order_by("creado_en"))
    except Conversacion.DoesNotExist:
        return []
