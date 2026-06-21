"""Backend DAB+ audio vía welle.io (welle-cli) — decodificación externa."""
from __future__ import annotations

import shlex
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from core.monitor.dab_ofdm import nearest_dab_block_center_hz

# welle.io — receptor DAB/DAB+ open source (usa dablin internamente).
# https://github.com/AlbrechtL/welle.io
# welle-cli: interfaz de línea de comandos, soporta SoapySDR/HackRF.
WELLE_PROJECT_URL = "https://github.com/AlbrechtL/welle.io"
WELLE_DOCS_URL = "https://www.welle.io"
DABLIN_PROJECT_URL = "https://github.com/Opendigitalradio/dablin"


@dataclass(frozen=True)
class WelleCliProbe:
    available: bool
    executable: str | None
    message_key: str


_PROBE_CACHE: WelleCliProbe | None = None
_PROBE_CACHE_AT: float = 0.0
_PROBE_CACHE_TTL_SEC = 30.0


def invalidate_welle_cli_probe_cache() -> None:
    global _PROBE_CACHE, _PROBE_CACHE_AT
    _PROBE_CACHE = None
    _PROBE_CACHE_AT = 0.0


def _candidate_paths() -> list[str]:
    names = ("welle-cli", "welle-cli.exe")
    paths: list[str] = []
    for name in names:
        found = shutil.which(name)
        if found:
            paths.append(found)
    tools = Path(__file__).resolve().parents[3] / "tools"
    for name in names:
        p = tools / name
        if p.is_file():
            paths.append(str(p))
    return paths


def probe_welle_cli(*, force: bool = False) -> WelleCliProbe:
    """Comprueba si welle-cli está instalado (decodificador DAB+ recomendado)."""
    global _PROBE_CACHE, _PROBE_CACHE_AT
    now = time.monotonic()
    if (
        not force
        and _PROBE_CACHE is not None
        and now - _PROBE_CACHE_AT < _PROBE_CACHE_TTL_SEC
    ):
        return _PROBE_CACHE
    paths = _candidate_paths()
    if not paths:
        result = WelleCliProbe(available=False, executable=None, message_key="monitor_dab_welle_missing")
        _PROBE_CACHE = result
        _PROBE_CACHE_AT = now
        return result
    exe = paths[0]
    try:
        proc = subprocess.run(
            [exe, "-h"],
            capture_output=True,
            text=True,
            timeout=4.0,
            check=False,
        )
        if proc.returncode not in (0, 1) and "welle" not in (proc.stdout + proc.stderr).lower():
            result = WelleCliProbe(available=False, executable=exe, message_key="monitor_dab_welle_missing")
            _PROBE_CACHE = result
            _PROBE_CACHE_AT = now
            return result
    except (OSError, subprocess.TimeoutExpired):
        result = WelleCliProbe(available=False, executable=exe, message_key="monitor_dab_welle_missing")
        _PROBE_CACHE = result
        _PROBE_CACHE_AT = now
        return result
    result = WelleCliProbe(available=True, executable=exe, message_key="monitor_dab_welle_ok")
    _PROBE_CACHE = result
    _PROBE_CACHE_AT = now
    return result


@dataclass(frozen=True)
class WelleLaunchResult:
    ok: bool
    message_key: str
    channel: str = ""
    web_url: str = ""
    command: str = ""


def welle_dab_channel_label(freq_hz: float) -> str:
    """Etiqueta welle-cli -c (5A…13F) para la frecuencia dada."""
    _center_hz, block_index = nearest_dab_block_center_hz(freq_hz)
    return _block_index_to_welle_label(block_index)


def format_welle_cli_command(
    freq_hz: float,
    *,
    executable: str | None = None,
    web_port: int = 7970,
) -> str:
    probe = probe_welle_cli()
    exe = executable or probe.executable
    if not exe:
        return ""
    cmd = build_welle_cli_command(
        executable=exe,
        freq_hz=freq_hz,
        web_port=web_port,
    )
    if sys.platform == "win32":
        return subprocess.list2cmdline(cmd)
    return " ".join(shlex.quote(part) for part in cmd)


def launch_welle_cli(
    freq_hz: float,
    *,
    web_port: int = 7970,
) -> WelleLaunchResult:
    """Lanza welle-cli en consola nueva (requiere HackRF libre)."""
    probe = probe_welle_cli()
    if not probe.available or not probe.executable:
        return WelleLaunchResult(ok=False, message_key="monitor_dab_welle_missing")
    channel = welle_dab_channel_label(freq_hz)
    cmd = build_welle_cli_command(
        executable=probe.executable,
        freq_hz=freq_hz,
        web_port=web_port,
    )
    command_txt = format_welle_cli_command(freq_hz, executable=probe.executable, web_port=web_port)
    web_url = f"http://localhost:{int(web_port)}/"
    try:
        if sys.platform == "win32":
            subprocess.Popen(
                cmd,
                creationflags=subprocess.CREATE_NEW_CONSOLE,
                close_fds=False,
            )
        else:
            subprocess.Popen(
                cmd,
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    except OSError:
        return WelleLaunchResult(
            ok=False,
            message_key="monitor_dab_welle_launch_failed",
            channel=channel,
            command=command_txt,
        )
    return WelleLaunchResult(
        ok=True,
        message_key="monitor_dab_welle_launched",
        channel=channel,
        web_url=web_url,
        command=command_txt,
    )

def welle_channel_hint(freq_hz: float) -> str:
    """Sugerencia de canal para welle-cli -c (centro de bloque Band III)."""
    center_hz, block_index = nearest_dab_block_center_hz(freq_hz)
    mhz = center_hz / 1e6
    label = _block_index_to_welle_label(block_index)
    return f"{label} · {mhz:.3f} MHz"


def build_welle_cli_command(
    *,
    executable: str,
    freq_hz: float,
    programme: str = "",
    web_port: int | None = 7970,
    use_soapy_hackrf: bool = True,
) -> list[str]:
    """
    Comando welle-cli para decodificar DAB+ (requiere SDR exclusivo).

    Ejemplo manual:
      welle-cli -F soapysdr,driver=hackrf -c 11C -w 7970
    Nota: no puede compartir HackRF con ControladoRF en captura simultánea.
    """
    _center_hz, block_index = nearest_dab_block_center_hz(freq_hz)
    channel = _block_index_to_welle_label(block_index)
    cmd = [executable]
    if use_soapy_hackrf:
        cmd.extend(["-F", "soapysdr,driver=hackrf"])
    cmd.extend(["-c", channel])
    if programme:
        cmd.extend(["-p", programme])
    if web_port is not None:
        cmd.extend(["-w", str(int(web_port))])
    return cmd


def _block_index_to_welle_label(block_index: int) -> str:
    """Aproxima etiqueta welle (5A…13F) desde índice de bloque Band III."""
    labels = (
        "5A", "5B", "5C", "5D", "6A", "6B", "6C", "6D",
        "7A", "7B", "7C", "7D", "8A", "8B", "8C", "8D",
        "9A", "9B", "9C", "9D", "10A", "10B", "10C", "10D",
        "11A", "11B", "11C", "11D", "12A", "12B", "12C", "12D",
        "13A", "13B", "13C", "13D", "13E", "13F",
    )
    idx = max(0, min(len(labels) - 1, int(block_index)))
    return labels[idx]
