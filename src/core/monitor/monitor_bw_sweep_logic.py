"""RBW / suavizado de traza / barrido — lógica compartida (SDR++ + analizador).

Resolución (RBW o FFT) y suavizado (SUAV) son independientes:

- ``patch_rbw_*`` / ``patch_fft_size`` — cadena de análisis en frecuencia.
- ``patch_trace_smooth_*`` — ancho del kernel espacial en ``core/rf/analysis/pipeline.py``.

Política AUTO del analizador: ``core/rf/display.py`` y ``core/rf/acquisition/policy.py``. Ver ``docs/rf_engine/policies.md``.
"""
from __future__ import annotations

import math

from core.rf.display import (
    ANALYZER_AUTO_POINTS,
    auto_sweep_time_ms_for_span,
    clamp_sweep_rbw_hz,
    display_trace_bins,
    pick_auto_fft_size,
    pick_stable_sweep_rbw,
    snap_fft_size,
)
from core.monitor.spectrum_params import SpectrumParams

RBW_PRESETS_HZ = (
    100.0,
    300.0,
    1_000.0,
    3_000.0,
    10_000.0,
    30_000.0,
    100_000.0,
    300_000.0,
    1_000_000.0,
)

VBW_PRESETS_HZ = RBW_PRESETS_HZ  # legacy — no usar en código nuevo

SWEEP_TIME_PRESETS_MS = (10.0, 50.0, 100.0, 200.0, 500.0, 1000.0, 2000.0, 5000.0)

TRACE_MODES = ("clear_write", "max_hold", "min_hold", "average")
DETECTORS = ("peak", "rms", "sample", "neg_peak", "average")
SWEEP_MODES = ("continuous", "single")
SWEEP_TRIGGER_MODES = ("continuous", "manual", "periodic")
SWEEP_TRIGGER_PERIODS_SEC = (0.5, 1.0, 2.0, 5.0, 10.0, 30.0)

# Puntos FFT legacy (imports GUI); AUTO usa ~ANALYZER_AUTO_POINTS vía pick_auto_fft_size.
DEFAULT_AUTO_FFT_SIZE = 2048
SWEEP_RBW_MIN_HZ = 100_000.0
SWEEP_RBW_MAX_HZ = 5_000_000.0


def _snap_fft_size(n: int, *, min_size: int = 256) -> int:
    return snap_fft_size(n, min_size=min_size)


def analysis_bandwidth_hz(params: SpectrumParams) -> float:
    if params.capture_mode == "iq":
        return max(params.sample_rate_hz, 1.0)
    span = max(params.span_hz, params.display_span_hz(), 1.0)
    return span


def sweep_analysis_span_hz(params: SpectrumParams) -> float:
    """Ancho efectivo del barrido (ventana F ini–F fin o SPAN)."""
    window = max(float(params.freq_stop_hz()) - float(params.freq_start_hz()), 0.0)
    return max(window, float(params.span_hz), float(params.display_span_hz()), 1.0)


def auto_rbw_hz(params: SpectrumParams) -> float:
    return analysis_bandwidth_hz(params) / max(params.fft_size, 1)


def optimize_analyzer_auto_for_span(params: SpectrumParams) -> None:
    """Acopla RBW / rejilla FFT / SWT en AUTO — cada flag es independiente en barrido."""
    if params.capture_mode == "iq":
        return
    if params.rbw_auto:
        span = sweep_analysis_span_hz(params)
        current = params.rbw_hz if params.rbw_hz > 0 else None
        params.rbw_hz = pick_stable_sweep_rbw(span, current)
    if params.fft_auto:
        params.fft_size = pick_auto_fft_size(params)
    if params.sweep_auto:
        params.sweep_time_ms = auto_sweep_time_ms(params)


def resolved_sweep_rbw_hz(params: SpectrumParams) -> float:
    """RBW de barrido (Hz) sin recursar con ``effective_rbw_hz``."""
    if params.rbw_auto:
        span = sweep_analysis_span_hz(params)
        current = params.rbw_hz if params.rbw_hz > 0 else None
        return pick_stable_sweep_rbw(span, current)
    from core.rf.display import clamp_sweep_rbw_hz

    return clamp_sweep_rbw_hz(float(params.rbw_hz))


def sweep_bin_width_hz(params: SpectrumParams) -> float:
    """RBW efectivo en barrido HackRF (hackrf_sweep no admite bins < 100 kHz)."""
    if params.capture_mode == "sweep":
        return max(resolved_sweep_rbw_hz(params), 100_000.0)
    return max(params.effective_rbw_hz(), 100.0)


def auto_sweep_time_ms(params: SpectrumParams) -> float:
    span_hz = sweep_analysis_span_hz(params)
    rbw = sweep_bin_width_hz(params)
    return auto_sweep_time_ms_for_span(span_hz, rbw)


