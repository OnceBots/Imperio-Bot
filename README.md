# 🏛️ Imperio Otomano Bot — Final

Bot de administración y moderación para grupos/supergrupos de Telegram con estilo de panel tipo Group Help: comandos clásicos + panel inline, ayuda por categorías, Staff, filtros, purga, estadísticas y limpieza automática de mensajes de servicio.

## Funciones principales

- Comandos originales preservados: `/panel`, `/promotestaff`, `/etiqueta`, `/tag`, `/titulo`, `/del`, `/ban`, `/unban`, `/mute`, `/unmute`, `/warn`, `/unwarn`, `/delall`, `/pin`, `/unpin`, `/leyes`, `/reglas`, `/aportes`, `/topaportes`, `/s` y `.s`.
- `/help`, `/ayuda` y `/comandos` con menú inline categorizado.
- Eliminación automática de mensajes de servicio: usuarios que entran, salen, son expulsados, notificaciones de fijado/desfijado, cambios de título/foto, boosts, cambios de temporizador, temas del foro y otros eventos de servicio recibidos por el Bot API. Se elimina la notificación del servicio, no el contenido que fue fijado.
- Purga manual por usuario y purga automática de multimedia con ciclo configurable.
- Filtro anti-enlaces y lista negra por palabras.
- Anti-bot básico: bloquea bots no autorizados agregados por usuarios que no sean administradores.
- Staff persistente en MongoDB, con permisos limitados a moderación y gestión de mensajes; el bot no les concede invitaciones ni promoción de otros administradores.
- Auditoría básica de acciones administrativas.
- Health check para Render.
- Dockerfile, `render.yaml`, `.env.example`, pruebas y CI.

## Requisitos

Python 3.11+ recomendado. El proyecto usa aiogram 3.31.x y PyMongo Async. La API reciente de Telegram permite a los bots borrar mensajes de servicio y ofrece `deleteMessages` para lotes de hasta 100 mensajes; existen límites de antigüedad y algunos mensajes de creación no se pueden borrar. Ver la documentación oficial de Telegram y aiogram para esos límites. 

## Variables de entorno

Copia `.env.example` a `.env` en local. En Render se configuran en **Environment**.

```env
BOT_TOKEN=123456:ABC
MONGO_URI=mongodb+srv://usuario:password@cluster.mongodb.net/?retryWrites=true&w=majority
DB_NAME=imperio_bot
OWNER_IDS=123456789
PORT=10000
LOG_LEVEL=INFO
AUTO_DELETE_SERVICE_MESSAGES=true
AUTO_DELETE_JOIN_MESSAGES=true
AUTO_DELETE_LEAVE_MESSAGES=true
AUTO_DELETE_PIN_MESSAGES=true
AUTO_DELETE_GROUP_CHANGE_MESSAGES=true
AUTO_DELETE_OTHER_SERVICE_MESSAGES=true
AUTO_CLEANUP_ENABLED=true
AUTO_CLEANUP_HOURS=12
NOTICE_TTL=6
MAX_WARNINGS=3

# Si tu grupo usa un filtro muy estricto, puedes desactivarlo con false.
FILTER_LINKS=true
ANTI_BOT=true

# Opcional: tiempo máximo de mensajes que la purga intenta borrar.
CLEANUP_BATCH_SIZE=100
```

## Arranque local

```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
copy .env.example .env
python main.py
```

## Render

Crear un **Web Service**. El servicio escucha en `0.0.0.0:$PORT`. Configura al menos `BOT_TOKEN`, `MONGO_URI`, `DB_NAME` y `OWNER_IDS`. `render.yaml` contiene un ejemplo de despliegue.

## Permisos del bot en Telegram

Para que la moderación y la limpieza funcionen, el bot debe ser administrador del grupo con los permisos que correspondan. Como mínimo, para borrar mensajes necesita `can_delete_messages`; para ban/mute necesita `can_restrict_members`; para fijar necesita `can_pin_messages`. Para recibir solicitudes de ingreso necesita `can_invite_users`.

## Compatibilidad de base de datos

La colección conserva nombres simples (`groups`, `stats`, `admins`, `warns`, `cleanup_queue`, `audit_logs`) para que sea fácil migrar datos del proyecto anterior.
