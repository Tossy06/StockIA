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
Tienes acceso a los datos reales del negocio a través de herramientas.
Úsalas para responder con datos precisos y actualizados.
Responde SIEMPRE en español, en lenguaje simple que un tendero entienda.

Responde ÚNICAMENTE con un objeto JSON válido con esta estructura exacta:
{
  "tipo_respuesta": "texto | grafica | mixto",
  "grafica": { "tipo": "bar|line|pie|doughnut", "titulo": "", "labels": [], "datos": [] },
  "texto": "tu análisis aquí"
}

No incluyas nada fuera del JSON. No uses markdown. Solo el objeto JSON.
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
                "limite": {"type": "integer", "default": 5},
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
        respuesta_json = _llamar_claude(api_key, mensajes_api)
    else:
        respuesta_json = _llamar_openai_compat(proveedor, api_key, mensajes_api)

    tipo = respuesta_json.get("tipo_respuesta", "texto")
    grafica = respuesta_json.get("grafica") if tipo in ("grafica", "mixto") else None

    Mensaje.objects.create(
        conversacion=conversacion,
        rol=Mensaje.Rol.ASISTENTE,
        contenido=respuesta_json.get("texto", ""),
        tipo_respuesta=tipo,
        datos_grafica=grafica,
    )

    return {"tipo_respuesta": tipo, "texto": respuesta_json.get("texto", ""), "grafica": grafica}


def _llamar_claude(api_key: str, mensajes: list) -> dict:
    client = anthropic.Anthropic(api_key=api_key)
    while True:
        respuesta = client.messages.create(
            model=MODELOS["claude"],
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            tools=TOOLS_ANTHROPIC,
            messages=mensajes,
        )
        if respuesta.stop_reason == "tool_use":
            tool_results = []
            for bloque in respuesta.content:
                if bloque.type == "tool_use":
                    resultado = ejecutar_herramienta(bloque.name, bloque.input)
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


def _llamar_openai_compat(proveedor: str, api_key: str, mensajes: list) -> dict:
    client = OpenAI(api_key=api_key, base_url=BASE_URLS[proveedor])
    modelo = MODELOS[proveedor]
    mensajes = [{"role": "system", "content": SYSTEM_PROMPT}] + mensajes

    while True:
        respuesta = client.chat.completions.create(
            model=modelo,
            messages=mensajes,
            tools=TOOLS_OPENAI,
            tool_choice="auto",
        )
        mensaje = respuesta.choices[0].message

        if mensaje.tool_calls:
            mensajes.append(mensaje)
            for tool_call in mensaje.tool_calls:
                args = json.loads(tool_call.function.arguments)
                resultado = ejecutar_herramienta(tool_call.function.name, args)
                mensajes.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(resultado, ensure_ascii=False, default=str),
                })
            continue

        return _parsear_json(mensaje.content or "")


def _parsear_json(texto: str) -> dict:
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        return {"tipo_respuesta": "texto", "texto": texto, "grafica": None}


def obtener_historial(usuario) -> list:
    try:
        conversacion = Conversacion.objects.get(usuario=usuario)
        return list(conversacion.mensajes.order_by("creado_en"))
    except Conversacion.DoesNotExist:
        return []