def _freeze_sweep_on_manual_rbw(params: SpectrumParams) -> None:
    """Al pasar RBW a manual en barrido, congela SWT en el valor efectivo actual."""
    if params.capture_mode != "sweep":
        return
    if params.sweep_auto:
        params.sweep_time_ms = effective_sweep_time_ms(params)
        params.sweep_auto = False


def effective_sweep_time_ms(params: SpectrumParams) -> float:
    if params.sweep_auto:
        return auto_sweep_time_ms(params)
    return max(1.0, float(params.sweep_time_ms))


def sync_fft_size_from_rbw(params: SpectrumParams) -> None:
    if params.rbw_auto:
        return
    if params.capture_mode == "sweep":
        return
    bw = max(analysis_bandwidth_hz(params), 1.0)
    rbw = max(float(params.rbw_hz), 1.0)
    if not math.isfinite(bw) or not math.isfinite(rbw):
        return
    ratio = bw / rbw
    if not math.isfinite(ratio) or ratio <= 0:
        return
    min_fft = 64 if params.capture_mode == "iq" else 256
    params.fft_size = _snap_fft_size(ratio, min_size=min_fft)
    if params.capture_mode == "iq":
        params.rbw_hz = bw / max(params.fft_size, 1)


def normalize_resolution_flags(params: SpectrumParams) -> None:
    """Unifica flags AUTO/MANUAL al cambiar IQ ↔ barrido."""
    if params.capture_mode == "iq":
        if params.rbw_auto != params.fft_auto:
            params.fft_auto = False
            params.rbw_auto = False
        else:
            params.rbw_auto = params.fft_auto
        params.rbw_hz = params.sample_rate_hz / max(params.fft_size, 1)


def patch_rbw_manual(params: SpectrumParams) -> SpectrumParams:
    """Pasa RBW a manual conservando el valor efectivo actual."""
    updated = params.copy()
    if updated.capture_mode == "sweep":
        if updated.rbw_auto:
            updated.rbw_hz = max(1.0, float(updated.effective_rbw_hz()))
        _freeze_sweep_on_manual_rbw(updated)
        updated.rbw_auto = False
        return updated
    return patch_fft_manual(updated)


def patch_rbw_auto(params: SpectrumParams, *, enabled: bool = True) -> SpectrumParams:
    if not enabled:
        return patch_rbw_manual(params)
    updated = params.copy()
    if updated.capture_mode == "iq":
        return patch_fft_auto(updated, enabled=True)
    updated.rbw_auto = True
    optimize_analyzer_auto_for_span(updated)
    if updated.sweep_auto:
        updated.sweep_time_ms = auto_sweep_time_ms(updated)
    return updated


def _maybe_switch_iq_for_fine_rbw(params: SpectrumParams, rbw_hz: float) -> SpectrumParams:
    """RBW < 100 kHz no es válido en hackrf_sweep; usar IQ si el lapso cabe."""
    from core.rf.capabilities import capabilities_for_device

    updated = params.copy()
    hz = max(1.0, float(rbw_hz))
    if updated.capture_mode != "sweep" or hz >= SWEEP_RBW_MIN_HZ:
        return updated
    caps = capabilities_for_device(updated.source_id or "hackrf")
    span = max(float(updated.display_span_hz()), float(updated.span_hz), 1.0)
    if span > caps.instant_bw_hz + 1.0:
        return updated
    updated.capture_mode = "iq"
    updated.rbw_hz = hz
    updated.rbw_auto = False
    updated.fft_auto = False
    if updated.sample_rate_hz <= 0 or updated.sample_rate_hz > caps.instant_bw_hz:
        updated.apply_span_as_sample_rate()
    updated.fft_size = _snap_fft_size(int(updated.sample_rate_hz / hz), min_size=256)
    from core.monitor.iq_sdr_profile import sync_iq_hardware

    sync_iq_hardware(updated)
    return updated


def patch_rbw_hz(params: SpectrumParams, rbw_hz: float) -> SpectrumParams:
    updated = params.copy()
    preserve_fft = updated.capture_mode == "sweep"
    fft_size = updated.fft_size
    fft_auto = updated.fft_auto
    if updated.capture_mode == "sweep":
        _freeze_sweep_on_manual_rbw(updated)
    updated.rbw_auto = False
    switched = _maybe_switch_iq_for_fine_rbw(updated, rbw_hz)
    if switched.capture_mode == "iq" and updated.capture_mode == "sweep":
        return switched
    updated = switched
    if updated.capture_mode == "sweep":
        from core.rf.display import clamp_sweep_rbw_hz, snap_sweep_rbw_to_preset

        updated.rbw_hz = snap_sweep_rbw_to_preset(clamp_sweep_rbw_hz(float(rbw_hz)))
        if preserve_fft:
            updated.fft_size = fft_size
            updated.fft_auto = fft_auto
    else:
        updated.rbw_hz = max(1.0, float(rbw_hz))
        updated.fft_auto = False
        updated.rbw_auto = False
        sync_fft_size_from_rbw(updated)
    return updated


