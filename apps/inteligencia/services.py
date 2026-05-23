import json
import anthropic
from openai import OpenAI
from django.conf import settings
from cryptography.fernet import Fernet
from apps.identidad.models import PerfilTendero
from .models import Conversacion, Mensaje
from mcp_server.tools import ejecutar_herramienta

SYSTEM_PROMPT = """
Eres StockBot, el asistente de inventario para una tienda de barrio colombiana.
REGLA PRINCIPAL: SIEMPRE usa una herramienta antes de responder. Nunca respondas de memoria.
Habla en español colombiano simple. No uses anglicismos ni tecnicismos.

━━ GUÍA DE HERRAMIENTAS ━━

CONSULTAS GENERALES DEL NEGOCIO:
  obtener_resumen_negocio → "cómo va el negocio", "resumen", "estado de la tienda",
    "tengo ventas?", "cuántos productos tengo", "cuánto llevo hoy/semana/mes".
    Incluye: total_productos, stock, ingresos_hoy, ingresos_semana, ingresos_mes, top_productos.

VENTAS - HISTORIAL Y DETALLE:
  listar_ventas_recientes(limite) → "últimas ventas", "qué vendí", "ventas recientes",
    "muéstrame las ventas", "historial de ventas", "cuándo vendí".
    Usa limite=5 por defecto, más si el usuario pide más.
  obtener_ventas_producto(nombre_producto, periodo) → "cuánto vendí de X",
    "ventas de Fabuloso", "cuántos huevos vendí este mes", búsquedas por producto específico.
  obtener_ventas_por_periodo(inicio, fin) → cuando el usuario da fechas exactas.
    Formato YYYY-MM-DD. Hoy es ${hoy}. Calcula las fechas tú mismo.

INGRESOS Y DINERO:
  obtener_ingresos(periodo) → "cuánto gané", "ingresos de hoy/semana/mes",
    "cuánto dinero entró". periodo: "dia", "semana" o "mes".

PRODUCTOS MÁS VENDIDOS:
  obtener_top_productos(limite, periodo) → "qué se vende más", "top productos",
    "los más vendidos", "ranking de ventas". Usa periodo "mes" por defecto.

STOCK E INVENTARIO:
  listar_productos → "qué productos tengo", "lista de productos", "mis productos",
    "catálogo", buscar un producto por nombre, o antes de eliminar/asignar imagen.
  obtener_stock_critico → "qué me falta", "stock crítico", "qué está por agotarse".
  obtener_stock_bajo → "qué está bajo", "alertas de stock", "qué tengo poco".

CATEGORÍAS:
  listar_categorias → "qué categorías tengo", antes de crear un producto nuevo.

GRÁFICAS:
  obtener_top_productos + grafica bar → "ponme una gráfica de los más vendidos"
  obtener_ventas_por_periodo + grafica line → "gráfica de ventas del mes"
  obtener_stock_critico + grafica bar → "gráfica de stock crítico"
  obtener_resumen_negocio + grafica doughnut → "distribución del inventario"

CREAR:
  crear_producto(nombre, categoria, precio_unitario, stock_actual, stock_minimo)
    → "agrega", "crea el producto", "añade". La categoría se crea sola si no existe.
  crear_categoria(nombre) → "crea la categoría", "nueva categoría".

ELIMINAR:
  Primero llama listar_productos para obtener el ID, luego eliminar_producto(producto_id).
  → "elimina", "borra", "quita el producto".

IMAGEN:
  buscar_y_asignar_imagen(producto_id) → "busca imagen", "ponle foto", "asigna imagen".
  Llama listar_productos primero para obtener el ID.

━━ TIPO DE RESPUESTA ━━
- "texto": operaciones de gestión, preguntas directas de números, listados.
- "grafica": el usuario pide ver algo visualmente ("gráfica", "muéstrame", "ver tendencia").
- "mixto": análisis + gráfica juntos.

━━ MODO DASHBOARD ━━
- "agregar" (default): UNA gráfica → usa campo "grafica" (singular).
- "reemplazar": panel completo → "dashboard", "panel completo", "resumen visual" → usa "graficas" (array 2-4).

━━ ESTRUCTURA JSON OBLIGATORIA ━━
Modo texto o una gráfica:
{"tipo_respuesta":"texto|grafica|mixto","modo_dashboard":"agregar","grafica":null_o_objeto,"texto":"mensaje"}

Objeto grafica:
{"tipo":"bar|line|pie|doughnut","titulo":"título","labels":[...],"datos":[...],"query_key":"herramienta_o_null","query_params":{}}

Panel completo:
{"tipo_respuesta":"grafica","modo_dashboard":"reemplazar","graficas":[{...},{...}],"texto":"descripción"}

━━ CUANDO NO HAY DATOS ━━
Si no hay ventas ni productos: dilo claramente y ofrece ayuda para empezar.
Ejemplo: {"tipo_respuesta":"texto","modo_dashboard":"agregar","grafica":null,"texto":"Todavía no tienes ventas registradas. ¿Quieres que te explique cómo registrar una venta?"}

IMPORTANTE: Responde SOLO con el JSON. Sin texto extra, sin markdown, sin explicaciones fuera del JSON.
""".strip()

