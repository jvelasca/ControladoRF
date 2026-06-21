"""Log del flujo de datos Monitor — apply_params, reconfigure, stream IQ."""
from __future__ import annotations

import inspect
import logging
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Iterable, Optional

_LOG_NAME = "controladorf.monitor.flow"
_CONFIGURED = False

# Solo cambios en estos campos pueden reiniciar el stream IQ / barrido.
HARDWARE_PARAM_KEYS = frozenset(
    {
        "center_freq_hz",
        "sample_rate_hz",
        "lna_gain_db",
        "vga_gain_db",
        "rf_amp_enable",
        "rf_bias_tee_enable",
        "baseband_filter_bw_hz",
        "capture_mode",
    }
)

RF_GAIN_PARAM_KEYS = frozenset(
    {
        "lna_gain_db",
        "vga_gain_db",
        "rf_amp_enable",
        "rf_bias_tee_enable",
    }
)

# Cambios de análisis/visualización — no reinician stream IQ ni hackrf_transfer.
DISPLAY_PARAM_KEYS = frozenset(
    {
        "ref_level_dbm",
        "ref_range_db",
        "ref_scale_auto",
        "ref_offset_db",
        "amplitude_unit",
        "ampt_mode",
        "vertical_divisions",
        "horizontal_divisions",
        "rf_attenuation_db",
        "waterfall_min_db",
        "waterfall_max_db",
        "waterfall_auto_levels",
        "fft_size",
        "rbw_hz",
        "rbw_auto",
        "trace_smooth_auto",
        "trace_smooth_bins",
        "sweep_time_ms",
        "sweep_auto",
        "detector",
        "trace_mode",
        "display_span_viewport_color",
        "display_span_viewport_hi_color",
        "display_span_track_color",
        "display_span_handle_color",
        "display_trace_color",
        "display_sdr_span_viewport_color",
        "display_sdr_span_viewport_hi_color",
        "display_sdr_span_track_color",
        "display_sdr_span_handle_color",
        "display_sdr_trace_color",
    }
)

# Campos que afectan al panel RADIO (demod, audio, modo operativo).
RADIO_PANEL_KEYS = frozenset(
    {
        "operating_mode",
        "capture_mode",
        "vfo_freq_hz",
        "demod_mode",
        "demod_bandwidth_hz",
        "demod_snap_interval",
        "demod_deemphasis",
        "demod_noise_blanker_db",
        "demod_wfm_stereo",
        "demod_wfm_rds",
        "demod_wfm_lowpass",
        "demod_iq_correction",
        "demod_iq_invert",
        "demod_agc_attack",
        "demod_agc_decay",
        "squelch_db",
        "squelch_rf_level_dbm",
        "show_demod_bandwidth",
        "audio_volume",
        "audio_muted",
        "audio_enabled",
        "digital_analysis_enabled",
        "digital_profile",
        "digital_symbol_rate_hz",
        "digital_mod_order",
    }
)


def _ensure_logger() -> logging.Logger:
    global _CONFIGURED
    logger = logging.getLogger(_LOG_NAME)
    if _CONFIGURED:
        return logger
    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        log_dir / "monitor_flow.log",
        maxBytes=3 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    )
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    _CONFIGURED = True
    return logger


def infer_apply_source() -> str:
    """Infiera origen del apply_params (slider dock, toolbar, status…)."""
    for frame in inspect.stack()[2:10]:
        func = frame.function
        if func.startswith("_apply_params_from_"):
            return func.removeprefix("_apply_params_from_")
        filename = Path(frame.filename).name
        if filename == "monitor_toolbar.py":
            return "toolbar"
        if filename == "monitor_spectrum_overlays.py":
            if "Ampt" in frame.code_context[0] if frame.code_context else "":
                return "overlay_ref"
            if "Vrange" in frame.code_context[0] if frame.code_context else "":
                return "overlay_range"
            return "overlay_sliders"
        if filename == "monitor_rf_overlays.py":
            return "overlay_rf"
        if filename == "monitor_waterfall_overlays.py":
            return "waterfall_levels"
    return "unknown"


def param_value_changed(key: str, old, new) -> bool:
    if isinstance(old, bool) or isinstance(new, bool):
        return bool(old) != bool(new)
    if isinstance(old, (int, float)) or isinstance(new, (int, float)):
        old_f = float(old)
        new_f = float(new)
        if key.endswith("_hz") or "freq" in key:
            return abs(old_f - new_f) > 0.5
        if key.endswith("_db") or key.endswith("_dbm"):
            return abs(old_f - new_f) > 0.05
        return abs(old_f - new_f) > 1e-9
    return old != new


