console.log("load_files app.js v2 loaded");
const CLIENT_ID = "api-load-files";
const REQUIRED_ROLE = "load_files.upload";
let accessToken = null;
let progressWs = null;
let uploading = false;
let uploadStartTime = 0;

function decodeToken(token) {
    try {
        return JSON.parse(atob(token.split(".")[1]));
    } catch {
        return null;
    }
}

function hasRequiredRole(token) {
    const payload = decodeToken(token);
    if (!payload) return false;
    const roles = payload.resource_access?.[CLIENT_ID]?.roles || [];
    return roles.includes(REQUIRED_ROLE);
}

function getUserName(token) {
    const p = decodeToken(token);
    return p?.preferred_username || p?.sub || "?";
}

function showView(viewId) {
    const views = ["login-view", "forbidden-view", "upload-view"];
    for (const v of views) {
        document.getElementById(v).style.display = v === viewId ? "block" : "none";
    }
}

function navigate() {
    const hash = location.hash || "#/";
    if (!accessToken) {
        showView("login-view");
        document.getElementById("app-title").textContent = "Cargar Archivos - SFTP";
        return;
    }
    if (!hasRequiredRole(accessToken)) {
        showView("forbidden-view");
        document.getElementById("app-title").textContent = "Acceso Denegado";
        return;
    }
    if (hash === "#/load") {
        showView("upload-view");
        document.getElementById("app-title").textContent = "Cargar Archivos - SFTP";
        document.getElementById("result-card").style.display = "none";
        document.getElementById("result-content").innerHTML = "";
    } else {
        location.hash = "#/load";
    }
}

window.addEventListener("hashchange", navigate);

async function login(event) {
    event.preventDefault();
    const btn = document.getElementById("login-submit");
    const errorEl = document.getElementById("login-error");
    const username = document.getElementById("username").value;
    errorEl.style.display = "none";
    btn.disabled = true;
    btn.textContent = "Ingresando...";

    try {
        const resp = await fetch(API_BASE + "/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, password: document.getElementById("password").value }),
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || "Error al iniciar sesion");

        accessToken = data.access_token;
        document.getElementById("user-info").textContent = "Usuario: " + username;
        document.getElementById("user-info").style.display = "inline";
        document.getElementById("logout-btn").style.display = "inline";

        if (hasRequiredRole(accessToken)) {
            location.hash = "#/load";
        } else {
            location.hash = "#/";
        }
        navigate();
    } catch (err) {
        errorEl.textContent = err.message;
        errorEl.style.display = "block";
    } finally {
        btn.disabled = false;
        btn.textContent = "Ingresar";
    }
}

function logout() {
    disconnectWs();
    accessToken = null;
    document.getElementById("user-info").style.display = "none";
    document.getElementById("logout-btn").style.display = "none";
    document.getElementById("result-card").style.display = "none";
    document.getElementById("progress-card").style.display = "none";
    document.getElementById("upload-form").reset();
    location.hash = "#/";
    navigate();
}

function disconnectWs() {
    if (progressWs) {
        try { progressWs.close(); } catch (_) {}
        progressWs = null;
    }
}

function formatBytes(bytes) {
    if (bytes === 0) return "0 B";
    const units = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return (bytes / Math.pow(1024, i)).toFixed(i > 0 ? 2 : 0) + " " + units[i];
}

function formatSpeed(speedMbps) {
    if (!speedMbps || speedMbps <= 0) return "";
    if (speedMbps < 1) return (speedMbps * 1000).toFixed(0) + " Kbps";
    return speedMbps.toFixed(1) + " Mbps";
}

function formatEta(seconds) {
    if (!seconds || seconds <= 0) return "";
    if (seconds < 60) return Math.round(seconds) + "s";
    const m = Math.floor(seconds / 60);
    const s = Math.round(seconds % 60);
    return m + "m " + s + "s";
}

function addLog(msg) {
    const log = document.getElementById("progress-log");
    const line = document.createElement("div");
    line.textContent = "> " + msg;
    log.appendChild(line);
    log.scrollTop = log.scrollHeight;
}