def patch_fft_manual(params: SpectrumParams) -> SpectrumParams:
    """Pasa FFT/rejilla a manual conservando el valor efectivo actual."""
    updated = params.copy()
    if updated.capture_mode == "sweep":
        if updated.fft_auto:
            updated.fft_size = pick_auto_fft_size(updated)
        updated.fft_auto = False
        return updated
    updated.fft_auto = False
    updated.rbw_auto = False
    updated.rbw_hz = updated.sample_rate_hz / max(updated.fft_size, 1)
    return updated


def patch_fft_auto(params: SpectrumParams, *, enabled: bool = True) -> SpectrumParams:
    if not enabled:
        return patch_fft_manual(params)
    updated = params.copy()
    if updated.capture_mode == "sweep":
        updated.fft_auto = True
        if updated.fft_auto:
            updated.fft_size = pick_auto_fft_size(updated)
        return updated
    updated.fft_auto = True
    updated.fft_size = pick_auto_fft_size(updated)
    updated.rbw_auto = True
    updated.rbw_hz = updated.sample_rate_hz / max(updated.fft_size, 1)
    return updated


def patch_fft_size(params: SpectrumParams, fft_size: int) -> SpectrumParams:
    """Resolución IQ — puntos FFT. En barrido: puntos de rejilla en pantalla (no RBW hardware)."""
    updated = params.copy()
    min_fft = 64 if updated.capture_mode == "iq" else 256
    updated.fft_size = _snap_fft_size(int(fft_size), min_size=min_fft)
    if updated.capture_mode == "iq":
        updated.rbw_auto = False
        updated.fft_auto = False
        if updated.sample_rate_hz <= 0:
            updated.apply_span_as_sample_rate()
        updated.rbw_hz = updated.sample_rate_hz / max(updated.fft_size, 1)
    else:
        updated.fft_auto = False
    return updated


def clamp_trace_smooth_bins(params: SpectrumParams, bins: int) -> int:
    """Limita el ancho del kernel de suavizado al número de bins FFT."""
    from core.rf.display import display_trace_bins

    cap = max(display_trace_bins(params), 64)
    return max(1, min(int(bins), cap))


def default_manual_smooth_bins(params: SpectrumParams) -> int:
    """Preset por defecto al pasar SUAV de OFF a manual."""
    from core.monitor.monitor_bw_profile import smooth_presets_for_params

    presets = smooth_presets_for_params(params)
    for choice in (5, 3, 11, 21):
        if choice in presets:
            return choice
    return presets[-1] if presets else 5


def patch_trace_smooth_auto(params: SpectrumParams, *, enabled: bool = True) -> SpectrumParams:
    """SUAV OFF — traza sin suavizado espacial extra."""
    if not enabled:
        return patch_trace_smooth_manual(params)
    updated = params.copy()
    updated.trace_smooth_auto = True
    return updated


def patch_trace_smooth_manual(params: SpectrumParams) -> SpectrumParams:
    """Activa SUAV manual; si venía de OFF, asigna un preset razonable (×N bins)."""
    updated = params.copy()
    updated.trace_smooth_auto = False
    if params.trace_smooth_auto:
        updated.trace_smooth_bins = default_manual_smooth_bins(updated)
    else:
        updated.trace_smooth_bins = clamp_trace_smooth_bins(updated, updated.trace_smooth_bins)
    return updated


def patch_trace_smooth_bins(params: SpectrumParams, bins: int) -> SpectrumParams:
    """Fija el ancho del suavizado en bins adyacentes (presets ×3, ×5, …)."""
    updated = params.copy()
    updated.trace_smooth_auto = False
    updated.trace_smooth_bins = clamp_trace_smooth_bins(updated, bins)
    return updated


def patch_vbw_hz(params: SpectrumParams, vbw_hz: float) -> SpectrumParams:
    """Compatibilidad: convierte ancho Hz legacy a bins y delega en ``patch_trace_smooth_bins``."""
    rbw = max(float(params.effective_rbw_hz()), 1.0)
    hz = max(0.1, min(float(vbw_hz), rbw * 0.99))
    if hz >= rbw * 0.98:
        return patch_trace_smooth_auto(params, enabled=True)
    bins = max(1, int(round(rbw / hz)))
    return patch_trace_smooth_bins(params, bins)


