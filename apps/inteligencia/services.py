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
Tienes acceso a los datos reales del negocio a través de herramientas. Úsalas SIEMPRE antes de responder.
Responde SIEMPRE en español, en lenguaje simple y cercano que un tendero colombiano entienda.

━━ CÓMO ELEGIR tipo_respuesta ━━
- "grafica": el usuario pide ver algo visualmente. Señales: "muéstrame", "gráfica", "top", "tendencia",
  "cómo van", "cuáles son los más", "comparar", "distribución", "ver", "ponme una gráfica".
- "mixto": útil mostrar explicación + gráfica. Señales: preguntas que piden análisis Y visualización.
- "texto": respuesta sin visual. Señales: "cuánto", "qué pasó", "por qué", preguntas directas sin comparar.

━━ CÓMO ELEGIR modo_dashboard ━━
Usa "reemplazar" si el usuario quiere un PANEL COMPLETO con varias métricas.
Señales de "reemplazar": "dashboard", "panel", "resumen completo", "todo de hoy/semana/mes",
  "análisis completo", "cómo va todo", "dame un resumen visual", "hazme un panel".
En este modo usa el campo "graficas" (ARRAY con 2 a 4 gráficas).

Usa "agregar" para UNA sola gráfica puntual (modo por defecto).
Señales de "agregar": "muéstrame el top", "gráfica de ventas", "cómo van los productos",
  "ponme la gráfica de", una sola pregunta específica.
En este modo usa el campo "grafica" (SINGULAR).

━━ query_key: nombre EXACTO de la herramienta usada ━━
obtener_stock_critico | obtener_ventas_por_periodo | obtener_top_productos | obtener_ingresos | obtener_resumen_negocio
Si usaste varias herramientas o no aplica, pon null.

━━ ESTRUCTURA JSON — modo "agregar" ━━
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
Si una herramienta devuelve lista vacía [], total 0, o sin registros:
- Responde YA con tipo_respuesta "texto". NO sigas llamando herramientas. NO inventes cifras.
- Ejemplo: {"tipo_respuesta":"texto","texto":"No hay ventas registradas en ese período.","grafica":null}

IMPORTANTE: No incluyas nada fuera del JSON. No uses markdown. Solo el objeto JSON válido.
""".strip()

# Herramientas en formato Anthropic
TOOLS_ANTHROPIC = [
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
                "limite": {"description": "Cantidad de productos a retornar. Por defecto 5.", "default": 5},
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
        "description": "Snapshot completo del estado actual de la tienda.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
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
            "texto": (
                f"No tienes una API key configurada para {proveedor.capitalize()}. "
                "Ve a 'Mi cuenta' y agrega tu key."
            ),
            "grafica": None,
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
    # Primera llamada: forzar uso de herramienta para consultar datos reales del usuario
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
        # Llamadas siguientes: el modelo puede decidir si necesita más datos
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
            # Groq y Gemini soportan "required"; Ollama puede no soportarlo — intentamos y hacemos fallback
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

    # 3. Extrae el primer objeto JSON del texto (maneja prefijos como <function-null>)
    inicio = texto.find("{")
    fin = texto.rfind("}") + 1
    if inicio != -1 and fin > inicio:
        try:
            return json.loads(texto[inicio:fin])
        except json.JSONDecodeError:
            pass

    # 4. Fallback: devuelve el texto limpio sin artefactos del modelo
    texto_limpio = re.sub(r'<[^>]+>', '', texto).strip()
    return {"tipo_respuesta": "texto", "texto": texto_limpio or texto, "grafica": None}


def obtener_historial(usuario) -> list:
    try:
        conversacion = Conversacion.objects.get(usuario=usuario)
        return list(conversacion.mensajes.order_by("creado_en"))
    except Conversacion.DoesNotExist:
        return []