function showProgress(phase, percent, speed, eta) {
    const card = document.getElementById("progress-card");
    const bar = document.getElementById("progress-bar");
    const phaseEl = document.getElementById("progress-phase");
    const percentEl = document.getElementById("progress-percent");
    const speedEl = document.getElementById("progress-speed");
    const etaEl = document.getElementById("progress-eta");

    card.style.display = "block";
    document.getElementById("result-card").style.display = "none";

    phaseEl.textContent = phase || "Procesando...";
    bar.style.width = Math.min(percent, 100) + "%";

    bar.className = "progress-bar";
    if (percent >= 100) {
        bar.classList.add("complete");
    } else if (phase && phase.toLowerCase().includes("sftp")) {
        bar.classList.add("sftp-phase");
    } else {
        bar.classList.add("upload-phase");
    }

    percentEl.textContent = percent.toFixed(1) + "%";
    speedEl.textContent = speed ? formatSpeed(speed) : "";
    etaEl.textContent = eta ? "ETA: " + formatEta(eta) : "";
}

function showResult(data) {
    uploading = false;
    document.getElementById("progress-card").style.display = "none";
    disconnectWs();

    const card = document.getElementById("result-card");
    const content = document.getElementById("result-content");
    const isSuccess = data.success;
    card.className = "card result-card " + (isSuccess ? "success" : "failure");

    let html = "<table>";
    html += "<tr><td>Resultado</td><td><strong>" + (isSuccess ? "EXITOSO" : "FALLIDO") + "</strong></td></tr>";
    html += "<tr><td>UUID</td><td style='font-family:monospace;font-size:.8rem'>" + (data.id || "") + "</td></tr>";
    html += "<tr><td>Archivo</td><td>" + (data.file_name || "") + "</td></tr>";
    html += "<tr><td>Extension</td><td>" + (data.extension || "") + "</td></tr>";
    html += "<tr><td>Tamaño</td><td>" + (data.size_display || "") + "</td></tr>";
    html += "<tr><td>Tipo</td><td>" + (data.tipo_archivo || "") + "</td></tr>";
    html += "<tr><td>Fecha</td><td>" + (data.fecha || "") + "</td></tr>";
    html += "<tr><td>Ruta SFTP</td><td style='font-family:monospace;font-size:.8rem'>" + (data.upload_path || "") + "</td></tr>";
    html += "<tr><td>Tiempo SFTP</td><td>" + (data.upload_time_seconds || "0") + "s</td></tr>";
    const totalSec = uploadStartTime ? ((Date.now() - uploadStartTime) / 1000).toFixed(1) : 0;
    html += "<tr><td>Tiempo total</td><td>" + totalSec + "s</td></tr>";
    if (data.uploaded_at) html += "<tr><td>Subido</td><td>" + data.uploaded_at + "</td></tr>";
    if (data.error) html += "<tr><td>Error</td><td class='error'>" + data.error + "</td></tr>";
    html += "</table>";

    content.innerHTML = html;
    card.style.display = "block";

    document.getElementById("upload-btn").disabled = false;
}

function connectProgressWs(taskId) {
    if (!accessToken) {
        addLog("Error: no hay token de autenticacion");
        return;
    }
    disconnectWs();

    const wsUrl = WS_BASE + "/ws/" + taskId + "?token=" + encodeURIComponent(accessToken);
    console.log("Connecting WebSocket:", wsUrl);

    progressWs = new WebSocket(wsUrl);

    progressWs.onopen = function () {
        console.log("WebSocket connected for task:", taskId);
        addLog("Conectado al canal de progreso");
    };

    progressWs.onmessage = function (event) {
        try {
            const msg = JSON.parse(event.data);
            console.log("WS message:", msg.type, msg);

            if (msg.type === "starting") {
                showProgress("Preparando subida SFTP...", 0, 0, 0);
                addLog("Iniciando subida SFTP de " + (msg.size_display || formatBytes(msg.total_bytes)));
            } else if (msg.type === "progress") {
                showProgress(
                    "Subiendo a SFTP...",
                    msg.percentage || 0,
                    msg.speed_mbps || 0,
                    msg.eta_seconds || 0,
                );
                if (msg.percentage % 10 < 2) {
                    addLog(msg.percentage.toFixed(0) + "% - " + formatSpeed(msg.speed_mbps));
                }
            } else if (msg.type === "complete") {
                showProgress("Completado", 100, 0, 0);
                addLog("Subida completada exitosamente");
                setTimeout(function () { showResult(msg.result); }, 500);
            } else if (msg.type === "error") {
                document.getElementById("progress-bar").className = "progress-bar error";
                addLog("Error: " + msg.message);
                setTimeout(function () {
                    showResult({
                        success: false,
                        error: msg.message,
                        file_name: "",
                        extension: "",
                        size_bytes: 0,
                        size_display: "",
                        upload_path: "",
                        upload_time_seconds: msg.elapsed || 0,
                        tipo_archivo: "",
                        fecha: "",
                        id: "",
                    });
                }, 1000);
            }
        } catch (e) {
            console.error("WS parse error:", e);
        }
    };

    progressWs.onerror = function (err) {
        console.error("WebSocket error:", err);
        addLog("Error de conexion WebSocket");
    };

    progressWs.onclose = function () {
        console.log("WebSocket closed for task:", taskId);
        addLog("Canal de progreso cerrado");
    };
}

