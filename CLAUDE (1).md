# StockIA — CLAUDE.md

Sistema web inteligente de gestión de inventario con IA para micronegocios de barrio en Colombia.
Universidad Manuela Beltrán · Ingeniería Web 2026-1 · Ing. Juan José Osorio Tabares

---

## Equipo

| Integrante | Correo |
|---|---|
| Jennifer Natalia Beltrán | jenniferbeltran.s@academia.umb.edu.co |
| David Gómez (Líder) | davidgomez.sp@academia.umb.edu.co |
| Juan Quevedo Ovalle | juanquevedo.do@academia.umb.edu.co |
| Luis Olmedo Velasco | luisvelasco.oc@academia.umb.edu.co |
| Juan Manuel Guerrero | juanmanuelguerrero.sr@academia.umb.edu.co |

---

## Visión del producto

StockIA permite a tenderos colombianos controlar su inventario desde el navegador,
ver sus métricas en tiempo real con gráficas claras, y conversar con un asistente de
inteligencia artificial (Claude de Anthropic) que consulta sus datos reales a través de
servidores MCP y responde en lenguaje natural con recomendaciones, análisis y
visualizaciones personalizadas.

---

## Stack tecnológico

| Componente | Tecnología | Versión | Propósito |
|---|---|---|---|
| Backend | Django | 5.2 | Framework principal, ORM, auth, templates |
| Frontend | Django Templates + Tailwind CDN + JS Vanilla | — | UI responsiva renderizada en servidor |
| Gráficas | Chart.js | 4.x (CDN) | Renderizado de gráficas en el cliente |
| Base de datos | PostgreSQL | 17 | Persistencia de todos los datos |
| IA | Claude API (Anthropic) | claude-sonnet-4-5 | Asistente conversacional BYOK |
| MCP PostgreSQL | @henkdz/postgresql-mcp-server | latest | Claude accede a la BD en producción |
| MCP propio | mcp (SDK Python de Anthropic) | latest | Servidor MCP con herramientas del negocio |
| Cifrado | cryptography (Fernet) | 42.x | Cifrar API keys de tenderos en BD |
| Archivos estáticos | WhiteNoise | 6.x | Servir estáticos desde Django sin Nginx |
| Despliegue | Railway | — | Hosting Django + PostgreSQL, free tier |
| MCP desarrollo | @henkdz/postgresql-mcp-server | latest | Claude Code lee la BD durante desarrollo |
| Control versiones | Git + GitHub | — | Ramas: main, develop, feature/* |

---

## Arquitectura — Clean Architecture

Cuatro capas. Cada una solo conoce a la que está debajo. Sin excepciones.

```
┌─────────────────────────────────────────────┐
│  PRESENTACIÓN                               │
│  views.py · templates/ · forms.py           │
│  JS Vanilla · Chart.js                      │
├─────────────────────────────────────────────┤
│  APLICACIÓN                                 │
│  services.py  ← toda la lógica va aquí      │
├─────────────────────────────────────────────┤
│  DOMINIO                                    │
│  models.py · validaciones · reglas negocio  │
├─────────────────────────────────────────────┤
│  INFRAESTRUCTURA                            │
│  PostgreSQL · Claude API · MCP Servers      │
│  WhiteNoise                                 │
└─────────────────────────────────────────────┘
```

**Regla absoluta:** la lógica de negocio NUNCA va en `views.py` ni en `models.py`.
Todo pasa por `services.py`. Las views llaman al servicio, reciben el resultado y
lo pasan al template. Nada más.

---

## Arquitectura de IA — MCP como capa central

El asistente de IA no recibe datos inyectados manualmente en el prompt.
Claude consulta los datos él mismo a través de dos servidores MCP que corren en producción.

### Diagrama de flujo completo

```
Tendero escribe un mensaje en el chat
              ↓
  Django view → inteligencia/services.py
              ↓
  Descifrar API key del tendero (Fernet)
              ↓
  Llamar a Claude API con:
    · key del tendero (BYOK)
    · MCP 1: postgresql-mcp-server  ──→ PostgreSQL (lectura directa)
    · MCP 2: stockia-mcp-server     ──→ Herramientas del negocio
              ↓
  Claude decide qué herramientas MCP invocar
  según la pregunta del tendero
              ↓
  Claude obtiene datos reales de la tienda
              ↓
  Claude genera respuesta JSON estructurada
              ↓
  services.py parsea el JSON
  Guarda Mensaje en la BD
              ↓
  Django renderiza texto + gráfica (Chart.js)
```

### MCP 1 — PostgreSQL (acceso directo a datos)

Servidor: `@henkdz/postgresql-mcp-server`

Le da a Claude acceso de lectura directa a todas las tablas de la tienda:
productos, categorías, stock, ventas, líneas de venta, historial de conversaciones.
Claude usa este MCP cuando necesita datos crudos que las herramientas del MCP 2 no cubren.

> **Por qué HenkDz:** el servidor oficial de Anthropic (`@modelcontextprotocol/server-postgres`)
> fue archivado en mayo 2025 y tiene una vulnerabilidad de SQL injection sin parchear.

### MCP 2 — Servidor propio (herramientas del negocio)

Servidor: `mcp_server/server.py` — construido con el SDK oficial de Python de MCP.

Expone herramientas de alto nivel que Claude puede invocar directamente.
Cada herramienta encapsula una consulta de negocio y devuelve datos listos para analizar.

**Herramientas expuestas:**

```python
@mcp.tool()
def obtener_stock_critico() -> list[dict]:
    """Productos con stock_actual <= stock_minimo * 0.5."""

@mcp.tool()
def obtener_ventas_por_periodo(inicio: str, fin: str) -> list[dict]:
    """Ventas agrupadas por día entre dos fechas ISO (YYYY-MM-DD)."""

@mcp.tool()
def obtener_top_productos(limite: int = 5, periodo: str = "mes") -> list[dict]:
    """Productos más vendidos del período: dia | semana | mes."""

@mcp.tool()
def obtener_ingresos(periodo: str = "mes") -> dict:
    """Ingresos totales del período: dia | semana | mes."""

@mcp.tool()
def obtener_resumen_negocio() -> dict:
    """Snapshot completo: stock por estado, ingresos, top productos, últimas ventas."""
```

### Formato JSON que Claude siempre devuelve

El prompt del sistema instruye a Claude a responder ÚNICAMENTE con este JSON:

```json
{
  "tipo_respuesta": "texto | grafica | mixto",
  "grafica": {
    "tipo": "bar | line | pie | doughnut",
    "titulo": "string",
    "labels": ["string"],
    "datos": [0]
  },
  "texto": "Análisis en lenguaje natural para el tendero"
}
```

`grafica` solo existe cuando `tipo_respuesta` es `grafica` o `mixto`.
`texto` siempre está presente.
Django renderiza la gráfica con Chart.js si hay datos de gráfica.

### Prompt del sistema base

```
Eres un asistente de inventario para una tienda de barrio colombiana.
Tienes acceso a los datos reales del negocio a través de herramientas MCP.
Úsalas para responder con datos precisos y actualizados.
Responde SIEMPRE en español, en lenguaje simple que un tendero entienda.

Responde ÚNICAMENTE con un objeto JSON válido con esta estructura exacta:
{
  "tipo_respuesta": "texto | grafica | mixto",
  "grafica": { "tipo": "bar|line|pie|doughnut", "titulo": "", "labels": [], "datos": [] },
  "texto": "tu análisis aquí"
}

No incluyas nada fuera del JSON. No uses markdown. Solo el objeto JSON.
```

### Lo que NO hace el sistema de IA

- **No inyecta contexto manualmente** en el prompt — para eso están los MCP.
- **No hace queries directas** desde `services.py` para alimentar a Claude — Claude consulta los datos él mismo.
- **No expone la API key** del tendero al cliente nunca — la key solo la usa Django al llamar a Claude API.
- **No usa MCP en el cliente** — los MCP corren en el servidor Django, no en el navegador.

---

## Estructura del proyecto

```
stockia/
├── manage.py
├── Procfile                        # web: gunicorn config.wsgi --log-file -
├── requirements/
│   ├── base.txt
│   └── dev.txt
├── mcp_server/                     # Servidor MCP propio del negocio
│   ├── __init__.py
│   └── server.py                   # Herramientas MCP: stock, ventas, ingresos
├── .env                            # NUNCA subir a GitHub
├── .env.example                    # plantilla para el equipo
├── .mcp.json                       # MCP de desarrollo para Claude Code (no va al repo)
├── .gitignore
├── config/
│   ├── __init__.py
│   ├── settings/
│   │   ├── base.py                 # settings comunes
│   │   └── dev.py                  # DEBUG=True, settings locales
│   ├── urls.py
│   └── wsgi.py
├── apps/
│   ├── catalogo/                   # CRUD de productos y categorías
│   ├── inventario/                 # dashboard, semáforo, alertas
│   ├── ventas/                     # registro de ventas, descuento de stock
│   ├── inteligencia/               # asistente IA, BYOK, Claude API + MCP
│   └── identidad/                  # auth Django, configuración de API key
├── templates/
│   ├── base.html
│   └── components/
└── static/
    └── js/
        └── dashboard.js
```

### Estructura interna de cada app

```
apps/catalogo/
├── __init__.py
├── admin.py
├── apps.py
├── models.py       # solo modelos y validaciones de datos
├── views.py        # solo recibir request → llamar service → render template
├── urls.py
├── forms.py
├── services.py     # TODA la lógica de negocio de esta app
└── templates/
    └── catalogo/
        ├── lista.html
        ├── detalle.html
        └── form.html
```

---

## Apps y responsabilidades

### `apps/catalogo`
**Modelos:** `Categoria`, `Producto`

```python
class Producto(models.Model):
    nombre = models.CharField(max_length=200)
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    stock_actual = models.PositiveIntegerField(default=0)
    stock_minimo = models.PositiveIntegerField(default=5)
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre

    @property
    def estado_stock(self):
        if self.stock_actual <= self.stock_minimo * 0.5:
            return "critico"
        if self.stock_actual <= self.stock_minimo:
            return "bajo"
        return "normal"
```

`estado_stock` es propiedad del modelo porque es una regla de datos pura.
Nada más va en el modelo.

---

### `apps/inventario`
Sin modelos propios. Lee desde `Producto` y `Venta`.

`services.py` expone:
- `obtener_resumen_dashboard()` → ingresos del día/semana/mes, conteo por estado de stock, top 5 productos más vendidos, últimas 10 ventas.
- `obtener_productos_por_estado(estado)` → lista filtrada por estado de stock.

El dashboard siempre está visible. No requiere API key de IA.

---

### `apps/ventas`
**Modelos:** `Venta`, `LineaVenta`

```python
class Venta(models.Model):
    fecha = models.DateTimeField(auto_now_add=True)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)

class LineaVenta(models.Model):
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name="lineas")
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT)
    cantidad = models.PositiveIntegerField()
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
```

Patrón obligatorio para registrar ventas — transacción ACID con `select_for_update()`:

```python
def registrar_venta(lineas: list[dict]) -> Venta:
    with transaction.atomic():
        venta = Venta.objects.create()
        total = 0
        for linea in lineas:
            producto = Producto.objects.select_for_update().get(pk=linea["producto_id"])
            if producto.stock_actual < linea["cantidad"]:
                raise ValueError(f"Stock insuficiente para {producto.nombre}")
            producto.stock_actual -= linea["cantidad"]
            producto.save()
            LineaVenta.objects.create(
                venta=venta,
                producto=producto,
                cantidad=linea["cantidad"],
                precio_unitario=producto.precio_unitario,
            )
            total += producto.precio_unitario * linea["cantidad"]
        venta.total = total
        venta.save()
        return venta
```

---

### `apps/inteligencia`
**Modelos:** `Conversacion`, `Mensaje`

```python
class Conversacion(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    creada_en = models.DateTimeField(auto_now_add=True)

class Mensaje(models.Model):
    class Rol(models.TextChoices):
        USUARIO = "usuario", "Usuario"
        ASISTENTE = "asistente", "Asistente"
    conversacion = models.ForeignKey(Conversacion, on_delete=models.CASCADE, related_name="mensajes")
    rol = models.CharField(max_length=20, choices=Rol.choices)
    contenido = models.TextField()
    tipo_respuesta = models.CharField(max_length=20, default="texto")  # texto | grafica | mixto
    datos_grafica = models.JSONField(null=True, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)
```

`services.py` orquesta:
1. Verificar que el usuario tiene API key configurada.
2. Descifrar la API key con Fernet.
3. Configurar los dos servidores MCP (PostgreSQL + propio).
4. Llamar a Claude API con la key del usuario (BYOK) y los MCP configurados.
5. Claude invoca las herramientas MCP que necesite para responder.
6. Parsear la respuesta JSON de Claude.
7. Guardar el `Mensaje` en la BD y devolver el resultado a la view.

---

### `apps/identidad`
Extiende `User` de Django con `PerfilTendero`.

```python
from cryptography.fernet import Fernet

class PerfilTendero(models.Model):
    usuario = models.OneToOneField(User, on_delete=models.CASCADE)
    api_key_cifrada = models.BinaryField(null=True, blank=True)

    def guardar_api_key(self, api_key_texto: str, fernet: Fernet):
        self.api_key_cifrada = fernet.encrypt(api_key_texto.encode())
        self.save()

    def obtener_api_key(self, fernet: Fernet) -> str | None:
        if not self.api_key_cifrada:
            return None
        return fernet.decrypt(bytes(self.api_key_cifrada)).decode()

    def tiene_api_key(self) -> bool:
        return bool(self.api_key_cifrada)
```

La clave Fernet vive en `settings.py` leída desde `.env`.
La API key nunca se muestra en texto plano después de guardarse.
Si el tendero no tiene API key configurada, el asistente muestra un mensaje
explicativo con los pasos para obtenerla en console.anthropic.com.

---

## MCP — tres contextos, bien separados

### MCP 1 — PostgreSQL en producción (parte del producto)

Conecta a Claude directamente con la base de datos de la tienda.
Corre como proceso aparte en el servidor junto a Django.

```json
{
  "mcpServers": {
    "postgres": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@henkdz/postgresql-mcp-server", "postgresql://user:pass@host:5432/db"]
    }
  }
}
```

### MCP 2 — Servidor propio en producción (parte del producto)

Construido con el SDK oficial de Python de MCP (`mcp` de Anthropic).
Vive en `mcp_server/server.py`. Expone herramientas de negocio de alto nivel
que Claude invoca según la pregunta del tendero.

```python
# mcp_server/server.py
from mcp.server.fastmcp import FastMCP
from apps.catalogo.models import Producto
from apps.ventas.models import Venta, LineaVenta
from django.db.models import Sum, F
from django.utils import timezone

mcp = FastMCP("stockia")

@mcp.tool()
def obtener_stock_critico() -> list[dict]:
    """Productos con stock_actual <= stock_minimo * 0.5."""
    productos = Producto.objects.filter(activo=True)
    return [
        {"nombre": p.nombre, "stock_actual": p.stock_actual, "stock_minimo": p.stock_minimo}
        for p in productos if p.estado_stock == "critico"
    ]

@mcp.tool()
def obtener_ventas_por_periodo(inicio: str, fin: str) -> list[dict]:
    """Ventas agrupadas por día entre dos fechas ISO (YYYY-MM-DD)."""
    ventas = Venta.objects.filter(fecha__date__range=[inicio, fin])
    return list(ventas.values("fecha__date").annotate(total=Sum("total")).order_by("fecha__date"))

@mcp.tool()
def obtener_top_productos(limite: int = 5, periodo: str = "mes") -> list[dict]:
    """Productos más vendidos. periodo: dia | semana | mes."""
    hoy = timezone.now()
    if periodo == "dia":
        desde = hoy.replace(hour=0, minute=0, second=0)
    elif periodo == "semana":
        desde = hoy - timezone.timedelta(days=hoy.weekday())
    else:
        desde = hoy.replace(day=1, hour=0, minute=0, second=0)
    return list(
        LineaVenta.objects.filter(venta__fecha__gte=desde)
        .values(nombre=F("producto__nombre"))
        .annotate(total_vendido=Sum("cantidad"))
        .order_by("-total_vendido")[:limite]
    )

@mcp.tool()
def obtener_ingresos(periodo: str = "mes") -> dict:
    """Ingresos totales del período: dia | semana | mes."""
    hoy = timezone.now()
    if periodo == "dia":
        desde = hoy.replace(hour=0, minute=0, second=0)
    elif periodo == "semana":
        desde = hoy - timezone.timedelta(days=hoy.weekday())
    else:
        desde = hoy.replace(day=1, hour=0, minute=0, second=0)
    total = Venta.objects.filter(fecha__gte=desde).aggregate(t=Sum("total"))["t"] or 0
    return {"periodo": periodo, "total": float(total)}

@mcp.tool()
def obtener_resumen_negocio() -> dict:
    """Snapshot completo del estado de la tienda."""
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
```

### MCP 3 — Desarrollo con Claude Code (NO es parte del producto)

`.mcp.json` en la raíz conecta Claude Code con la base de datos local para
que genere código más preciso al conocer el esquema real. Este archivo va en
`.gitignore` — cada integrante configura sus credenciales locales.

```json
{
  "mcpServers": {
    "postgres": {
      "type": "stdio",
      "command": "npx",
      "args": [
        "-y",
        "@henkdz/postgresql-mcp-server",
        "postgresql://postgres:password@localhost:5432/stockia-db"
      ]
    }
  }
}
```

Activar en Claude Code:
```bash
claude mcp add-json postgres '{
  "type": "stdio",
  "command": "npx",
  "args": ["-y", "@henkdz/postgresql-mcp-server", "postgresql://postgres:password@localhost:5432/stockia-db"]
}' --scope project

# Verificar
/mcp
```

---

## Variables de entorno

### `.env` (local, nunca al repositorio)
```env
DJANGO_SETTINGS_MODULE=config.settings.dev
SECRET_KEY=django-insecure-reemplazar-en-produccion
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
DB_NAME=stockia-db
DB_USER=postgres
DB_PASSWORD=
DB_HOST=localhost
DB_PORT=5432
FERNET_KEY=generar-con-Fernet.generate_key()
ANTHROPIC_MODEL=claude-sonnet-4-5
```

### `.env.example` (sí va al repositorio, sin valores)
```env
DJANGO_SETTINGS_MODULE=config.settings.dev
SECRET_KEY=
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
DB_NAME=
DB_USER=
DB_PASSWORD=
DB_HOST=localhost
DB_PORT=5432
FERNET_KEY=
ANTHROPIC_MODEL=claude-sonnet-4-5
```

---

## Requirements

### `requirements/base.txt`
```
Django==5.2
psycopg2-binary==2.9.9
python-decouple==3.8
whitenoise==6.7.0
cryptography==42.0.8
anthropic==0.28.0
mcp[cli]
gunicorn==22.0.0
dj-database-url==2.1.0
```

### `requirements/dev.txt`
```
-r base.txt
black==24.4.2
django-extensions==3.2.3
ipython==8.24.0
```

---

## Convenciones de código

- Python 3.12, Django 5.2, PEP 8, máximo 88 caracteres (`black`)
- Nombres de modelos, vistas, urls y templates **en español**
- Nombres de variables internas y métodos **en inglés**
- `__str__` obligatorio en todos los modelos
- `class Meta` con `verbose_name` y `verbose_name_plural` en español
- `models.TextChoices` para campos de selección fija
- No usar `null=True` en campos de texto — usar `blank=True` con `default=""`
- Templates heredan siempre de `base.html`
- Bloques en `base.html`: `title`, `content`, `extra_css`, `extra_js`
- Tailwind responsivo por defecto con clases `sm:`, `md:`, `lg:`
- Chart.js via CDN — inicialización en bloque `extra_js` del template que lo use
- Solo JS Vanilla — sin frameworks, sin jQuery, sin axios
- `fetch` para llamadas al asistente desde el cliente

---

## Comandos frecuentes

```bash
# Setup inicial
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements/dev.txt

# Generar FERNET_KEY (ejecutar una vez, guardar en .env)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Django
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver

# Migraciones
python manage.py makemigrations
python manage.py migrate

# Correr el servidor MCP propio (desarrollo)
python mcp_server/server.py

# Formatear
black .

# Claude Code
claude
```

---

## Lo que NO hacer

- No subir `.env` a GitHub
- No poner lógica en `views.py` ni en `models.py` — va en `services.py`
- No usar `print()` — usar `import logging`
- No modificar la base de datos sin migración
- No usar `@modelcontextprotocol/server-postgres` — archivado, con vulnerabilidad
- No guardar API keys de tenderos en texto plano — siempre Fernet
- No exponer la API key del tendero en templates ni en respuestas JSON al cliente
- No hacer queries manuales con `SELECT *` — usar el ORM de Django
- No inyectar contexto manualmente en el prompt de Claude — para eso están los MCP
- No commitear directamente a `main` — todo pasa por `develop` y PR

---

## Despliegue en Railway

### Archivos necesarios

**`Procfile`**
```
web: gunicorn config.wsgi --log-file -
```

**`config/settings/base.py`** — base de datos vía Railway:
```python
import dj_database_url
from decouple import config

DATABASES = {
    "default": dj_database_url.config(default=config("DATABASE_URL"))
}

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # segundo, justo después de security
    ...
]

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
```

### Variables en Railway
```
SECRET_KEY=valor-real
DEBUG=False
ALLOWED_HOSTS=.railway.app
DATABASE_URL=postgresql://...  # Railway la inyecta automáticamente al agregar PostgreSQL
FERNET_KEY=valor-real
ANTHROPIC_MODEL=claude-sonnet-4-5
DJANGO_SETTINGS_MODULE=config.settings.base
```

### Pasos de deploy
1. Conectar repositorio GitHub a Railway
2. Agregar servicio PostgreSQL desde el dashboard
3. Configurar variables de entorno
4. Cada push a `main` dispara deploy automático
5. Correr migraciones: panel Railway → servicio → Shell → `python manage.py migrate`
