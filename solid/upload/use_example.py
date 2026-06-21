#!/usr/bin/env python3
"""
Ejemplo mínimo de uso del módulo solid/upload.

Uso básico:
    python solid/upload/use_example.py <archivo> <tipo> <YYYY-MM-DD>

Ejemplo:
    python solid/upload/use_example.py ./reporte.xlsx REPOSITORIO 2026-06-20

Con progreso:
    python solid/upload/use_example.py ./reporte.xlsx FACTURAS 2026-06-20 --progress

Requiere configurar SFTP_HOST, SFTP_USER, SFTP_PASS (o usar defaults).
"""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from solid.upload import upload_file


def main():
    if len(sys.argv) < 4:
        print(f"Uso: python {sys.argv[0]} <archivo> <tipo> <YYYY-MM-DD> [--progress]")
        print(f"Ej:  python {sys.argv[0]} ~/reporte.xlsx REPOSITORIO 2026-06-20")
        sys.exit(1)

    file_path = sys.argv[1]
    tipo = sys.argv[2].upper()
    fecha = sys.argv[3]
    show_progress = "--progress" in sys.argv

    progress_callback = None
    if show_progress:
        total = os.path.getsize(file_path)
        start = time.perf_counter()

        def progress(sent: int, _total: int) -> None:
            elapsed = time.perf_counter() - start
            pct = sent / total * 100
            speed = sent / elapsed / 1_000_000 if elapsed > 0 else 0
            bar = "█" * int(40 * sent / total) + "░" * (40 - int(40 * sent / total))
            print(f"\r  {bar} {pct:5.1f}%  {sent/1_000_000:.2f}MB  {speed:.2f}MB/s", end="")

        progress_callback = progress

    print(f"\nSubiendo: {file_path}")
    print(f"  Tipo: {tipo}  |  Fecha: {fecha}\n")

    from solid.upload import UploadResult
    result: UploadResult = upload_file(file_path, tipo, fecha, progress_callback=progress_callback)

    print()
    print(f"{'  ✓' if result.success else '  ✗'} {result.file_name}")
    print(f"  Ruta remota: {result.upload_path}")
    print(f"  Tamaño:      {result.size_display}")
    print(f"  Tiempo:      {result.upload_time_seconds}s")
    if result.error:
        print(f"  Error:       {result.error}")

    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