function uploadFile(event) {
    event.preventDefault();
    const tipoArchivo = document.getElementById("tipo_archivo").value;
    const fecha = document.getElementById("fecha").value;
    const fileInput = document.getElementById("file");
    const file = fileInput.files[0];
    const btn = document.getElementById("upload-btn");
    const resultCard = document.getElementById("result-card");

    if (!file || !tipoArchivo || !fecha) {
        alert("Complete todos los campos");
        return;
    }

    if (uploading) {
        addLog("Ya hay una subida en curso");
        return;
    }
    uploading = true;
    uploadStartTime = Date.now();
    btn.disabled = true;
    resultCard.style.display = "none";
    document.getElementById("result-content").innerHTML = "";
    document.getElementById("progress-log").innerHTML = "";

    showProgress("Enviando archivo al servidor...", 0, 0, 0);
    addLog("Archivo: " + file.name + " (" + formatBytes(file.size) + ")");
    addLog("Tipo: " + tipoArchivo + " | Fecha: " + fecha);

    const formData = new FormData();
    formData.append("tipo_archivo", tipoArchivo);
    formData.append("fecha", fecha);
    formData.append("file", file);

    const xhr = new XMLHttpRequest();

    xhr.upload.onprogress = function (e) {
        if (e.lengthComputable) {
            const pct = (e.loaded / e.total) * 100;
            showProgress("Enviando archivo al servidor...", pct, 0, 0);
        }
    };

    xhr.onload = function () {
        if (xhr.status >= 200 && xhr.status < 300) {
            const data = JSON.parse(xhr.responseText);
            fileInput.value = "";
            addLog("Archivo recibido. Task ID: " + data.task_id);
            showProgress("Archivo recibido, iniciando subida SFTP...", 100, 0, 0);
            connectProgressWs(data.task_id);
        } else {
            btn.disabled = false;
            try {
                const err = JSON.parse(xhr.responseText);
                showResult({
                    success: false,
                    error: err.detail || "Error del servidor",
                    file_name: file.name,
                    extension: "",
                    size_bytes: file.size,
                    size_display: formatBytes(file.size),
                    upload_path: "",
                    upload_time_seconds: 0,
                    tipo_archivo: tipoArchivo,
                    fecha: fecha,
                    id: "",
                });
            } catch (_) {
                showResult({
                    success: false,
                    error: "Error " + xhr.status + ": " + xhr.statusText,
                    file_name: file.name, extension: "", size_bytes: file.size,
                    size_display: formatBytes(file.size), upload_path: "",
                    upload_time_seconds: 0, tipo_archivo: tipoArchivo,
                    fecha: fecha, id: "",
                });
            }
        }
    };

    xhr.onerror = function () {
        btn.disabled = false;
        document.getElementById("progress-bar").className = "progress-bar error";
        addLog("Error de red al enviar archivo");
        setTimeout(function () {
            showResult({
                success: false,
                error: "Error de conexion: No se pudo enviar el archivo",
                file_name: file.name, extension: "", size_bytes: file.size,
                size_display: formatBytes(file.size), upload_path: "",
                upload_time_seconds: 0, tipo_archivo: tipoArchivo,
                fecha: fecha, id: "",
            });
        }, 500);
    };

    xhr.ontimeout = function () {
        btn.disabled = false;
        document.getElementById("progress-bar").className = "progress-bar error";
        addLog("La subida supero el tiempo maximo de espera");
        setTimeout(function () {
            showResult({
                success: false,
                error: "Timeout: La subida HTTP supero el tiempo maximo de espera",
                file_name: file.name, extension: "", size_bytes: file.size,
                size_display: formatBytes(file.size), upload_path: "",
                upload_time_seconds: 0, tipo_archivo: tipoArchivo,
                fecha: fecha, id: "",
            });
        }, 500);
    };

    xhr.open("POST", API_BASE + "/upload");
    xhr.setRequestHeader("Authorization", "Bearer " + accessToken);

    xhr.timeout = Math.min(Math.max(file.size / 1000, 300000), 7200000);
    xhr.send(formData);
}

navigate();
