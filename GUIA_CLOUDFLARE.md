# Guia de Exposicion en Cloudflare

## Componentes a exponer

| Componente | Puerta de salida | Se expone publicamente? |
|---|---|---|
| Frontend (`front/`) | Puerto `3000` (sin Docker) | **Si** — los usuarios lo cargan en el navegador |
| Backend API (`api:8005`) | Puerto `8005` | **Si** — el frontend lo consume via HTTP + WebSocket |
| Worker (Celery) | Sin puerto | **No** — solo habla con Redis y SFTP |
| Redis (`redis:6379`) | Puerto `6379` | **No** — solo lo usan API y Worker internamente |
| Keycloak (externo) | Variable | **No** — solo el backend lo llama internamente |

---

## Estrategia: config.js

Las URLs del frontend (`API_BASE`, `WS_BASE`) estan separadas en `front/config.js`
y se cargan **antes** que `app.js` en el HTML:

```html
<script src="config.js"></script>
<script src="app.js"></script>
```

Para cada entorno creas un `config.*.js` distinto y activas el que corresponda:

| Archivo | Entorno | `API_BASE` | `WS_BASE` |
|---|---|---|---|
| `config.js` (por defecto) | Local dev | `http://localhost:8005` | `ws://localhost:8005` |
| `config.cloudflare.js` | Cloudflare (mismo origen) | `""` | `"wss://" + location.host` |
| `config.production.js` | Produccion con dominio | `""` | `"wss://" + location.host` |

**En las variantes siguientes** solo se indica que valores poner en `config.js`.
El archivo `app.js` nunca se toca.

---

## Resumen de variantes

| # | Variante | Frontend | Backend | Infra extra | Cambios codigo | Uso |
|---|---|---|---|---|---|---|---|
| 1 | Tunnel solo al frontend | `trycloudflare` → :3000 | Local (`localhost:8005`) | Nada | Ninguno | **Solo pruebas — el backend no es accesible desde afuera** |
| 2 | Tunnel solo al front con nginx | nginx :3001 sirve front + proxy al backend | Mismo origen | nginx | `config.js` | **PRODUCCION** |
| 3 | Dos tunnels separados | `trycloudflare` → :3000 | `trycloudflare` → :8005 | Nada | `config.js` | Pruebas |
| 4 | Tunnel unico con nginx | `trycloudflare` → nginx :3001 → front + backend | Mismo origen | nginx | `config.js` | Pruebas / Produccion |
| 5 | Tunnel unico directo a FastAPI | FastAPI :8005 sirve estaticos + API | Mismo origen | Nada | `main.py` + `config.js` | Pruebas rapidas |
| 6 | Tunnel persistente (systemd) | nginx :3001 sirve front + proxy backend | Mismo origen | nginx + systemd | `config.js` | **PRODUCCION** |

---

## Modos de tunnel en Cloudflare

`cloudflared` acepta dos modos de ejecucion:

### Modo ad-hoc (`trycloudflare.com`) — URLs efimeras

```bash
cloudflared tunnel --url <local-url>
```

- No requiere autenticacion ni cuenta Cloudflare
- Genera una URL publica aleatoria (`https://<hash>.trycloudflare.com`)
- **La URL cambia cada vez que se reinicia** el comando
- Ideal para pruebas rapidas, demostraciones, o cuando no tienes dominio propio
- El tunnel se cierra al cerrar la terminal (sin `Ctrl+C` de por medio, vive ~8h)

### Modo con dominio propio (`--hostname`)

```bash
cloudflared tunnel --url <local-url> --hostname app.tudominio.com
```

- Requiere autenticar: `cloudflared tunnel login`
- Usa un dominio que hayas configurado en Cloudflare DNS
- La URL es fija: `https://app.tudominio.com`
- El tunnel se cierra al cerrar la terminal igual que el modo ad-hoc

### Modo persistente (tunnel con nombre + systemd)

```bash
cloudflared tunnel create load-files
cloudflared tunnel route dns load-files app.tudominio.com
sudo cloudflared service install
```

- El tunnel se inicia como servicio del sistema
- Sobrevive a reinicios del servidor
- Requiere dominio propio

---

## Variante 1: Tunnel solo al frontend (solo pruebas, sin backend expuesto)

```
cloudflared tunnel → npx serve :3000 (frontend)
                     Backend solo accesible desde localhost:8005
```

> **Limitacion:** el frontend se ve desde cloudflare pero `API_BASE` apunta
> a `localhost:8005` en el navegador, que no existe desde otra maquina.
> Solo sirve para probar la interfaz grafica si el backend corre en la misma
> maquina desde donde abres el navegador.

```bash
# Iniciar backend (local o Docker)
docker compose up -d

# Iniciar frontend
npx serve ./front -l 3000

# Exponer frontend via Cloudflare
cloudflared tunnel --url http://localhost:3000
```

**Cambios en codigo:** ninguno (usas `API_BASE=http://localhost:8005` tal cual).

---