def is_sdr_rf_gain_only_patch(prev, updated) -> bool:
    """SDR IQ: solo LNA/VGA/P cambió — no re-sincronizar SPAN ni sample rate."""
    from core.monitor.monitor_operating_mode import MonitorOperatingMode

    if prev.operating_mode_enum() is not MonitorOperatingMode.SDR:
        return False
    if str(getattr(prev, "capture_mode", "")) != "iq" or str(getattr(updated, "capture_mode", "")) != "iq":
        return False
    frozen = (
        prev.span_mode == updated.span_mode
        and abs(float(prev.manual_span_hz) - float(updated.manual_span_hz)) <= 1.0
        and abs(float(prev.span_hz) - float(updated.span_hz)) <= 1.0
        and abs(float(prev.sample_rate_hz) - float(updated.sample_rate_hz)) <= 1.0
        and abs(float(prev.center_freq_hz) - float(updated.center_freq_hz)) <= 0.5
        and prev.operating_mode == updated.operating_mode
    )
    if not frozen:
        return False
    if not any(
        param_value_changed(key, getattr(prev, key), getattr(updated, key))
        for key in RF_GAIN_PARAM_KEYS
        if hasattr(prev, key) and hasattr(updated, key)
    ):
        return False
    scan_keys = HARDWARE_PARAM_KEYS | DISPLAY_PARAM_KEYS | frozenset(
        {
            "span_mode",
            "manual_span_hz",
            "max_span_hz",
            "marker_start_hz",
            "marker_stop_hz",
            "operating_mode",
            "baseband_filter_auto",
        }
    )
    for key in scan_keys:
        if key in RF_GAIN_PARAM_KEYS:
            continue
        if not hasattr(prev, key) or not hasattr(updated, key):
            continue
        if param_value_changed(key, getattr(prev, key), getattr(updated, key)):
            return False
    return True


def diff_param_keys(prev, updated, keys: Iterable[str]) -> list[str]:
    changed: list[str] = []
    for key in keys:
        if not hasattr(prev, key) or not hasattr(updated, key):
            continue
        old = getattr(prev, key)
        new = getattr(updated, key)
        if param_value_changed(key, old, new):
            changed.append(f"{key}={old!r}->{new!r}")
    return changed


def log_apply_params(
    *,
    source: str,
    display_changes: list[str],
    hardware_changes: list[str],
    triggers_reconfigure: bool,
    running: bool,
) -> None:
    logger = _ensure_logger()
    if not display_changes and not hardware_changes:
        return
    hw = ", ".join(hardware_changes) if hardware_changes else "(ninguno)"
    disp = ", ".join(display_changes[:8]) if display_changes else "(ninguno)"
    if len(display_changes) > 8:
        disp += f" …+{len(display_changes) - 8}"
    level = logging.INFO if (hardware_changes and running) else logging.DEBUG
    logger.log(
        level,
        "apply_params source=%s running=%s reconfigure=%s | HW[%s] | UI[%s]",
        source,
        running,
        triggers_reconfigure,
        hw,
        disp,
    )


def log_reconfigure_scheduled(changed_hw: list[str], *, delay_sec: float = 0.65) -> None:
    logger = _ensure_logger()
    logger.debug(
        "reconfigure_scheduled in %.2fs | %s",
        delay_sec,
        ", ".join(changed_hw) if changed_hw else "(sin cambios HW)",
    )


def log_reconfigure_done(*, ok: bool, msg: str, elapsed_ms: float, capture_mode: str) -> None:
    logger = _ensure_logger()
    level = logging.INFO if ok else logging.WARNING
    logger.log(
        level,
        "reconfigure_done ok=%s mode=%s %.1fms | %s",
        ok,
        capture_mode,
        elapsed_ms,
        msg[:200],
    )


def log_stream_restart(*, reason: str, detail: str = "") -> None:
    logger = _ensure_logger()
    level = logging.DEBUG if reason in ("params_changed", "recover") else logging.WARNING
    logger.log(level, "stream_restart reason=%s %s", reason, detail[:200])


def log_capture_error(msg: str, *, fatal: bool = False) -> None:
    logger = _ensure_logger()
    (logger.error if fatal else logger.warning)("capture_error fatal=%s | %s", fatal, msg[:300])


def log_frame_gap(gap_sec: float, *, capture_mode: str) -> None:
    logger = _ensure_logger()
    logger.debug("frame_gap %.2fs mode=%s (sin tramas recientes)", gap_sec, capture_mode)


def log_diagnose_marker(label: str) -> None:
    """Marca inicio/fin de prueba manual — analizar con scripts/monitor_diagnose_session.py."""
    logger = _ensure_logger()
    logger.info("DIAG_MARKER %s", label.strip()[:120])


class ReconfigureTimer:
    """Mide duración de reconfigure en vivo."""

    def __init__(self) -> None:
        self._t0 = 0.0

    def start(self) -> None:
        self._t0 = time.monotonic()

    def elapsed_ms(self) -> float:
        return (time.monotonic() - self._t0) * 1000.0
