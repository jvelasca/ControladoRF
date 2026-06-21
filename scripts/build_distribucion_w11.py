#!/usr/bin/env python3
"""
Genera la distribución Windows 11 de CONTROLADORF (ZIP + carpeta).

Incluye:
  - ControladoRF-<version>.exe
  - rf-tools\\bin\\ (libhackrf + hackrf_info / hackrf_sweep / hackrf_transfer)
  - instalar_rf.ps1
  - LEEME.txt, manifest.json, VERSION.txt

Salida por defecto:
  %USERPROFILE%\\Documents\\distribuciones python\\
    ControladoRF-<version>-w11\\     (carpeta descomprimible)
    ControladoRF-<version>-w11.zip

Antes de compilar, actualice la versión en src\\VERSION.

Uso:
  python scripts\\build_distribucion_w11.py
  python scripts\\build_distribucion_w11.py --skip-rf-tools
  python scripts\\build_distribucion_w11.py --no-zip
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
    STAGING_ROOT,
    ensure_icon,
    ensure_pyinstaller,
    package_folder_name,
    read_version,
    run_pyinstaller,
)
from scripts.release.inno_setup import build_installer  # noqa: E402
from scripts.release.package_w11 import assemble_package, create_zip, staging_dir  # noqa: E402
from scripts.release.rf_tools import ensure_pothos_installed  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Empaqueta CONTROLADORF para Windows 11 (exe + rf-tools + ZIP)"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Carpeta de salida (por defecto: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--skip-rf-tools",
        action="store_true",
        help="No copiar rf-tools (solo exe + scripts; útil para pruebas)",
    )
    parser.add_argument(
        "--skip-pothos-install",
        action="store_true",
        help="No ejecutar install_hackrf_windows.ps1 si faltan herramientas",
    )
    parser.add_argument(
        "--no-zip",
        action="store_true",
        help="Generar solo la carpeta, sin ZIP",
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="No borrar caché de PyInstaller antes de compilar",
    )
    parser.add_argument(
        "--installer",
        action="store_true",
        help="Generar también ControladoRF-<version>-w11-Setup.exe (Inno Setup)",
    )
    parser.add_argument(
        "--skip-installer",
        action="store_true",
        help="No generar Setup.exe aunque Inno Setup esté instalado",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    version = read_version()
    output_dir = args.output_dir.expanduser().resolve()
    folder_name = package_folder_name(version)

    print(f"Proyecto:  {ROOT}")
    print(f"Versión:   {version}")
    print(f"Paquete:   {folder_name}")
    print(f"Salida:    {output_dir}")

    if not args.skip_rf_tools and not args.skip_pothos_install:
        ensure_pothos_installed(allow_install=True)
    elif not args.skip_rf_tools:
        ensure_pothos_installed(allow_install=False)

    ensure_pyinstaller()
    icon_path = ensure_icon()
    print(f"Icono:     {icon_path}")

    build_dir = STAGING_ROOT / "_pyinstaller"
    build_dir.mkdir(parents=True, exist_ok=True)
    build = run_pyinstaller(
        icon_path=icon_path,
        output_dir=build_dir,
        version=version,
        clean=not args.no_clean,
        onefile=False,
    )

    package_path = assemble_package(
        version=version,
        build=build,
        include_rf_tools=not args.skip_rf_tools,
        verify_tools=True,
    )

    zip_path = None
    if not args.no_zip:
        zip_path = create_zip(package_path, output_dir)
        print(f"ZIP:       {zip_path} ({zip_path.stat().st_size / (1024 * 1024):.1f} MB)")

    # Copia la carpeta al destino final (junto al ZIP)
    final_folder = output_dir / folder_name
    if final_folder.exists():
        import shutil

        shutil.rmtree(final_folder)
    import shutil

    shutil.copytree(package_path, final_folder)

    exe_size = (final_folder / build.exe_path.name).stat().st_size / (1024 * 1024)

    setup_path = None
    if args.installer:
        try:
            setup_path = build_installer(
                package_dir=final_folder,
                output_dir=output_dir,
                version=version,
            )
        except RuntimeError as exc:
            print(f"ERROR: {exc}")
            return 1

    print("")
    print("Distribución W11 completada.")
    print(f"  Carpeta: {final_folder}")
    if zip_path:
        print(f"  ZIP:     {zip_path}")
    if setup_path:
        print(f"  Setup:   {setup_path}")
    print(f"  Exe:     {build.exe_path.name} ({exe_size:.1f} MB)")
    print("")
    if setup_path:
        print("Distribuya el Setup.exe para usuarios finales; el ZIP queda como respaldo.")
    else:
        print("Próximo paso: instale Inno Setup y vuelva a compilar con --installer.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