## Variante 2: Tunnel solo al frontend con nginx (backend expuesto localmente)

```
cloudflared tunnel → nginx :3001
                     ├── / → frontend (estaticos)
                     └── /api /login /upload /ws /health → localhost:8005
```

> El frontend se conecta al backend con rutas relativas (mismo origen).
> Para que funcione desde afuera, el backend **debe** ser accesible desde
> el navegador — como esta detras de nginx en el mismo servidor, funciona.

### 1. Configurar nginx

Ver config completa en la **Variante 4**.

### 2. Crear `front/config.cloudflare.js`

```js
const API_BASE = "";
const WS_BASE = "wss://" + location.host;
```

Y activarlo:

```bash
cp front/config.cloudflare.js front/config.js
```

### 3. Iniciar

```bash
# Backend
docker compose up -d

# Frontend por nginx y tunnel
sudo systemctl reload nginx
cloudflared tunnel --url http://localhost:3001
```

Con dominio propio:

```bash
cloudflared tunnel --url http://localhost:3001 --hostname app.tudominio.com
```

---

## Variante 3: Dos tunnels separados

```
Terminal 1: cloudflared → npx serve :3000  → https://abc.trycloudflare.com
Terminal 2: cloudflared → FastAPI :8005    → https://xyz.trycloudflare.com
```

**Cuando usar:** pruebas rapidas, cuando quieres probar el flujo completo
desde otra maquina sin instalar nada extra.

### Paso a paso con `trycloudflare.com`

```bash
# Terminal 1 — Backend (asegurar que corre en :8005)
docker compose up -d

# Terminal 2 — Tunnel del backend
cloudflared tunnel --url http://localhost:8005
# Copiar la URL: https://xyz789.trycloudflare.com

# Terminal 3 — Frontend + su tunnel
npx serve ./front -l 3000
cloudflared tunnel --url http://localhost:3000
# Copiar la URL: https://abc123.trycloudflare.com
```

### Ajustar `front/config.js`

```js
const API_BASE = "https://xyz789.trycloudflare.com";
const WS_BASE  = "wss://xyz789.trycloudflare.com";
```

Reemplaza `xyz789` con el hash real que te dio `cloudflared`.

### Habilitar WebSocket en Cloudflare Dashboard

1. Ir a `https://dash.cloudflare.com/`
2. Seleccionar el dominio (si usas `trycloudflare.com` no aplica)
3. `Red → WebSocket → On`

> En `trycloudflare.com` WebSocket funciona por defecto sin config.

### Limpieza

```bash
# Detener tunnels con Ctrl+C en cada terminal
```

---

## Variante 4: Tunnel unico + nginx (recomendada para pruebas y produccion)

```
cloudflared tunnel → nginx :3001
                     ├── / (estaticos)        → front/
                     ├── /login               → localhost:8005
                     ├── /upload              → localhost:8005
                     ├── /health              → localhost:8005
                     └── /ws (WebSocket)      → localhost:8005
```

Un solo tunnel, un solo punto de entrada, mismo origen (sin CORS).

### 1. Instalar nginx

```bash
# Debian/Ubuntu
sudo apt install nginx

# RHEL/Fedora
sudo dnf install nginx
```

### 2. Configurar nginx

Crear `/etc/nginx/sites-available/load-files` o `/etc/nginx/conf.d/load-files.conf`:

```nginx
upstream backend {
    server 127.0.0.1:8005;
}

server {
    listen 3001;

    # ── Frontend estatico ──
    root /ruta/completa/a/load-files-project/front;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    # ── Backend API ──
    location /login {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /upload {
        client_max_body_size 500m;
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /health {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # ── WebSocket ──
    location /ws {
        proxy_pass http://backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 86400;
    }
}
```

> Reemplaza `/ruta/completa/a/load-files-project/front` por la ruta absoluta
> en tu servidor.

Activar:

```bash
sudo ln -s /etc/nginx/sites-available/load-files /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 3. Crear `front/config.cloudflare.js`

```js
const API_BASE = "";
const WS_BASE = "wss://" + location.host;
```

Y activarlo:

```bash
cp front/config.cloudflare.js front/config.js
```

### 4. Iniciar

```bash
# Backend
docker compose up -d

# Verificar que nginx sirve localmente
curl http://localhost:3001/health

# Tunnel con URL efimera
cloudflared tunnel --url http://localhost:3001

# O con dominio propio
cloudflared tunnel --url http://localhost:3001 --hostname app.tudominio.com
```

---

## Variante 5: Tunnel unico directo a FastAPI (backend sirve frontend)

```
cloudflared tunnel → FastAPI :8005
                     ─── FastAPI sirve estaticos + API
```

Sin nginx, sin `npx serve`. Util cuando quieres minimizar procesos.

### 1. Modificar `backend/load_files/api/main.py`

Agregar despues de los `include_router`:

```python
from fastapi.staticfiles import StaticFiles
from pathlib import Path

