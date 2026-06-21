#!/usr/bin/env python
"""Analiza una sesión de prueba Monitor: logs, HackRF, demod y audio.

Uso tras probar en la app:
  1. PLAY, sintoniza FM, pulsa FM Broad, escucha 30–60 s, STOP.
  2. Ejecuta:
       .\\env\\Scripts\\python.exe scripts\\monitor_diagnose_session.py
     o solo las últimas líneas del log:
       .\\env\\Scripts\\python.exe scripts\\monitor_diagnose_session.py --tail 400

Genera: logs/monitor_diagnose_report.txt
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
LOG_DIR = ROOT / "logs"
sys.path.insert(0, str(SRC))

FLOW_LOG = LOG_DIR / "monitor_flow.log"
REPORT_PATH = LOG_DIR / "monitor_diagnose_report.txt"

_KEY_PATTERNS = {
    "reconfigure": re.compile(r"reconfigure_", re.I),
    "stream_restart": re.compile(r"stream_restart", re.I),
    "frame_gap": re.compile(r"frame_gap", re.I),
    "capture_error": re.compile(r"capture_error", re.I),
    "apply_params": re.compile(r"apply_params", re.I),
    "iq_peak": re.compile(r"iq_peak", re.I),
    "diag_marker": re.compile(r"DIAG_MARKER", re.I),
}


def _read_tail(path: Path, max_lines: int) -> list[str]:
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    return lines[-max_lines:] if max_lines > 0 else lines


def _analyze_flow_lines(lines: list[str]) -> dict:
    counts: Counter[str] = Counter()
    warnings: list[str] = []
    markers: list[str] = []
    hw_changes: list[str] = []
    last_peaks: list[str] = []

    for line in lines:
        for name, pat in _KEY_PATTERNS.items():
            if pat.search(line):
                counts[name] += 1
        if "WARNING" in line or "ERROR" in line:
            if "frame_gap" in line or "stream_restart" in line or "capture_error" in line:
                warnings.append(line.strip())
        if "DIAG_MARKER" in line:
            markers.append(line.strip())
        if "apply_params" in line and "HW[" in line:
            hw_changes.append(line.strip())
        if "iq_peak" in line:
            last_peaks.append(line.strip())

    return {
        "counts": dict(counts),
        "warnings": warnings[-20:],
        "markers": markers[-10:],
        "hw_changes": hw_changes[-15:],
        "last_peaks": last_peaks[-8:],
    }


def _probe_hackrf() -> list[str]:
    rows: list[str] = []
    try:
        from core.monitor.hackrf_lib import libhackrf_available, resolve_hackrf_dll

        dll = resolve_hackrf_dll()
        rows.append(f"libhackrf: available={libhackrf_available()} path={dll or '—'}")
    except Exception as exc:
        rows.append(f"libhackrf probe failed: {exc}")

    try:
        from core.monitor.device_discovery import discover_sources

        sources = discover_sources(probe_backend=False)
        ids = [s.source_id for s in sources]
        rows.append(f"discovered sources: {', '.join(ids) if ids else '(ninguno)'}")
    except Exception as exc:
        rows.append(f"device_discovery failed: {exc}")

    return rows


def _probe_demod(*, fc_hz: float, duration_sec: float) -> list[str]:
    rows: list[str] = []
    try:
        import numpy as np

        from core.monitor.demod_branch import DemodBranch
        from core.monitor.demod_dsp import AUDIO_RATE_HZ
        from core.monitor.iq_constants import IQ_DEMOD_CHUNK_SAMPLES
        from core.monitor.spectrum_params import SpectrumParams
        from core.monitor.wfm_broadcast_profile import apply_fm_broadcast_preset

        rate = 2_000_000.0
        params = apply_fm_broadcast_preset(
            SpectrumParams(
                center_freq_hz=fc_hz,
                vfo_freq_hz=fc_hz,
                selected_freq_hz=fc_hz,
                freq_readout="f",
            )
        )
        branch = DemodBranch()
        pcm_total = 0
        level_dbfs: list[float] = []
        t0 = time.perf_counter()
        idx0 = 0
        while time.perf_counter() - t0 < duration_sec:
            n = IQ_DEMOD_CHUNK_SAMPLES
            idx = np.arange(idx0, idx0 + n, dtype=np.float64)
            t = idx / rate
            offset = 25_000.0
            mod = 0.4 * np.sin(2.0 * np.pi * 1_000.0 * t)
            iq = (0.5 * np.exp(1j * (2.0 * np.pi * offset * t + mod))).astype(np.complex64)
            idx0 += n
            branch.process_iq(iq, params, sample_rate_hz=rate)
            st = branch.last_state
            if st is not None and st.pcm.size:
                pcm_total += st.pcm.size
                level_dbfs.append(st.level_dbfs)

        elapsed = max(time.perf_counter() - t0, 1e-6)
        pcm_rate = pcm_total / elapsed
        rows.append(
            f"demod_sim: pcm_rate={pcm_rate:.0f} target={AUDIO_RATE_HZ:.0f} "
            f"ratio={pcm_rate / AUDIO_RATE_HZ:.3f}"
        )
        if level_dbfs:
            rows.append(
                f"demod_sim: level_dbfs min={min(level_dbfs):.1f} max={max(level_dbfs):.1f} "
                f"last={level_dbfs[-1]:.1f} stereo={getattr(st, 'stereo', False)}"
            )
        if pcm_rate < AUDIO_RATE_HZ * 0.85:
            rows.append("demod_sim: WARN baja tasa PCM — posible cuello en cadena demod")
    except Exception as exc:
        rows.append(f"demod_sim failed: {exc}")
    return rows


def _probe_audio_output() -> list[str]:
    rows: list[str] = []
    try:
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        from gui.monitor.demod_audio_output import DemodAudioOutput

        out = DemodAudioOutput()
        ok = out.start(stereo=True)
        rows.append(f"QAudioSink stereo: ok={ok} error={out.last_error or '—'}")
        out.stop()
        ok2 = out.start(stereo=False)
        rows.append(f"QAudioSink mono: ok={ok2} error={out.last_error or '—'}")
        out.stop()
    except Exception as exc:
        rows.append(f"audio_output probe failed: {exc}")
    return rows


def _write_report(sections: list[tuple[str, list[str]]]) -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        f"Monitor diagnose report — {datetime.now().isoformat(timespec='seconds')}",
        f"flow_log: {FLOW_LOG}",
        "",
    ]
    for title, body in sections:
        lines.append(f"=== {title} ===")
        if body:
            lines.extend(body)
        else:
            lines.append("(sin datos)")
        lines.append("")
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    return REPORT_PATH


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnóstico post-prueba Monitor FM/IQ")
    parser.add_argument("--tail", type=int, default=600, help="Líneas finales de monitor_flow.log")
    parser.add_argument("--fc-mhz", type=float, default=105.2, help="MHz para simulación demod offline")
    parser.add_argument("--demod-sec", type=float, default=3.0, help="Segundos simulación demod")
    parser.add_argument("--no-hardware", action="store_true", help="Omitir pruebas HackRF/audio Qt")
    args = parser.parse_args()

    flow_lines = _read_tail(FLOW_LOG, args.tail)
    flow = _analyze_flow_lines(flow_lines)

    sections: list[tuple[str, list[str]]] = []

    summary = [
        f"Líneas analizadas: {len(flow_lines)}",
        f"Eventos: {flow['counts'] or '(ninguno)'}",
    ]
    if flow["markers"]:
        summary.append("Marcadores DIAG (FM Broad, etc.):")
        summary.extend(f"  {m}" for m in flow["markers"])
    sections.append(("Resumen log", summary))

    if flow["warnings"]:
        sections.append(("Alertas recientes", flow["warnings"]))
    if flow["hw_changes"]:
        sections.append(("Cambios HW / apply_params", flow["hw_changes"]))
    if flow["last_peaks"]:
        sections.append(("Últimos picos IQ", flow["last_peaks"]))

    if not args.no_hardware:
        sections.append(("HackRF / fuentes", _probe_hackrf()))
        sections.append(("Salida audio Qt", _probe_audio_output()))

    sections.append(
        (
            "Demod WFM (simulación offline)",
            _probe_demod(fc_hz=args.fc_mhz * 1e6, duration_sec=args.demod_sec),
        )
    )

    hints: list[str] = []
    if flow["counts"].get("frame_gap", 0) > 2:
        hints.append("- Varios frame_gap: revisar stream IQ o reconfigures frecuentes.")
    if flow["counts"].get("stream_restart", 0) > 1:
        hints.append("- Reinicios de stream: ganancias/span pueden estar forzando stop_rx/start_rx.")
    if flow["counts"].get("reconfigure", 0) > 5:
        hints.append("- Muchos reconfigure: parámetros UI cambian HW en bucle.")
    if not flow_lines:
        hints.append("- Sin monitor_flow.log: ejecuta PLAY al menos una vez en la app.")
    hints.append("- Repite prueba y ejecuta de nuevo este script con --tail 800.")
    sections.append(("Interpretación", hints))

    report = _write_report(sections)
    print(f"Reporte: {report}")
    for title, body in sections:
        print(f"\n--- {title} ---")
        for row in body[:12]:
            print(row)
        if len(body) > 12:
            print(f"  … +{len(body) - 12} líneas (ver reporte)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
