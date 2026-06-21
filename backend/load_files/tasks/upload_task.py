import json
import os
import time
from collections import deque
from datetime import datetime
from uuid import uuid4

import redis

from load_files.celery_app import celery_app
from load_files.config.settings import settings
from load_files.utils.logger import logger
from solid.sftp.config import SFTPSettings
from solid.sftp.exceptions import SFTPError
from solid.sftp.paramiko_client import ParamikoSFTPClient
from solid.ws.config import WSSettings
from solid.ws.redis_publisher import RedisProgressPublisher

_REDIS_CLIENT = redis.Redis.from_url(settings.REDIS_URL)


def _publish(channel: str, data: dict) -> None:
    payload = json.dumps(data, default=str)
    _REDIS_CLIENT.publish(channel, payload)
    task_id = data.get("task_id", "")
    if task_id:
        _REDIS_CLIENT.set(f"upload:{task_id}:state", payload, ex=3600)


def _format_size(bytes_: int) -> str:
    size = float(bytes_)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} TB"


def _safe_error(msg: str) -> str:
    if settings.ENVIRONMENT.lower() == "production":
        return "An internal error occurred during upload. Contact the administrator."
    return msg


@celery_app.task(bind=True, max_retries=0)
def upload_to_sftp(
    self,
    task_id: str,
    file_path: str,
    file_name: str,
    tipo_archivo: str,
    fecha: str,
    username: str,
) -> dict:
    channel = f"upload:{task_id}"
    start_time = time.perf_counter()
    total_bytes = os.path.getsize(file_path)

    sftp_settings = SFTPSettings(
        host=settings.SFTP_HOST,
        port=settings.SFTP_PORT,
        user=settings.SFTP_USER,
        password=settings.SFTP_PASS,
        upload_dir=settings.SFTP_UPLOAD_DIR,
        chunk_size=settings.SFTP_CHUNK_SIZE,
    )
    sftp = ParamikoSFTPClient(sftp_settings)

    extension = (
        file_name[file_name.rfind("."):].lower()
        if "." in file_name else ""
    )

    _publish(channel, {
        "type": "starting",
        "task_id": task_id,
        "file_name": file_name,
        "total_bytes": total_bytes,
        "size_display": _format_size(total_bytes),
        "username": username,
        "timestamp": datetime.now().isoformat(),
    })

    try:
        remote_dir = (
            f"{settings.SFTP_UPLOAD_DIR.rstrip('/')}"
            f"/{tipo_archivo}/{fecha.replace('-', '')}/{datetime.now().strftime('%H')}"
        )
        remote_path = f"{remote_dir}/{file_name}"

        logger.info(
            "Worker starting upload: task=%s file=%s size=%s",
            task_id, file_name, _format_size(total_bytes),
        )

        sftp.connect()
        sftp.ensure_directory(remote_dir)

        speed_samples = deque(maxlen=5)

        def progress_callback(bytes_sent: int, _total: int) -> None:
            elapsed = time.perf_counter() - start_time
            speed = bytes_sent / elapsed if elapsed > 0 else 0
            speed_samples.append(speed)
            avg_speed = sum(speed_samples) / len(speed_samples)
            percentage = (
                round(bytes_sent / total_bytes * 100, 1)
                if total_bytes > 0 else 0
            )
            eta = (
                (total_bytes - bytes_sent) / avg_speed
                if avg_speed > 0 else 0
            )
            _publish(channel, {
                "type": "progress",
                "task_id": task_id,
                "percentage": percentage,
                "bytes_sent": bytes_sent,
                "total_bytes": total_bytes,
                "speed_mbps": round(avg_speed / 1000 / 1000 * 8, 2),
                "eta_seconds": round(eta),
                "elapsed": round(elapsed, 1),
            })

        with open(file_path, "rb") as file_obj:
            bytes_sent = sftp.upload_file_stream(
                remote_path, file_obj,
                progress_callback=progress_callback,
                total_bytes=total_bytes,
            )

        elapsed = time.perf_counter() - start_time
        logger.info(
            "Worker upload complete: task=%s (%d bytes) in %.2fs",
            task_id, bytes_sent, elapsed,
        )

        result = {
            "success": True,
            "id": str(uuid4()),
            "file_name": file_name,
            "extension": extension,
            "size_bytes": bytes_sent,
            "size_display": _format_size(bytes_sent),
            "upload_path": remote_path,
            "upload_time_seconds": round(elapsed, 2),
            "tipo_archivo": tipo_archivo,
            "fecha": fecha,
            "uploaded_at": datetime.now().isoformat(),
        }

        _publish(channel, {"type": "complete", "task_id": task_id, "result": result})
        return result

    except SFTPError as e:
        elapsed = time.perf_counter() - start_time
        msg = f"{e.__class__.__name__}: {e.message}"
        logger.error("Worker upload failed (sftp): task=%s error=%s", task_id, msg)
        _publish(channel, {
            "type": "error", "task_id": task_id,
            "message": _safe_error(msg), "elapsed": round(elapsed, 2),
        })
        return {"success": False, "error": _safe_error(msg)}

    except Exception as e:
        elapsed = time.perf_counter() - start_time
        msg = str(e)
        logger.error("Worker upload failed: task=%s error=%s", task_id, msg)
        _publish(channel, {
            "type": "error", "task_id": task_id,
            "message": _safe_error(msg), "elapsed": round(elapsed, 2),
        })
        return {"success": False, "error": _safe_error(msg)}

    finally:
        sftp.disconnect()
        _cleanup(file_path)


def _cleanup(file_path: str) -> None:
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            parent = os.path.dirname(file_path)
            if os.path.isdir(parent) and not os.listdir(parent):
                os.rmdir(parent)
    except OSError as e:
        logger.warning("Worker cleanup failed for %s: %s", file_path, e)