front_path = Path(__file__).resolve().parent.parent.parent.parent / "front"
if front_path.exists():
    app.mount("/", StaticFiles(directory=str(front_path), html=True), name="front")
```

### 2. Crear `front/config.cloudflare.js`

```js
const API_BASE = "";
const WS_BASE = "wss://" + location.host;
```

Y activarlo:

```bash
cp front/config.cloudflare.js front/config.js
```

### 3. Iniciar

```bash
# Con Docker
docker compose up -d

# O local
cd backend/load_files && source venv/bin/activate
uvicorn load_files.api.main:app --host 0.0.0.0 --port 8005

# Tunnel
cloudflared tunnel --url http://localhost:8005
```

---

## Variante 6: Tunnel persistente con systemd (PRODUCCION)

Igual que la Variante 4 (nginx) pero el tunnel corre como servicio del sistema.

```bash
# 1. Autenticar cloudflared
cloudflared tunnel login

# 2. Crear el tunnel
cloudflared tunnel create load-files
# → Crea ~/.cloudflared/<ID>.json

# 3. Asignar DNS
cloudflared tunnel route dns load-files app.tudominio.com

# 4. Configurar ingress
# Editar ~/.cloudflared/config.yml:
```

```yaml
tunnel: <TUNNEL-ID>
credentials-file: /root/.cloudflared/<TUNNEL-ID>.json
ingress:
  - hostname: app.tudominio.com
    service: http://localhost:3001
  - service: http_status:404
```

```bash
# 5. Instalar como servicio del sistema
sudo cloudflared service install

# 6. Verificar
sudo systemctl status cloudflared

# 7. Logs
sudo journalctl -u cloudflared -f
```

> El tunnel se reinicia automaticamente si el servidor se reinicia.
> Para detenerlo: `sudo systemctl stop cloudflared`

---

## Diferencias por tipo de URL

| Aspecto | `trycloudflare.com` (efimera) | `--hostname` (dominio propio) | Tunnel persistente |
|---|---|---|---|
| Registro | No requiere | `cloudflared tunnel login` | `cloudflared tunnel login` + `create` |
| URL | `https://<hash>.trycloudflare.com` | `https://app.tudominio.com` | `https://app.tudominio.com` |
| Persistencia | Se cierra al cerrar terminal | Se cierra al cerrar terminal | Servicio systemd (siempre activo) |
| SSL | Automatico | Automatico | Automatico |
| WebSocket | Funciona por defecto | Requiere activarlo en Dashboard | Requiere activarlo en Dashboard |
| Ideal para | Demos, pruebas rapidas | Pruebas con URL fija | Produccion |

---

## Mantener el entorno LOCAL como esta

`front/config.js` ya tiene los valores por defecto para desarrollo local.
Ninguna variante de las anteriores afecta esto. Puedes seguir usando
`GUIA_EJECUCION.md` sin cambios:

```bash
# Modo Local (Backend Docker + Frontend standalone)
docker compose up -d
npx serve ./front -l 3000
# → http://localhost:3000 (API_BASE=http://localhost:8005 en config.js)
```

### Alternativa: un solo config.js automatico

Si prefieres un unico `config.js` que funcione en local y cloudflare sin
tener que renombrar archivos, usa deteccion por hostname:

```js
const IS_CLOUDFLARE = location.hostname !== "localhost"
                   && location.hostname !== "127.0.0.1";
const API_BASE = IS_CLOUDFLARE ? "" : "http://localhost:8005";
const WS_BASE  = IS_CLOUDFLARE ? "wss://" + location.host : "ws://localhost:8005";
```

Esto funciona sin cambios en cualquier variante donde frontend y backend
compartan origen (Variantes 2, 4, 5, 6).

---

## Tabla comparativa completa

| Variante | Frontend | Backend | Infra extra | Cambios codigo | URL | Persistencia | Recomendado |
|---|---|---|---|---|---|---|---|---|
| 1 — Tunnel solo front | `trycloudflare` → :3000 | Localhost solo | Nada | Ninguno | Efimera | Sesion | Pruebas UI |
| 2 — Tunnel+nginx solo front | `trycloudflare` → nginx :3001 | Mismo origen (nginx) | nginx | `config.js` | Efimera o dominio | Sesion | Pruebas |
| 3 — Dos tunnels | `trycloudflare` → :3000 + :8005 | Cross-origin | Nada | `config.js` | Efimera | Sesion | Pruebas flujo completo |
| 4 — Un tunnel + nginx | `trycloudflare` → nginx :3001 | Mismo origen (nginx) | nginx | `config.js` | Efimera o dominio | Sesion | **Pruebas** |
| 5 — Un tunnel + FastAPI | `trycloudflare` → FastAPI :8005 | Mismo origen | Nada | `main.py` + `config.js` | Efimera o dominio | Sesion | Pruebas rapidas |
| 6 — Tunnel persistente + nginx | Dominio propio → nginx :3001 | Mismo origen (nginx) | nginx + systemd | `config.js` | Dominio propio | **Siempre** | **PRODUCCION** |
