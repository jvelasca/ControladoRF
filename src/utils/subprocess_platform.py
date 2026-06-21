"""Subprocess sin ventana de consola en Windows (distribución empaquetada)."""
from __future__ import annotations

import subprocess
import sys
from typing import Any


def no_window_kwargs() -> dict[str, Any]:
    if sys.platform != "win32":
        return {}
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    return {"creationflags": flags, "startupinfo": startupinfo}


def run_hidden(*popenargs, **kwargs):
    merged = no_window_kwargs()
    merged.update(kwargs)
    return subprocess.run(*popenargs, **merged)


def popen_hidden(*popenargs, **kwargs):
    merged = no_window_kwargs()
    merged.update(kwargs)
    return subprocess.Popen(*popenargs, **merged)