# ── DEFINICIÓN DE HERRAMIENTAS ───────────────────────────────────────────────

TOOLS_ANTHROPIC = [
    # Analíticas
    {
        "name": "obtener_resumen_negocio",
        "description": "Snapshot completo: total productos, estados de stock, ingresos de hoy/semana/mes y top ventas del mes. Úsala para preguntas generales del negocio.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "obtener_stock_critico",
        "description": "Productos con stock crítico (≤ 50% del mínimo). Para alertas urgentes.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "obtener_stock_bajo",
        "description": "Productos con stock bajo (≤ mínimo) o crítico. Vista completa de alertas de inventario.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "obtener_ingresos",
        "description": "Ingresos totales del período. Úsala para preguntas de cuánto dinero entró.",
        "input_schema": {
            "type": "object",
            "properties": {
                "periodo": {
                    "type": "string",
                    "enum": ["dia", "semana", "mes"],
                    "description": "dia = hoy, semana = semana actual, mes = mes actual.",
                }
            },
            "required": ["periodo"],
        },
    },
    {
        "name": "obtener_top_productos",
        "description": "Productos más vendidos del período por cantidad. Úsala para rankings de ventas.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limite": {
                    "type": "integer",
                    "description": "Cuántos productos mostrar. Por defecto 5.",
                    "default": 5,
                },
                "periodo": {
                    "type": "string",
                    "enum": ["dia", "semana", "mes"],
                    "description": "Período de análisis.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "listar_ventas_recientes",
        "description": "Últimas N ventas con detalle de qué productos se vendieron, cantidades y precios. Úsala para 'últimas ventas', 'qué vendí', 'historial de ventas'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limite": {
                    "type": "integer",
                    "description": "Cantidad de ventas a mostrar. Por defecto 10.",
                    "default": 10,
                }
            },
            "required": [],
        },
    },
    {
        "name": "obtener_ventas_producto",
        "description": "Cuánto se vendió de un producto específico en el período. Úsala para 'cuántos X vendí', 'ventas de Fabuloso', búsquedas por nombre de producto.",
        "input_schema": {
            "type": "object",
            "properties": {
                "nombre_producto": {
                    "type": "string",
                    "description": "Nombre o parte del nombre del producto a buscar.",
                },
                "periodo": {
                    "type": "string",
                    "enum": ["dia", "semana", "mes"],
                    "description": "Período de análisis. Por defecto mes.",
                    "default": "mes",
                },
            },
            "required": ["nombre_producto"],
        },
    },
    {
        "name": "obtener_ventas_por_periodo",
        "description": "Ventas totales agrupadas por día entre dos fechas. Úsala cuando el usuario da fechas exactas o pide gráfica de tendencia de ventas.",
        "input_schema": {
            "type": "object",
            "properties": {
                "inicio": {"type": "string", "description": "Fecha inicio YYYY-MM-DD."},
                "fin": {"type": "string", "description": "Fecha fin YYYY-MM-DD."},
            },
            "required": ["inicio", "fin"],
        },
    },
    # Gestión de inventario
    {
        "name": "listar_productos",
        "description": "Lista todos los productos activos con ID, nombre, categoría, precio y stock. Úsala para mostrar el catálogo, buscar un producto o antes de eliminar/asignar imagen.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "listar_categorias",
        "description": "Lista todas las categorías con ID y nombre. Úsala antes de crear un producto.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "crear_categoria",
        "description": "Crea una nueva categoría. No duplica si ya existe con ese nombre.",
        "input_schema": {
            "type": "object",
            "properties": {
                "nombre": {"type": "string", "description": "Nombre de la categoría."}
            },
            "required": ["nombre"],
        },
    },
    {
        "name": "crear_producto",
        "description": "Crea un nuevo producto. Si la categoría no existe se crea automáticamente.",
        "input_schema": {
            "type": "object",
            "properties": {
                "nombre": {"type": "string", "description": "Nombre del producto."},
                "categoria": {"type": "string", "description": "Nombre de la categoría."},
                "precio_unitario": {
                    "type": "number",
                    "description": "Precio en pesos colombianos.",
                },
                "stock_actual": {
                    "type": "integer",
                    "description": "Unidades en inventario ahora. Por defecto 0.",
                    "default": 0,
                },
                "stock_minimo": {
                    "type": "integer",
                    "description": "Unidades mínimas antes de alertar. Por defecto 5.",
                    "default": 5,
                },
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
                "producto_id": {
                    "type": "integer",
                    "description": "ID numérico del producto a eliminar.",
                }
            },
            "required": ["producto_id"],
        },
    },
    {
        "name": "buscar_y_asignar_imagen",
        "description": "Busca una foto del producto en internet y la asigna. Requiere el ID del producto (usa listar_productos si no lo conoces).",
        "input_schema": {
            "type": "object",
            "properties": {
                "producto_id": {
                    "type": "integer",
                    "description": "ID del producto al que asignar la imagen.",
                }
            },
            "required": ["producto_id"],
        },
    },
]

