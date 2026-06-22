"""Perfiles de operación Monitor — límites SDR vs analizador."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from core.monitor.monitor_operating_mode import MonitorOperatingMode, normalize_operating_mode
from core.monitor.spectrum_params import SpectrumParams

SPAN_MIN_IQ_HZ = 2_000_000.0
SPAN_MIN_SWEEP_HZ = 100_000.0


def _base_source_id(source_id: str) -> str:
    from core.rf.source_ids import device_family

    if not source_id:
        return "mock"
    return device_family(source_id)


def source_freq_limits_hz(source_id: str) -> Tuple[float, float]:
    """Rango sintonizable del equipo (Hz)."""
    base = _base_source_id(source_id)
    if base in ("hackrf", "mock"):
        return 1_000_000.0, 6_000_000_000.0
    if base == "airspy":
        return 24_000_000.0, 1_800_000_000.0
    if base == "airspy_hf":
        return 50_000.0, 31_000_000.0
    if base == "rf_explorer":
        return 15_000_000.0, 2_700_000_000.0
    if base == "tinysa":
        return 100_000.0, 960_000_000.0
    return 1_000_000.0, 6_000_000_000.0


def instant_span_hz_for_source(source_id: str) -> float:
    """Ancho de banda instantáneo máximo (modo SDR / IQ)."""
    base = _base_source_id(source_id)
    if base in ("hackrf", "mock"):
        return 20_000_000.0
    if base == "airspy":
        return 10_000_000.0
    if base == "airspy_hf":
        return 660_000.0
    if base in ("rf_explorer", "tinysa"):
        return 100_000.0
    return 20_000_000.0


def device_full_span_hz(source_id: str) -> float:
    """Lapso completo del equipo: Fmax − Fmin (estilo analizador Full Span)."""
    fmin, fmax = source_freq_limits_hz(source_id)
    return fmax - fmin


def full_span_window_hz(source_id: str) -> tuple[float, float, float]:
    """Ventana lapso completo: (center_hz, span_hz, start_hz)."""
    fmin, fmax = source_freq_limits_hz(source_id)
    span = fmax - fmin
    center = (fmin + fmax) / 2.0
    return center, span, fmin


def apply_full_span_freq_window(params: SpectrumParams) -> None:
    """F inicio / F final = rango del equipo (estilo analizador Full Span)."""
    fmin, fmax = source_freq_limits_hz(params.source_id)
    params.marker_start_hz = fmin
    params.marker_stop_hz = fmax
    params.center_freq_hz = (fmin + fmax) / 2.0
    params.manual_span_hz = fmax - fmin
    if params.freq_readout == "fc":
        params.selected_freq_hz = params.center_freq_hz
        if params.operating_mode_enum().demod_enabled():
            params.vfo_freq_hz = params.center_freq_hz


def max_span_hz_for_source(
    source_id: str,
    *,
    operating_mode: str = MonitorOperatingMode.SPECTRUM.value,
    center_freq_hz: float = 100_000_000.0,
) -> float:
    """SPAN máximo según modo: SDR = BW instantáneo; analizador = lapso en FC."""
    instant = instant_span_hz_for_source(source_id)
    mode = normalize_operating_mode(operating_mode)
    if mode is MonitorOperatingMode.SDR:
        return instant

    fmin, fmax = source_freq_limits_hz(source_id)
    center = max(fmin, min(fmax, float(center_freq_hz)))
    span_at_center = 2.0 * min(center - fmin, fmax - center)
    return max(instant, span_at_center)


def ui_max_span_hz(params: SpectrumParams) -> float:
    """SPAN máximo en controles UI (lapso completo del equipo en analizador)."""
    mode = normalize_operating_mode(params.operating_mode)
    if mode is MonitorOperatingMode.SDR:
        return instant_span_hz_for_source(params.source_id)
    return device_full_span_hz(params.source_id)


@dataclass(frozen=True)
class MonitorModeProfile:
    """Restricciones de hardware/UI por modo."""

    operating_mode: MonitorOperatingMode
    capture_mode: str  # "iq" | "sweep"
    max_span_hz: float
    instant_span_hz: float
    demod_enabled: bool
    supervision_enabled: bool
    realtime_fft: bool


def profile_for_params(params: SpectrumParams) -> MonitorModeProfile:
    mode = params.operating_mode_enum()
    instant = instant_span_hz_for_source(params.source_id)
    max_span = max_span_hz_for_source(
        params.source_id,
        operating_mode=params.operating_mode,
        center_freq_hz=params.center_freq_hz,
    )
    return MonitorModeProfile(
        operating_mode=mode,
        capture_mode=params.capture_mode,
        max_span_hz=max_span,
        instant_span_hz=instant,
        demod_enabled=mode.demod_enabled(),
        supervision_enabled=mode is MonitorOperatingMode.SPECTRUM,
        realtime_fft=params.capture_mode == "iq",
    )


def refresh_capture_and_span_limits(params: SpectrumParams) -> None:
    """Recalcula max_span, capture_mode y acota SPAN al cambiar modo o FC."""
    from core.rf.source_ids import is_analyzer_only_source

    mode = normalize_operating_mode(params.operating_mode)
    params.operating_mode = mode.value
    params.max_span_hz = max_span_hz_for_source(
        params.source_id,
        operating_mode=params.operating_mode,
        center_freq_hz=params.center_freq_hz,
    )
    instant = instant_span_hz_for_source(params.source_id)

    if is_analyzer_only_source(params.source_id):
        params.operating_mode = MonitorOperatingMode.SPECTRUM.value
        mode = MonitorOperatingMode.SPECTRUM
        params.capture_mode = "sweep"
        params.audio_enabled = False
        if not params.supervision_dwell_active:
            params.digital_analysis_enabled = False
        params.supervision_enabled = True
        params.sync_marker_window_from_span()
        params.apply_span_mode()
        return

    if mode is MonitorOperatingMode.SDR:
        params.capture_mode = "iq"
        if (params.demod_mode or "fm").lower() != "dig":
            params.audio_enabled = True
        params.supervision_enabled = False
        if params.manual_span_hz > instant:
            params.manual_span_hz = instant
    else:
        params.audio_enabled = False
        if not params.supervision_dwell_active:
            params.digital_analysis_enabled = False
        params.supervision_enabled = True
        target_span = _target_span_hz(params)
        from core.rf.bridge import sync_params_capture_mode_from_v2

        sync_params_capture_mode_from_v2(params)

    params.apply_span_mode()


def transition_operating_mode(
    params: SpectrumParams,
    *,
    previous_mode: MonitorOperatingMode,
    new_mode: MonitorOperatingMode,
) -> bool:
    """Prepara FC/SPAN al cambiar ANALIZADOR ↔ SDR.

    Convención A (estándar show / SDR++):
    - Analizador → SDR: FC igual; SPAN solo se reduce si supera el BW instantáneo
      (~20 MHz HackRF). Si ya cabe (p. ej. 10 MHz), se mantiene.
    - SDR → Analizador: restaurar lapso y modo guardados en ``analyzer_span_*``.

    Returns:
        True si el SPAN activo se acotó al entrar en SDR (lapso analizador > instant).
    """
    if previous_mode == new_mode:
        return False

    instant = instant_span_hz_for_source(params.source_id)
    span_clamped = False

    if new_mode is MonitorOperatingMode.SDR and previous_mode is not MonitorOperatingMode.SDR:
        saved_span = _analyzer_span_to_save(params)
        params.analyzer_span_hz = saved_span
        params.analyzer_span_mode = str(params.span_mode or "manual")
        params.remember_span_before_mode_change()
        params.span_mode = "manual"
        active_span = float(params.manual_span_hz) if params.manual_span_hz > 0 else saved_span
        if active_span > instant + 1.0:
            span_clamped = True
            params.manual_span_hz = instant
        elif active_span > 0:
            params.manual_span_hz = max(SPAN_MIN_IQ_HZ, min(active_span, instant))
        else:
            params.manual_span_hz = instant
        params.clear_freq_window()
        params.vfo_freq_hz = params.center_freq_hz
        params.selected_freq_hz = params.center_freq_hz
    elif previous_mode is MonitorOperatingMode.SDR and new_mode is not MonitorOperatingMode.SDR:
        _restore_analyzer_span(params)
        params.clear_freq_window()

    return span_clamped


def _analyzer_span_to_save(params: SpectrumParams) -> float:
    from core.monitor.monitor_freq_span_logic import display_span_hz as ui_display_span_hz

    saved_span = max(0.0, ui_display_span_hz(params))
    if saved_span <= 0.0:
        saved_span = max(0.0, float(params.manual_span_hz))
    if params.span_mode == "full":
        saved_span = device_full_span_hz(params.source_id)
    return saved_span


def _restore_analyzer_span(params: SpectrumParams) -> None:
    if params.analyzer_span_hz <= 0.0:
        return
    restored_mode = str(params.analyzer_span_mode or "manual")
    if restored_mode in ("manual", "full", "last", "zero"):
        params.span_mode = restored_mode
    if restored_mode == "manual":
        params.manual_span_hz = params.analyzer_span_hz
    params.analyzer_span_hz = 0.0
    params.analyzer_span_mode = ""


def _target_span_hz(params: SpectrumParams) -> float:
    if params.span_mode == "full":
        return device_full_span_hz(params.source_id)
    if params.span_mode == "zero":
        return 0.0
    if params.span_mode == "last":
        return max(params.last_span_hz, params.manual_span_hz)
    return max(0.0, params.manual_span_hz)


def sweep_timeout_sec(params: SpectrumParams) -> float:
    """Tiempo máximo de un barrido hackrf_sweep según lapso / SWEEP."""
    from core.monitor.monitor_bw_sweep_logic import effective_sweep_time_ms

    if not params.sweep_auto:
        return max(2.0, effective_sweep_time_ms(params) / 1000.0)
    span_hz = max(1.0, params.freq_stop_hz() - params.freq_start_hz())
    span_mhz = span_hz / 1_000_000.0
    return max(12.0, min(180.0, 8.0 + span_mhz * 0.3))


def clamp_center_to_source(params: SpectrumParams) -> None:
    fmin, fmax = source_freq_limits_hz(params.source_id)
    params.center_freq_hz = max(fmin, min(fmax, params.center_freq_hz))
