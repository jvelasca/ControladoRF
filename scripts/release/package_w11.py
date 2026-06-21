"""Ensamblado del paquete ZIP de distribución Windows 11."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from scripts.release.common import APP_BASENAME, STAGING_ROOT, PyInstallerResult, package_folder_name, timestamp
from scripts.release.rf_tools import stage_rf_tools, verify_rf_tools

PACKAGING_DIR = Path(__file__).resolve().parents[2] / "packaging" / "w11"
INSTALLER_SCRIPT = PACKAGING_DIR / "instalar_rf.ps1"


def staging_dir(version: str) -> Path:
    return STAGING_ROOT / package_folder_name(version)


def write_leeme(target: Path, *, version: str, copied_tools: list[str]) -> None:
    target.write_text(
        "\n".join(
            [
                f"CONTROLADORF {version} — Distribución Windows 11",
                "=" * 52,
                "",
                "CONTENIDO",
                "---------",
                f"  {APP_BASENAME}.exe           Aplicación",
                "  _internal\\                   Librerías PyQt6 / Python",
                "  rf-tools\\bin\\                 Utilidades HackRF (libhackrf + CLI)",
                "  instalar_rf.ps1                 Comprueba RF y configura PATH local",
                "  LEEME.txt                       Este archivo",
                "  manifest.json                   Metadatos de la build",
                "",
                "INSTALACIÓN RÁPIDA",
                "-----------------",
                "1. Descomprima todo en una carpeta (p. ej. C:\\ControladoRF).",
                "2. Conecte el HackRF One por USB.",
                "3. Si es la primera vez en este PC, instale el driver USB con Zadig:",
                "     https://zadig.akeo.ie/",
                "   - Options → List All Devices",
                "   - Seleccione «HackRF One» (USB 1d50:6089)",
                "   - Driver: WinUSB → Replace Driver",
                "   (Solo una vez por equipo.)",
                "4. Ejecute instalar_rf.ps1 (clic derecho → Ejecutar con PowerShell).",
                "5. Inicie ControladoRF.exe",
                "",
                "DATOS DE USUARIO",
                "----------------",
                "Proyectos (.crf), workspaces y logs se guardan en:",
                "  Documentos\\ControladoRF\\",
                "",
                "MONITOR / SDR",
                "-------------",
                "La app detecta automáticamente rf-tools\\bin junto al ejecutable.",
                f"Herramientas incluidas ({len(copied_tools)} ficheros):",
                *[f"  - {name}" for name in copied_tools[:12]],
                *(["  - …"] if len(copied_tools) > 12 else []),
                "",
                "SOPORTE",
                "-------",
                "Documentación del proyecto: docs\\monitor_sdr_setup.md",
                "",
            ]
        ),
        encoding="utf-8",
    )


def write_manifest(target: Path, *, version: str, copied_tools: list[str], exe_name: str) -> None:
    payload = {
        "app": APP_BASENAME,
        "version": version,
        "platform": "windows-11",
        "built_at": timestamp(),
        "executable": exe_name,
        "rf_tools_count": len(copied_tools),
        "rf_tools_files": copied_tools,
    }
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def assemble_package(
    *,
    version: str,
    build: "PyInstallerResult",
    include_rf_tools: bool = True,
    verify_tools: bool = True,
) -> Path:
    folder = staging_dir(version)
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True, exist_ok=True)

    for item in build.bundle_dir.iterdir():
        target = folder / item.name
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)

    copied_tools: list[str] = []
    if include_rf_tools:
        copied = stage_rf_tools(folder / "rf-tools" / "bin")
        copied_tools = copied
        if verify_tools:
            ok, detail = verify_rf_tools(folder / "rf-tools" / "bin")
            if not ok:
                print(f"AVISO: hackrf_info no pasó verificación USB: {detail}")
                print("       (Normal si no hay HackRF conectado durante la build.)")

    if INSTALLER_SCRIPT.is_file():
        shutil.copy2(INSTALLER_SCRIPT, folder / "instalar_rf.ps1")
    else:
        raise FileNotFoundError(f"No se encontró {INSTALLER_SCRIPT}")

    write_leeme(folder / "LEEME.txt", version=version, copied_tools=copied_tools)
    write_manifest(
        folder / "manifest.json",
        version=version,
        copied_tools=copied_tools,
        exe_name=build.exe_path.name,
    )
    (folder / "VERSION.txt").write_text(version + "\n", encoding="utf-8")
    return folder


def create_zip(folder: Path, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    zip_base = output_dir / folder.name
    if zip_base.with_suffix(".zip").is_file():
        zip_base.with_suffix(".zip").unlink()
    archive = shutil.make_archive(str(zip_base), "zip", root_dir=str(folder.parent), base_dir=folder.name)
    return Path(archive)
