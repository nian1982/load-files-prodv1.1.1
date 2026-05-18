import json
import sys
from dataclasses import asdict
from io import BytesIO
from datetime import datetime
from load_files.factories.di import create_upload_service
from load_files.utils.logger import logger

def main(comando: str, tipo_archivo: str | None = None, fecha: str | None = None, ruta: str | None = None):
    if comando != "upload":
        print("Uso: python -m load_files.cli upload <tipo_archivo> <YYYY-MM-DD> <ruta_archivo>", file=sys.stderr)
        sys.exit(1)

    if not tipo_archivo or not fecha or not ruta:
        print("Error: Se requieren 3 argumentos: tipo_archivo fecha ruta_archivo", file=sys.stderr)
        sys.exit(1)

    try:
        with open(ruta, "rb") as f:
            file_data = f.read()
    except FileNotFoundError:
        print(f"Error: Archivo no encontrado: {ruta}", file=sys.stderr)
        sys.exit(1)
    except IOError as e:
        print(f"Error al leer archivo: {e}", file=sys.stderr)
        sys.exit(1)

    file_name = ruta.split("/")[-1] if "/" in ruta else ruta

    service = create_upload_service()
    result = service.upload_file(file_name, BytesIO(file_data), tipo_archivo, fecha)
    output = asdict(result)
    output["uploaded_at"] = str(output["uploaded_at"]) if output["uploaded_at"] else None
    print(json.dumps(output, indent=2, default=str))

    if not result.success:
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python -m load_files.cli upload <tipo_archivo> <YYYY-MM-DD> <ruta_archivo>", file=sys.stderr)
        print("", file=sys.stderr)
        print("Ejemplos:", file=sys.stderr)
        print("  python -m load_files.cli upload REPOSITORIO 2026-05-17 ./reporte.xlsx", file=sys.stderr)
        print("  python -m load_files.cli upload FACTURAS 2026-05-17 /home/user/factura.pdf", file=sys.stderr)
        sys.exit(1)

    comando = sys.argv[1]
    tipo_archivo = sys.argv[2] if len(sys.argv) > 2 else None
    fecha = sys.argv[3] if len(sys.argv) > 3 else None
    ruta = sys.argv[4] if len(sys.argv) > 4 else None

    try:
        main(comando, tipo_archivo, fecha, ruta)
    except Exception as e:
        logger.error("Error: %s", e)
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