# Formato OpenAI (Groq, Gemini, Ollama)
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
    from django.utils import timezone
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

    # Inyectamos la fecha actual en el prompt para que el modelo calcule fechas bien
    hoy_str = timezone.now().strftime("%Y-%m-%d")
    prompt_con_fecha = SYSTEM_PROMPT.replace("${hoy}", hoy_str)

    try:
        if proveedor == "claude":
            respuesta_json = _llamar_claude(api_key, mensajes_api, usuario, prompt_con_fecha)
        else:
            respuesta_json = _llamar_openai_compat(proveedor, api_key, mensajes_api, usuario, prompt_con_fecha)
    except Exception as e:
        respuesta_json = _manejar_error_ia(e, proveedor)

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


def _manejar_error_ia(e: Exception, proveedor: str) -> dict:
    """Convierte cualquier excepción de la API de IA en un mensaje amigable en español."""
    nombres = {
        "claude": "Claude (Anthropic)",
        "groq": "Groq",
        "gemini": "Gemini (Google)",
        "ollama": "Ollama",
    }
    nombre = nombres.get(proveedor, proveedor.capitalize())
    err = str(e).lower()

    # ── Rate limit (429) ──────────────────────────────────────────────────────
    if any(x in err for x in ("rate_limit", "429", "quota", "too many requests",
                               "tokens per day", "tokens per minute",
                               "requests per day", "requests per minute")):
        if "tokens per day" in err or "daily" in err:
            msg = (f"Alcanzaste el límite diario de tokens de {nombre}. "
                   "Espera hasta mañana o actualiza tu plan.")
        elif "tokens per minute" in err:
            msg = f"Demasiadas solicitudes en poco tiempo a {nombre}. Espera un minuto e intenta de nuevo."
        else:
            msg = (f"Límite de uso alcanzado en {nombre}. "
                   "Espera unos minutos e intenta de nuevo.")

    # ── API key inválida / sin permisos (401, 403) ────────────────────────────
    elif any(x in err for x in ("401", "403", "invalid api key", "invalid_api_key",
                                 "authentication", "unauthorized", "permission denied",
                                 "forbidden", "incorrect api key")):
        msg = (f"La API key de {nombre} no es válida o expiró. "
               "Ve a 'Mi cuenta' y actualiza tu clave.")

    # ── Ollama no está corriendo ──────────────────────────────────────────────
    elif proveedor == "ollama" and any(x in err for x in (
            "connection refused", "cannot connect", "econnrefused",
            "failed to connect", "connection error")):
        msg = ("Ollama no está corriendo en tu máquina. "
               "Abre la aplicación Ollama y asegúrate de que el modelo esté descargado.")

    # ── Error de red / timeout ────────────────────────────────────────────────
    elif any(x in err for x in ("connection", "timeout", "timed out",
                                 "network", "unreachable", "name or service not known",
                                 "failed to establish", "remotedisconnected")):
        msg = (f"No se pudo conectar a {nombre}. "
               "Verifica tu conexión a internet e intenta de nuevo.")

    # ── Servicio sobrecargado / no disponible (503, 529) ─────────────────────
    elif any(x in err for x in ("503", "529", "overloaded", "service unavailable",
                                 "temporarily unavailable")):
        msg = (f"{nombre} está temporalmente saturado. "
               "Espera unos minutos e intenta de nuevo.")

    # ── Error interno del servidor (500) ──────────────────────────────────────
    elif any(x in err for x in ("500", "internal server error")):
        msg = f"Error interno en {nombre}. Intenta de nuevo en un momento."

    # ── Request malformado (400) — normalmente ya resuelto por retry ──────────
    elif "400" in err or "bad request" in err:
        msg = "No pude procesar esa consulta. Intenta reformular la pregunta."

    # ── Modelo no encontrado ──────────────────────────────────────────────────
    elif any(x in err for x in ("model not found", "model_not_found",
                                 "does not exist", "no such model")):
        msg = (f"El modelo configurado para {nombre} no existe o no está disponible. "
               "Revisa la configuración en 'Mi cuenta'.")

    # ── Clave agotada / sin créditos ──────────────────────────────────────────
    elif any(x in err for x in ("insufficient_quota", "billing", "credit",
                                 "payment", "out of credits")):
        msg = (f"Tu cuenta de {nombre} no tiene créditos suficientes. "
               "Revisa tu plan de facturación.")

    # ── Error desconocido ────────────────────────────────────────────────────
    else:
        msg = f"Error inesperado al usar {nombre}. Detalle: {str(e)[:120]}"

    return {
        "tipo_respuesta": "texto",
        "modo_dashboard": "agregar",
        "texto": msg,
        "grafica": None,
    }


