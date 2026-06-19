from datetime import datetime


def build_upload_path(
    sftp_upload_dir: str,
    tipo_archivo: str,
    fecha: str,
    file_name: str,
) -> str:
    date_compressed = fecha.replace("-", "")
    hour = datetime.now().strftime("%H")
    remote_dir = (
        f"{sftp_upload_dir.rstrip('/')}"
        f"/{tipo_archivo}/{date_compressed}/{hour}"
    )
    return f"{remote_dir}/{file_name}"
