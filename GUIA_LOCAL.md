# Guia Local — Docker para pruebas con 5 usuarios concurrentes

## Requisitos previos

- Docker 24+ y Docker Compose v2
- Puerto `8001` libre (API)
- Puerto `6379` libre (Redis)
- Archivo `backend/.env` configurado con credenciales SFTP y Keycloak

## Configuracion

El archivo `backend/.env` ya contiene las variables necesarias. Asegurate de que apunte a servicios accesibles desde los contenedores Docker:

```env
# SFTP — si corre local, usa host.docker.internal
SFTP_HOST=host.docker.internal
SFTP_PORT=4223
SFTP_USER=sftpuser
SFTP_PASS=Bogota2026!
SFTP_UPLOAD_DIR=/upload

# Keycloak — si corre local, usa host.docker.internal
KEYCLOAK_URL=http://host.docker.internal:8080
KEYCLOAK_REALM=muhoco
KEYCLOAK_CLIENT_ID=api-load-files
```

> **Nota:** `host.docker.internal` permite que el contenedor acceda a servicios en tu maquina host.
> Tambien puedes usar la IP de tu red local si lo prefieres.

## Uso

### 1. Construir e iniciar

```bash
docker compose -f docker-compose.local.yml up -d
```

Esto levanta tres servicios:
- **redis** — broker y backend de Celery + pub/sub para WebSocket
- **api** — FastAPI con 5 workers de uvicorn en `http://localhost:8001`
- **worker** — Celery worker con concurrencia 5

### 2. Verificar health

```bash
curl http://localhost:8001/health
```

Respuesta esperada:
```json
{"status":"healthy","version":"1.0.1","redis":"ok"}
```

### 3. Probar upload

```bash
curl -X POST http://localhost:8001/upload \
  -H "Authorization: Bearer <TOKEN_JWT>" \
  -F "tipo_archivo=REPOSITORIO" \
  -F "fecha=2026-05-26" \
  -F "file=@/ruta/al/archivo.xlsx"
```

Respuesta esperada:
```json
{"task_id":"<uuid>","status":"queued","message":"File received and queued for upload"}
```

### 4. Ver progreso por WebSocket (opcional)

```bash
# Instalar wscat si no lo tienes
npm install -g wscat

# Conectar al WebSocket con el task_id devuelto
wscat -c "ws://localhost:8001/ws/<task_id>?token=<TOKEN_JWT>"
```

### 5. Ver logs

```bash
# Todos los servicios
docker compose -f docker-compose.local.yml logs -f

# Solo API
docker compose -f docker-compose.local.yml logs -f api

# Solo Worker
docker compose -f docker-compose.local.yml logs -f worker
```

### 6. Detener todo

```bash
docker compose -f docker-compose.local.yml down -v
```

La bandera `-v` elimina el volumen de Redis. Omite `-v` si quieres conservar los datos.

## Limite de 5 usuarios concurrentes

Se implementa a nivel de infraestructura:

| Componente | Configuracion | Explicacion |
|---|---|---|
| **API (uvicorn)** | `--workers 5` | 5 procesos independientes manejando requests HTTP. Cada proceso puede atender un upload simultaneo. |
| **Worker (Celery)** | `-c 5` | 5 procesos hijo procesando uploads a SFTP en paralelo. |

Cada upload sigue este flujo:

```
Usuario ──► POST /upload ──► Uvicorn worker (1 de 5) ──► Recibe archivo ──► Encola en Celery
                                                                                │
                                                                     Celery worker (1 de 5) ──► Sube a SFTP
```

Con 5 usuarios simultaneos:
1. Los 5 requests HTTP son recibidos por los 5 workers de uvicorn
2. Cada request encola una tarea en Redis
3. Los 5 workers de Celery toman las 5 tareas y suben a SFTP en paralelo

Si llega un 6to usuario, uvicorn lo encola en el sistema operativo hasta que un worker se libere.

## Puertos

| Servicio | Host | Contenedor | Protocolo |
|---|---|---|---|
| API | 8001 | 8005 | HTTP |
| WebSocket | 8001 | 8005 | WS |
| Redis | 6379 | 6379 | TCP |

## Frontend

El frontend ya apunta a `http://localhost:8005` (`front/app.js` linea 2).

Para iniciarlo:

```bash
# Opcion 1 — con Node
npx serve ./front -l 3000

# Opcion 2 — con Python
python3 -m http.server 3000 -d front
```

Luego abre `http://localhost:3000` en el navegador.

## Comandos utiles

```bash
# Reconstruir despues de cambios en el codigo
docker compose -f docker-compose.local.yml build
docker compose -f docker-compose.local.yml up -d

# Solo API + Redis (sin worker)
docker compose -f docker-compose.local.yml up -d redis api

# Ver uso de recursos
docker stats load_files_api_local load_files_worker_local load_files_redis_local
```