# Aliases legacy (imports existentes en GUI/tests).
patch_vbw_auto = patch_trace_smooth_auto
patch_vbw_manual = patch_trace_smooth_manual
patch_smooth_bins = patch_trace_smooth_bins


def patch_iq_trace_sharp(params: SpectrumParams, *, enabled: bool) -> SpectrumParams:
    """Activa traza fina IQ: pico, SUAV ligero, FFT AUTO ampliada si span ancho."""
    updated = params.copy()
    updated.iq_trace_sharp = bool(enabled)
    if enabled:
        updated.detector = "peak"
        updated.trace_smooth_auto = False
        updated.trace_smooth_bins = 3
    if updated.capture_mode == "iq" and updated.fft_auto:
        from core.rf.display import pick_auto_fft_size

        updated.fft_size = pick_auto_fft_size(updated)
        updated.rbw_hz = updated.sample_rate_hz / max(updated.fft_size, 1)
    return updated


def patch_sweep_auto(params: SpectrumParams, *, enabled: bool = True) -> SpectrumParams:
    updated = params.copy()
    updated.sweep_auto = bool(enabled)
    if enabled:
        updated.sweep_time_ms = auto_sweep_time_ms(updated)
    else:
        updated.sweep_time_ms = effective_sweep_time_ms(params)
    return updated


def patch_sweep_time_ms(params: SpectrumParams, sweep_ms: float) -> SpectrumParams:
    updated = params.copy()
    updated.sweep_auto = False
    updated.sweep_time_ms = max(1.0, float(sweep_ms))
    return updated


def patch_sweep_mode(params: SpectrumParams, mode: str) -> SpectrumParams:
    updated = params.copy()
    normalized = str(mode).lower()
    if normalized not in SWEEP_MODES:
        normalized = "continuous"
    updated.sweep_mode = normalized
    return updated


def patch_sweep_trigger_mode(params: SpectrumParams, mode: str) -> SpectrumParams:
    updated = params.copy()
    normalized = str(mode).lower()
    if normalized not in SWEEP_TRIGGER_MODES:
        normalized = "continuous"
    updated.sweep_trigger_mode = normalized
    if normalized == "continuous":
        updated.sweep_mode = "continuous"
        updated.single_sweep_pending = False
    elif normalized == "manual":
        updated.sweep_mode = "single"
        updated.single_sweep_pending = False
    else:
        updated.sweep_mode = "single"
        updated.single_sweep_pending = True
    return updated


def patch_sweep_trigger_period(params: SpectrumParams, period_sec: float) -> SpectrumParams:
    updated = params.copy()
    updated.sweep_trigger_period_sec = max(0.2, float(period_sec))
    return updated


def arm_sweep_trigger(params: SpectrumParams) -> SpectrumParams:
    updated = params.copy()
    updated.single_sweep_pending = True
    return updated


def patch_trace_mode(params: SpectrumParams, mode: str) -> SpectrumParams:
    updated = params.copy()
    if mode not in TRACE_MODES:
        mode = "clear_write"
    updated.trace_mode = mode
    return updated


def patch_detector(params: SpectrumParams, detector: str) -> SpectrumParams:
    updated = params.copy()
    if detector not in DETECTORS:
        detector = "rms"
    updated.detector = detector
    return updated


def arm_single_sweep(params: SpectrumParams) -> SpectrumParams:
    updated = patch_sweep_mode(params, "single")
    updated.single_sweep_pending = True
    return updated


def capture_trace_now(params: SpectrumParams) -> SpectrumParams:
    """Congela la traza visible en max-hold (sustituto simple del barrido único)."""
    updated = patch_trace_mode(params, "max_hold")
    updated.sweep_mode = "continuous"
    updated.single_sweep_pending = False
    return updated


def sync_analysis_chain(params: SpectrumParams) -> None:
    normalize_resolution_flags(params)
    if params.capture_mode == "iq":
        from core.monitor.iq_sdr_profile import sync_iq_rbw_label

        if params.fft_auto:
            sync_iq_rbw_label(params)
        else:
            params.rbw_hz = params.sample_rate_hz / max(params.fft_size, 1)
            params.rbw_auto = False
        return
    if params.rbw_auto:
        span = sweep_analysis_span_hz(params)
        current = params.rbw_hz if params.rbw_hz > 0 else None
        params.rbw_hz = pick_stable_sweep_rbw(span, current)
    elif params.rbw_hz > 0:
        from core.rf.display import clamp_sweep_rbw_hz, snap_sweep_rbw_to_preset

        params.rbw_hz = snap_sweep_rbw_to_preset(
            clamp_sweep_rbw_hz(float(params.rbw_hz))
        )
    if params.fft_auto:
        params.fft_size = pick_auto_fft_size(params)
    if params.sweep_auto:
        params.sweep_time_ms = auto_sweep_time_ms(params)
