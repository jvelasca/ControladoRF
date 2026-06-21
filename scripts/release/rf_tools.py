"""Copia y verificación de herramientas HackRF para distribución W11."""
from __future__ import annotations

import fnmatch
import shutil
import subprocess
import sys
from pathlib import Path

from scripts.release.common import ROOT


def _run_hidden(cmd: list[str], **kwargs):
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        kwargs.setdefault("creationflags", subprocess.CREATE_NO_WINDOW)
        kwargs.setdefault("startupinfo", startupinfo)
    return subprocess.run(cmd, **kwargs)

POTHOS_BIN = ROOT / "tools" / "PothosSDR" / "bin"
INSTALL_SCRIPT = ROOT / "scripts" / "install_hackrf_windows.ps1"

# Ficheros mínimos + dependencias habituales en PothosSDR (Windows x64).
RF_TOOL_PATTERNS = (
    "hackrf*",
    "libhackrf*",
    "libusb*",
    "pthread*",
    "cygusb*",
    "usb-1.0*",
    "fftw*",
    "libfftw*",
    "libwinpthread*",
    "msvc*.dll",
    "vcruntime*.dll",
    "concrt*.dll",
)


def pothos_bin_ready() -> bool:
    return (POTHOS_BIN / "hackrf_info.exe").is_file()


def ensure_pothos_installed(*, allow_install: bool = True) -> None:
    if pothos_bin_ready():
        return
    if not allow_install:
        raise RuntimeError(
            "No hay herramientas HackRF en tools\\PothosSDR\\bin.\n"
            "Ejecute: powershell -ExecutionPolicy Bypass -File scripts\\install_hackrf_windows.ps1"
        )
    if not INSTALL_SCRIPT.is_file():
        raise RuntimeError(f"No se encontró {INSTALL_SCRIPT}")
    print("Instalando PothosSDR / libhackrf (primera vez o instalación incompleta)…")
    subprocess.check_call(
        [
            "powershell",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(INSTALL_SCRIPT),
        ],
        cwd=str(ROOT),
    )
    if not pothos_bin_ready():
        raise RuntimeError(
            "Tras install_hackrf_windows.ps1 sigue sin existir hackrf_info.exe en "
            f"{POTHOS_BIN}"
        )


def _matches_any_pattern(name: str) -> bool:
    lower = name.lower()
    return any(fnmatch.fnmatch(lower, pattern.lower()) for pattern in RF_TOOL_PATTERNS)


def stage_rf_tools(dest_bin: Path, *, source_bin: Path | None = None) -> list[str]:
    """Copia utilidades HackRF a dest_bin. Devuelve lista de ficheros copiados."""
    source = source_bin or POTHOS_BIN
    if not (source / "hackrf_info.exe").is_file():
        raise RuntimeError(f"hackrf_info.exe no encontrado en {source}")

    if dest_bin.exists():
        shutil.rmtree(dest_bin)
    dest_bin.mkdir(parents=True, exist_ok=True)

    copied: list[str] = []
    for item in sorted(source.iterdir()):
        if not item.is_file():
            continue
        if not _matches_any_pattern(item.name):
            continue
        target = dest_bin / item.name
        shutil.copy2(item, target)
        copied.append(item.name)

    required = ("hackrf_info.exe", "hackrf_sweep.exe", "hackrf_transfer.exe")
    missing = [name for name in required if not (dest_bin / name).is_file()]
    if missing:
        raise RuntimeError(
            "Copia incompleta de rf-tools; faltan: "
            + ", ".join(missing)
            + f"\nRevise {source} o amplíe RF_TOOL_PATTERNS en rf_tools.py"
        )
    return copied


def verify_rf_tools(bin_dir: Path) -> tuple[bool, str]:
    info = bin_dir / "hackrf_info.exe"
    if not info.is_file():
        return False, "hackrf_info.exe no encontrado"
    try:
        proc = _run_hidden(
            [str(info)],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except OSError as exc:
        return False, str(exc)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        return False, detail or f"hackrf_info terminó con código {proc.returncode}"
    return True, (proc.stdout or "").strip().splitlines()[0] if proc.stdout else "OK"
