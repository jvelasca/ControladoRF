#!/usr/bin/env python3
"""
Genera solo el ejecutable one-file de CONTROLADORF (sin paquete rf-tools).

Para la distribución completa Windows 11 use:
  python scripts/build_distribucion_w11.py

Salida por defecto:
  %USERPROFILE%\\Documents\\distribuciones python\\ControladoRF-<version>.exe
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.release.common import (  # noqa: E402
    APP_BASENAME,
    DEFAULT_OUTPUT_DIR,
    ensure_icon,
    ensure_pyinstaller,
    read_version,
    run_pyinstaller,
    timestamp,
)


def _write_release_notes(output_dir: Path, exe_path: Path, version: str) -> Path:
    notes_path = output_dir / f"{APP_BASENAME}-{version}-README.txt"
    notes_path.write_text(
        "\n".join(
            [
                f"CONTROLADORF {version}",
                f"Generado: {timestamp()}",
                "",
                f"Ejecutable: {exe_path.name}",
                "",
                "Para distribución completa (rf-tools + ZIP W11):",
                "  python scripts\\build_distribucion_w11.py",
                "",
                "Datos de usuario:",
                f"  {Path.home() / 'Documents' / 'ControladoRF'}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return notes_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Empaqueta CONTROLADORF en un solo .exe")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Carpeta de salida (por defecto: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="No borrar caché de PyInstaller antes de compilar",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    version = read_version()
    output_dir = args.output_dir.expanduser().resolve()

    print(f"Proyecto: {ROOT}")
    print(f"Versión:  {version}")
    print(f"Salida:   {output_dir}")

    ensure_pyinstaller()
    icon_path = ensure_icon()
    print(f"Icono:    {icon_path}")

    build = run_pyinstaller(
        icon_path=icon_path,
        output_dir=output_dir,
        version=version,
        clean=not args.no_clean,
        exe_basename=f"{APP_BASENAME}-{version}",
        onefile=True,
    )
    notes_path = _write_release_notes(output_dir, build.exe_path, version)

    size_mb = build.exe_path.stat().st_size / (1024 * 1024)
    print("")
    print("Compilación completada.")
    print(f"  Ejecutable: {build.exe_path}")
    print(f"  Tamaño:     {size_mb:.1f} MB")
    print(f"  Notas:      {notes_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
