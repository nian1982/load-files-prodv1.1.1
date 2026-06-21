# Mejoras de Rendimiento - Load Files

## 1. Revertir SFTP_CHUNK_SIZE (Backend)
**Archivo**: `backend/.env`

**Problema**: Aumentar el chunk de 4MB a 8MB degradó la velocidad de subida SFTP de ~88 Mbps a ~4 Mbps para un archivo de 423 MB. El servidor SFTP remoto no manejó bien chunks más grandes, posiblemente por buffering interno.

**Qué hace**: El `SFTP_CHUNK_SIZE` controla cuántos bytes se envían por cada operación de escritura SFTP. Un valor muy grande puede causar que paramiko (librería SFTP) sature buffers intermedios o que el servidor remoto rechace paquetes grandes, forzando reintentos que matan el throughput.

**Mejora**: Se revirtió a `4194304` (4MB), restaurando el rendimiento a niveles estables de ~13-88 Mbps dependiendo de la red.

---

## 2. Timeout en XHR HTTP (Frontend)
**Archivo**: `front/app.js`

**Problema**: Archivos grandes (>400MB) fallaban con "Error de red al enviar archivo" sin dar más información. El navegador no tenía timeout configurado (`xhr.timeout = 0` por defecto), dejando la conexión indefinida pero propensa a cortes por el sistema operativo o proxy.

**Qué hace**: El `XMLHttpRequest` sube el archivo completo al backend vía HTTP. Sin timeout, si la red se degrada, el navegador espera indefinidamente o corta sin aviso.

**Mejora**: Se agregó `xhr.timeout` dinámico:

```js
xhr.timeout = Math.min(Math.max(file.size / 1000, 300000), 7200000);
```

Calcula el timeout según el peso del archivo (~1ms por byte), mínimo 5 minutos, máximo 2 horas. Además se agregó `xhr.ontimeout` para mostrar un mensaje claro ("Timeout: La subida superó el tiempo máximo").

---

## 3. Prevención de Subidas Concurrentes (Frontend)
**Archivo**: `front/app.js`

**Problema**: El usuario podía hacer clic en "Subir Archivo" múltiples veces, iniciando varias subidas simultáneas que competían por ancho de banda y recursos del servidor, degradando el rendimiento de todas.

**Qué hace**: Cada clic iniciaba un nuevo `XMLHttpRequest`, y el backend procesaba cada uno creando una tarea Celery independiente.

**Mejora**: Se agregó una bandera global `uploading` que se activa al iniciar la subida y se desactiva al mostrar el resultado. Cualquier intento de subir mientras `uploading === true` es ignorado con un mensaje en el log.

---

## 4. Corrección de Métrica speed_mbps (Backend)
**Archivo**: `backend/load_files/tasks/upload_task.py`

**Problema**: El campo `speed_mbps` se calculaba como `speed / 1024 / 1024`, que da **MiB/s** (mebibytes por segundo), no **Mbps** (megabits por segundo). El frontend lo etiquetaba como "Mbps", mostrando un valor 8x menor al real.

**Qué hace**: Determina la velocidad instantánea de la subida SFTP para mostrarla en la interfaz y calcular el ETA.

**Mejora**: Se cambió la fórmula a `avg_speed / 1000 / 1000 * 8`, convirtiendo bytes/segundo a megabits/segundo (estándar de redes). Un valor que antes mostraba "1.7 Mbps" ahora muestra correctamente "~13.6 Mbps".

---

## 5. Promedio Móvil para Velocidad y ETA (Backend)
**Archivo**: `backend/load_files/tasks/upload_task.py`

**Problema**: La velocidad instantánea fluctúa entre muestras (ej: 1.3 → 1.7 → 1.5 Mbps), haciendo que el ETA salte de 3:49 a 4:15 a 3:55, dando una experiencia errática al usuario.

**Qué hace**: El callback `progress_callback` de paramiko se invoca después de cada chunk enviado. Usar la velocidad de un solo sample es ruidoso.

**Mejora**: Se agregó un `deque(maxlen=5)` que almacena los últimos 5 samples de velocidad y calcula el promedio. El ETA ahora usa `avg_speed` en lugar de `speed` instantánea, dando valores estables y predecibles.

---

## 6. Tiempo Total Real (Frontend)
**Archivo**: `front/app.js`

**Problema**: El campo `upload_time_seconds` solo medía el tiempo de subida SFTP (dentro del worker Celery). El usuario no veía cuánto tomó el proceso completo: desde que presionaba "Subir Archivo" hasta que veía la tarjeta de resultado.

**Qué hace**: La respuesta del WebSocket incluye el tiempo SFTP, pero no contabiliza el HTTP upload, el encolamiento en Celery, ni el overhead de procesamiento.

**Mejora**: Se captura `Date.now()` al inicio de `uploadFile()` y en `showResult()` se calcula la diferencia. La tabla de resultado ahora muestra dos filas:

| Tiempo SFTP | 284s (solo subida SFTP) |
|---|---|
| **Tiempo total** | **286s** (desde el clic hasta el resultado) |

---

## 7. Limpieza de Estado Visual (Frontend)
**Archivo**: `front/app.js`

**Problema**: Al iniciar una nueva subida, el resultado y los logs de la subida anterior permanecían en el DOM (ocultos pero acumulados). Si ocurría un error temprano, el resultado viejo quedaba visible.

**Qué hace**: El `#result-content` se llenaba con HTML nuevo en cada `showResult()`, pero nunca se limpiaba explícitamente. El `#progress-log` acumulaba líneas sin límite.

**Mejora**: Al iniciar `uploadFile()`, se limpian ambos contenedores:

```js
document.getElementById("result-content").innerHTML = "";
document.getElementById("progress-log").innerHTML = "";
```

Al navegar a la vista de carga, también se oculta y limpia el resultado.

---

## Resumen de Impacto

| Mejora | Impacto |
|--------|---------|
| Chunk 4MB | Velocidad SFTP estable |
| XHR Timeout | Archivos grandes ya no fallan silenciosamente |
| Flag concurrente | Sin degradación por subidas paralelas |
| Métricas correctas | Velocidad real (Mbps, no MiB/s) |
| Promedio móvil | ETA sin saltos |
| Tiempo total | Visibilidad del overhead real |
| Limpieza visual | Sin residuos de subidas anteriores |
