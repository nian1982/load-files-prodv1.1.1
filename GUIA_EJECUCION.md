# Guia de Ejecucion

## Requisitos previos

- Docker 24+ y Docker Compose v2
- Keycloack accesible desde el host (externo)
- Servidor SFTP accesible desde el host (externo)

---

## Modo A: Backend + Frontend local (sin Docker)

```bash
cd backend/load_files

# Configurar variables de entorno
cp ../../.env.example .env
# editar .env con credenciales reales (SFTP, Keycloak, Redis)

# Crear entorno virtual e instalar
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Iniciar servidor
uvicorn load_files.api.main:app --host 0.0.0.0 --port 8001
# → http://localhost:8001 (frontend + API en el mismo puerto)
```

---

## Modo B: Backend en Docker + Frontend standalone

> **Redis**: El `docker-compose.yml` principal ya incluye Redis como servicio.
> Si prefieres usar Redis externo o el archivo `docker-compose.redis.yml`,
> **debes iniciarlo antes** de levantar el compose principal.

### 1. Redis (opcional — solo si no usas el integrado)

```bash
# Iniciar Redis aparte (debe ejecutarse ANTES del compose principal)
docker compose -f docker-compose.redis.yml up -d
```

Si usas el Redis del compose principal, salta este paso.

### 2. Configurar backend

```bash
cp backend/.env.example backend/.env
nano backend/.env
```

Ajustar credenciales. Si usas Redis externo, asegurar que `REDIS_URL` apunte a tu Redis:

```env
REDIS_URL=redis://localhost:6379/0
```

> Si usas el Redis del compose principal, `REDIS_URL` se sobreescribe automáticamente
> a `redis://redis:6379/0` (no necesita cambios en `.env`).

### 3. Construir e iniciar backend

```bash
docker compose build
docker compose up -d
# → Redis (si está integrado) + API + Worker
# → API en http://localhost:8005
# → Worker en background (sin puerto)
```

Verificar:

```bash
curl http://localhost:8005/health
# {"status":"healthy","version":"1.0.1","redis":"ok"}
```

### 4. Iniciar frontend

Desde otra terminal:

```bash
cd load-files-project
npx serve ./front -l 3000
# → http://localhost:3000
```

O con Python:

```bash
python3 -m http.server 3000 -d front
```

### 5. Abrir en el navegador

```
http://localhost:3000
```

El frontend se conecta automaticamente al backend en `http://localhost:8005`.

---

## Modo C: Backend local + Frontend standalone (mixed)

```bash
# Terminal 1: backend local
cd backend/load_files
source venv/bin/activate
uvicorn load_files.api.main:app --host 0.0.0.0 --port 8001

# Terminal 2: frontend (con API_BASE apuntando a :8001)
# editar front/app.js → API_BASE = "http://localhost:8001"
npx serve ./front -l 3000
```

---

## Comandos utiles (Docker)

```bash
# Ver logs
docker compose logs -f api
docker compose logs -f worker

# Reconstruir despues de cambios
docker compose build
docker compose up -d

# Detener todo
docker compose down

# Solo backend sin worker (para pruebas)
docker compose up -d api
```

---

## Puertos

| Servicio | Puerto | Protocolo |
|---|---|---|
| API (Docker) | 8005 | HTTP |
| API (local) | 8001 | HTTP |
| Frontend (standalone) | 3000 | HTTP |
| Redis | 6379 | TCP |

---

## Arquitectura

```
                    ┌──────────────┐
                    │   Keycloak   │
                    │  (externo)   │
                    └──────┬───────┘
                           │
Navegador ──► front:3000 ──┤
                           │
                    ┌──────▼─────────┐    ┌──────────┐
                    │  api:8005      │───►│   SFTP   │
                    │  worker (int)  │    │ (externo)│
                    └──────┬─────────┘    └──────────┘
                           │
                    ┌──────▼──────┐
                    │   Redis     │
                    │  :6379      │
                    └─────────────┘
```