def _llamar_claude(api_key: str, mensajes: list, usuario=None, system_prompt: str = None) -> dict:
    client = anthropic.Anthropic(api_key=api_key)
    tool_choice = {"type": "any"}
    while True:
        respuesta = client.messages.create(
            model=MODELOS["claude"],
            max_tokens=2048,
            system=system_prompt or SYSTEM_PROMPT,
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


def _llamar_openai_compat(
    proveedor: str, api_key: str, mensajes: list, usuario=None, system_prompt: str = None
) -> dict:
    client = OpenAI(api_key=api_key, base_url=BASE_URLS[proveedor])
    modelo = MODELOS[proveedor]
    mensajes = [{"role": "system", "content": system_prompt or SYSTEM_PROMPT}] + mensajes
    primera_llamada = True
    reintentos_bad_request = 0

    while True:
        kwargs = {"model": modelo, "messages": mensajes, "tools": TOOLS_OPENAI}

        # Primera llamada: intentar forzar uso de herramienta.
        # Si Groq falla con 400 (tool call malformado), reintentamos con auto.
        if primera_llamada:
            try:
                respuesta = client.chat.completions.create(**kwargs, tool_choice="required")
                primera_llamada = False
            except Exception as e:
                primera_llamada = False
                err_str = str(e)
                if "400" in err_str or "failed_generation" in err_str or "tool_use_failed" in err_str:
                    reintentos_bad_request += 1
                    if reintentos_bad_request <= 2:
                        try:
                            respuesta = client.chat.completions.create(**kwargs, tool_choice="auto")
                        except Exception as e2:
                            raise e2
                    else:
                        raise
                else:
                    raise
        else:
            respuesta = client.chat.completions.create(**kwargs, tool_choice="auto")

        mensaje = respuesta.choices[0].message

        # Si el modelo no llamó herramientas pero tampoco devolvió texto, reintentamos
        if not mensaje.tool_calls and not (mensaje.content or "").strip():
            if reintentos_bad_request < 2:
                reintentos_bad_request += 1
                primera_llamada = True
                continue
            return {"tipo_respuesta": "texto", "modo_dashboard": "agregar", "grafica": None,
                    "texto": "No pude procesar tu consulta. Intenta reformularla."}

        if mensaje.tool_calls:
            mensajes.append(mensaje)
            for tool_call in mensaje.tool_calls:
                try:
                    args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    args = {}
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

    # 1. Bloque markdown ```json ... ```
    m = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", texto)
    if m:
        texto = m.group(1).strip()

    # 2. Intento directo
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        pass

    # 3. Extraer primer objeto JSON del texto
    inicio = texto.find("{")
    fin = texto.rfind("}") + 1
    if inicio != -1 and fin > inicio:
        try:
            return json.loads(texto[inicio:fin])
        except json.JSONDecodeError:
            pass

    # 4. Fallback limpio
    texto_limpio = re.sub(r"<[^>]+>", "", texto).strip()
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
