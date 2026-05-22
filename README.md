# StockIA

Sistema web para gestion de inventario, ventas y asistencia inteligente para tiendas de barrio, construido con Django.

## Caracteristicas

- Autenticacion de usuarios para tenderos.
- Gestion de inventario y catalogo de productos.
- Registro y consulta de ventas.
- Dashboard de negocio.
- Asistente inteligente con soporte de herramientas del negocio.
- Cifrado de API keys del usuario con Fernet.

## Stack tecnico

- Python 3.12+
- Django 5.2
- PostgreSQL
- WhiteNoise (archivos estaticos)
- Gunicorn (produccion)

## Estructura principal

- apps/identidad: login, registro y configuracion de proveedor IA.
- apps/inventario: dashboard e indicadores.
- apps/catalogo: productos y catalogo.
- apps/ventas: flujo de ventas.
- apps/inteligencia: chat asistido con herramientas del negocio.
- config/settings: configuracion base y de desarrollo.

## Requisitos previos

1. Python 3.12 o superior.
2. PostgreSQL instalado y ejecutandose.
3. Pip actualizado.

## Instalacion local

1. Clona el repositorio y entra al proyecto.
2. Crea y activa un entorno virtual.
3. Instala dependencias.

### Windows (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements/dev.txt
```

## Variables de entorno

Crea un archivo .env en la raiz del proyecto con este contenido:

```env
DJANGO_SETTINGS_MODULE=config.settings.dev
SECRET_KEY=django-insecure-cambia-esta-clave
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

DB_NAME=stockia
DB_USER=postgres
DB_PASSWORD=tu_password
DB_HOST=localhost
DB_PORT=5432

# Genera una clave con:
# python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
FERNET_KEY=pega_aqui_tu_fernet_key

# Opcional
ANTHROPIC_MODEL=claude-sonnet-4-5
```

Nota: en desarrollo local se usan DB_NAME, DB_USER, DB_PASSWORD, DB_HOST y DB_PORT. En despliegue (ej. Railway), normalmente se usa DATABASE_URL.

## Base de datos

1. Crea una base de datos PostgreSQL, por ejemplo: stockia.
2. Ejecuta migraciones:

```powershell
python manage.py migrate
```

3. (Opcional) Crea un superusuario:

```powershell
python manage.py createsuperuser
```

## Ejecutar en local

```powershell
python manage.py runserver
```

La app quedara disponible en:

- http://127.0.0.1:8000

Ruta inicial:

- /identidad/login/

## Comandos utiles

```powershell
# Crear migraciones
python manage.py makemigrations

# Aplicar migraciones
python manage.py migrate

# Formatear codigo
black .

# Servidor MCP (desarrollo)
python mcp_server/server.py
```

## Produccion (referencia)

El proyecto ya incluye Procfile para correr con Gunicorn:

```txt
web: gunicorn config.wsgi --log-file -
```

Recomendaciones minimas:

1. Definir DEBUG=False.
2. Configurar ALLOWED_HOSTS con tu dominio.
3. Definir SECRET_KEY segura.
4. Configurar DATABASE_URL.
5. Ejecutar collectstatic antes de publicar (si aplica en tu plataforma).

## Solucion de problemas rapida.

- Error de conexion a PostgreSQL:
  - Verifica que el servicio este activo.
  - Revisa DB_HOST, DB_PORT, DB_USER y DB_PASSWORD.
- Error por FERNET_KEY:
  - Genera una nueva clave valida y actualiza .env.
- Error por modulo no encontrado:
  - Activa el entorno virtual y reinstala dependencias.

## Licencia

Uso interno del proyecto...
