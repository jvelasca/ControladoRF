"""Rutas locales de herramientas HackRF (PothosSDR portable o rf-tools de distribución)."""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Optional


def project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]


def bundled_rf_tools_bin_dir() -> Optional[Path]:
    """rf-tools\\bin junto al .exe en una distribución W11."""
    candidate = project_root() / "rf-tools" / "bin"
    if (candidate / "hackrf_info.exe").is_file() or (candidate / "hackrf_info").is_file():
        return candidate
    return None


def local_pothos_bin_dir() -> Optional[Path]:
    bundled = bundled_rf_tools_bin_dir()
    if bundled is not None:
        return bundled
    candidate = Path(__file__).resolve().parents[3] / "tools" / "PothosSDR" / "bin"
    if (candidate / "hackrf_info.exe").is_file() or (candidate / "hackrf_info").is_file():
        return candidate
    return None


def resolve_hackrf_bin_dir() -> Optional[Path]:
    for key in ("HACKRF_LIB_DIR", "POTHOS_SDR_BIN"):
        value = os.environ.get(key)
        if value:
            path = Path(value)
            if (path / "hackrf_info.exe").is_file() or (path / "hackrf_info").is_file():
                return path
    local = local_pothos_bin_dir()
    if local:
        return local
    which = shutil.which("hackrf_info")
    if which:
        return Path(which).parent
    return None


def resolve_hackrf_tool(name: str) -> Optional[Path]:
    bin_dir = resolve_hackrf_bin_dir()
    if not bin_dir:
        return None
    for suffix in (f"{name}.exe", name):
        candidate = bin_dir / suffix
        if candidate.is_file():
            return candidate
    return None


def ensure_hackrf_on_path() -> Optional[Path]:
    """Añade el directorio HackRF al PATH del proceso si existe."""
    bin_dir = resolve_hackrf_bin_dir()
    if not bin_dir:
        return None
    path = os.environ.get("PATH", "")
    bin_str = str(bin_dir)
    if bin_str not in path:
        os.environ["PATH"] = bin_str + os.pathsep + path
    os.environ.setdefault("HACKRF_LIB_DIR", bin_str)
    return bin_dir
