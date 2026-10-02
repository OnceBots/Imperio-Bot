# Migración desde la versión anterior

El bot conserva los nombres de las colecciones principales de MongoDB: `groups`, `stats`, `admins`, `warns` y `cleanup_queue`.

Antes de actualizar en producción:

1. Haz una copia de seguridad de MongoDB.
2. Configura las variables de entorno.
3. Añade el bot como administrador con los permisos necesarios.
4. Despliega la nueva versión.
5. Revisa `/panel` y `help`.

Los mensajes de servicio se eliminan automáticamente de forma independiente de la purga multimedia. La eliminación del mensaje de servicio no elimina el mensaje que fue fijado: elimina la notificación de Telegram sobre el fijado.
