"""Lógica compartida FC / SPAN (toolbar + sliders del gráfico)."""
from __future__ import annotations

import math

from core.monitor.monitor_mode_profile import (
    SPAN_MIN_IQ_HZ,
    SPAN_MIN_SWEEP_HZ,
    apply_full_span_freq_window,
    clamp_center_to_source,
    device_full_span_hz,
    full_span_window_hz,
    instant_span_hz_for_source,
    refresh_capture_and_span_limits,
    source_freq_limits_hz,
    ui_max_span_hz,
)
from core.monitor.spectrum_params import SpectrumParams

STEP_PRESETS_HZ = (
    1_000.0,
    5_000.0,
    10_000.0,
    12_500.0,
    25_000.0,
    50_000.0,
    100_000.0,
    250_000.0,
    1_000_000.0,
)


def ui_span_min_hz(params: SpectrumParams) -> float:
    """Mínimo mostrado en UI (analizador permite barrido fino)."""
    from core.monitor.monitor_operating_mode import MonitorOperatingMode

    if params.operating_mode_enum() is MonitorOperatingMode.SDR:
        return SPAN_MIN_IQ_HZ
    return SPAN_MIN_SWEEP_HZ


def span_min_hz(params: SpectrumParams) -> float:
    """Mínimo SPAN: IQ = sample rate HackRF (2 MHz); barrido = resolución fina."""
    if params.capture_mode == "sweep":
        return SPAN_MIN_SWEEP_HZ
    return SPAN_MIN_IQ_HZ


def display_span_hz(params: SpectrumParams) -> float:
    """SPAN mostrado en toolbar/slider (coherente con modo analizador vs SDR)."""
    from core.monitor.monitor_operating_mode import MonitorOperatingMode

    if params.operating_mode_enum() is MonitorOperatingMode.SDR:
        hz = float(params.manual_span_hz)
        if hz <= 0.0 and params.capture_mode == "iq":
            hz = float(params.span_hz or params.sample_rate_hz)
        return max(0.0, hz)

    if params.span_mode == "manual" and params.manual_span_hz > 0.0:
        return max(0.0, float(params.manual_span_hz))
    if params.has_freq_window():
        return max(0.0, float(params.marker_stop_hz - params.marker_start_hz))
    return max(0.0, float(params.display_span_hz()))


def clamp_center_hz(params: SpectrumParams, hz: float) -> float:
    fmin, fmax = source_freq_limits_hz(params.source_id)
    return max(fmin, min(fmax, float(hz)))


def visible_freq_window_hz(params: SpectrumParams) -> tuple[float, float]:
    """Rango visible en espectro/waterfall (Hz): ventana FI/FF o IQ."""
    if params.capture_mode == "iq":
        half = float(params.sample_rate_hz) / 2.0
        center = float(params.center_freq_hz)
        return center - half, center + half
    if params.uses_start_stop_window():
        return float(params.marker_start_hz), float(params.marker_stop_hz)
    start = float(params.freq_start_hz())
    stop = float(params.freq_stop_hz())
    if stop <= start:
        half = max(float(display_span_hz(params)) / 2.0, 1.0)
        center = float(params.center_freq_hz)
        return center - half, center + half
    return start, stop


def clamp_freq_to_visible_hz(params: SpectrumParams, freq_hz: float) -> float:
    start, stop = visible_freq_window_hz(params)
    return max(start, min(stop, float(freq_hz)))


def nudge_step_hz(params: SpectrumParams) -> float:
    from core.monitor.display_scale import center_freq_step_hz

    if params.operating_mode_enum().demod_enabled():
        step = float(params.demod_snap_interval or 0.0)
        if step > 0.0:
            return step
    step = float(params.freq_step_hz or 0.0)
    if step > 0.0:
        return step
    return center_freq_step_hz(active_freq_hz(params))


def nudge_selected_freq_hz(params: SpectrumParams, delta_hz: float) -> float:
    return clamp_freq_to_visible_hz(params, active_freq_hz(params) + float(delta_hz))


def clamp_span_hz(params: SpectrumParams, hz: float) -> float:
    if hz <= 0.0:
        return 0.0
    minimum = span_min_hz(params)
    return max(minimum, min(float(params.max_span_hz), float(hz)))


def active_freq_hz(params: SpectrumParams) -> float:
    if params.freq_readout == "f":
        return float(params.selected_freq_hz)
    return float(params.center_freq_hz)


def _effective_max_span_for_window(params: SpectrumParams) -> float:
    """SPAN máximo al editar FI/FF (SDR = BW instantáneo; analizador = lapso del equipo)."""
    from core.monitor.monitor_operating_mode import MonitorOperatingMode

    instant = instant_span_hz_for_source(params.source_id)
    mode = params.operating_mode_enum()
    if mode is MonitorOperatingMode.SDR:
        return instant
    return device_full_span_hz(params.source_id)


def _clamp_start_stop_window(
    params: SpectrumParams,
    start_hz: float,
    stop_hz: float,
    *,
    edit_edge: str,
    preserve_user_edges: bool = False,
) -> tuple[float, float]:
    """Acota ventana [start, stop] al rango del equipo (estilo analizador)."""
    fmin, fmax = source_freq_limits_hz(params.source_id)
    min_span = ui_span_min_hz(params)
    start = float(start_hz)
    stop = float(stop_hz)

    if stop <= start:
        if edit_edge == "stop":
            start = stop - min_span
        elif edit_edge == "start":
            stop = start + min_span
        else:
            center = (start + stop) / 2.0
            start = center - min_span / 2.0
            stop = center + min_span / 2.0

    if start < fmin:
        delta = fmin - start
        start = fmin
        if edit_edge == "stop":
            stop = max(stop, start + min_span)
        else:
            stop += delta
    if stop > fmax:
        delta = stop - fmax
        stop = fmax
        if edit_edge == "start":
            start = min(start, stop - min_span)
        else:
            start -= delta

    start = max(fmin, start)
    stop = min(fmax, stop)
    if stop <= start:
        stop = min(fmax, start + min_span)
        start = max(fmin, min(start, stop - min_span))

    if preserve_user_edges:
        return start, stop

    span = stop - start
    max_span = float(params.max_span_hz)
    if span > max_span:
        span = max_span
        if edit_edge == "stop":
            start = stop - span
        elif edit_edge == "start":
            stop = start + span
        else:
            center = (start + stop) / 2.0
            start = center - span / 2.0
            stop = center + span / 2.0
        start = max(fmin, start)
        stop = min(fmax, stop)
        if stop <= start:
            stop = min(fmax, start + min(ui_span_min_hz(params), max_span))

    return start, stop


def _enforce_freq_window_limits(params: SpectrumParams, *, edit_edge: str) -> None:
    """Tras elegir modo captura, ajusta FI/FF solo si el hardware lo exige (borde editado fijo)."""
    if not params.has_freq_window():
        return
    fmin, fmax = source_freq_limits_hz(params.source_id)
    min_span = ui_span_min_hz(params)
    max_span = _effective_max_span_for_window(params)
    start = float(params.marker_start_hz)
    stop = float(params.marker_stop_hz)

    start = max(fmin, min(fmax, start))
    stop = max(fmin, min(fmax, stop))
    if stop <= start:
        if edit_edge == "stop":
            start = max(fmin, stop - min_span)
        elif edit_edge == "start":
            stop = min(fmax, start + min_span)
        else:
            center = (start + stop) / 2.0
            start = max(fmin, center - min_span / 2.0)
            stop = min(fmax, center + min_span / 2.0)

    span = stop - start
    if span < min_span:
        if edit_edge == "stop":
            start = max(fmin, stop - min_span)
        elif edit_edge == "start":
            stop = min(fmax, start + min_span)
        else:
            center = (start + stop) / 2.0
            start = max(fmin, center - min_span / 2.0)
            stop = min(fmax, center + min_span / 2.0)
        span = stop - start

    if span > max_span:
        if edit_edge == "start":
            stop = min(fmax, start + max_span)
        elif edit_edge == "stop":
            start = max(fmin, stop - max_span)
        else:
            center = (start + stop) / 2.0
            half = max_span / 2.0
            start = max(fmin, center - half)
            stop = min(fmax, center + half)
            if stop - start > max_span:
                if edit_edge == "stop":
                    start = max(fmin, stop - max_span)
                elif edit_edge == "start":
                    stop = min(fmax, start + max_span)

    params.marker_start_hz = start
    params.marker_stop_hz = stop
    params.manual_span_hz = max(0.0, stop - start)
    params.center_freq_hz = (start + stop) / 2.0
    if params.operating_mode_enum().demod_enabled():
        if params.freq_readout == "f":
            params.vfo_freq_hz = params.selected_freq_hz
        else:
            params.vfo_freq_hz = params.center_freq_hz


def _apply_start_stop_window(
    params: SpectrumParams,
    start_hz: float,
    stop_hz: float,
    *,
    edit_edge: str,
) -> SpectrumParams:
    start, stop = _clamp_start_stop_window(
        params,
        start_hz,
        stop_hz,
        edit_edge=edit_edge,
        preserve_user_edges=True,
    )
    span = stop - start
    params.center_freq_hz = (start + stop) / 2.0
    params.selected_freq_hz = params.center_freq_hz
    if params.operating_mode_enum().demod_enabled():
        params.vfo_freq_hz = params.center_freq_hz
    params.span_mode = "manual"
    params.manual_span_hz = span
    params.marker_start_hz = start
    params.marker_stop_hz = stop
    refresh_capture_and_span_limits(params)
    _enforce_freq_window_limits(params, edit_edge=edit_edge)
    refresh_capture_and_span_limits(params)
    params.apply_span_mode()
    if params.capture_mode == "iq":
        params.apply_span_as_sample_rate()
    return params


def patch_freq_start(params: SpectrumParams, start_hz: float) -> SpectrumParams:
    updated = params.copy()
    stop = updated.freq_stop_hz()
    return _apply_start_stop_window(updated, start_hz, stop, edit_edge="start")


def patch_freq_stop(params: SpectrumParams, stop_hz: float) -> SpectrumParams:
    updated = params.copy()
    start = updated.freq_start_hz()
    return _apply_start_stop_window(updated, start, stop_hz, edit_edge="stop")


def patch_freq_step(params: SpectrumParams, step_hz: float) -> SpectrumParams:
    updated = params.copy()
    updated.freq_step_hz = max(1.0, float(step_hz))
    return updated


def patch_freq_readout(params: SpectrumParams, mode: str) -> SpectrumParams:
    updated = params.copy()
    updated.freq_readout = mode
    if mode == "fc":
        updated.freq_pan_mode = "pan_spectrum"
        updated.selected_freq_hz = updated.center_freq_hz
        if updated.operating_mode_enum().demod_enabled():
            updated.vfo_freq_hz = updated.center_freq_hz
    else:
        updated.freq_pan_mode = "marker_fixed"
        from core.monitor.marker_bank import sync_selected_freq_from_active_marker

        sync_selected_freq_from_active_marker(updated)
        if abs(updated.selected_freq_hz) < 1.0:
            updated.selected_freq_hz = updated.center_freq_hz
        updated = patch_selected_freq(
            updated,
            clamp_freq_to_visible_hz(updated, updated.selected_freq_hz),
            clamp_visible=True,
        )
    return updated


def patch_freq_pan_mode(params: SpectrumParams, mode: str) -> SpectrumParams:
    updated = params.copy()
    updated.freq_pan_mode = mode
    return updated


def patch_freq_offset(params: SpectrumParams, offset_hz: float) -> SpectrumParams:
    updated = params.copy()
    updated.freq_offset_hz = float(offset_hz)
    return updated


def patch_freq_input_mode(params: SpectrumParams, mode: str) -> SpectrumParams:
    updated = params.copy()
    updated.freq_input_mode = mode
    return updated


def _sync_marker_window(params: SpectrumParams) -> None:
    """Sincroniza marcadores solo si no hay ventana F inicio/F final definida."""
    if params.has_freq_window():
        return
    params.sync_marker_window_from_span()


def _set_center_preserve_window(params: SpectrumParams, center_hz: float) -> None:
    """Mueve FC manteniendo ventana [F ini, F fin] o sincroniza desde SPAN."""
    center = clamp_center_hz(params, center_hz)
    params.center_freq_hz = center
    if params.has_freq_window():
        width = max(float(params.marker_stop_hz - params.marker_start_hz), ui_span_min_hz(params))
        half = width / 2.0
        fmin, fmax = source_freq_limits_hz(params.source_id)
        start = center - half
        stop = center + half
        if start < fmin:
            stop = min(fmax, stop + (fmin - start))
            start = fmin
        if stop > fmax:
            start = max(fmin, start - (stop - fmax))
            stop = fmax
        params.marker_start_hz = start
        params.marker_stop_hz = stop
        params.manual_span_hz = stop - start
    else:
        params.sync_marker_window_from_span()


def _resize_window_from_center(params: SpectrumParams, span_hz: float) -> None:
    """Actualiza F inicio/F fin alrededor de FC cuando hay ventana activa."""
    span = max(float(span_hz), ui_span_min_hz(params))
    half = span / 2.0
    center = float(params.center_freq_hz)
    params.marker_start_hz = center - half
    params.marker_stop_hz = center + half
    params.manual_span_hz = span


def sync_span_geometry(params: SpectrumParams) -> None:
    """Alinea ventana FI/FF y marcadores con el SPAN manual activo."""
    from core.monitor.monitor_operating_mode import MonitorOperatingMode

    if params.operating_mode_enum() is MonitorOperatingMode.SDR or params.capture_mode == "iq":
        params.clear_freq_window()
        return

    if params.span_mode == "manual" and params.manual_span_hz > 0.0:
        if params.has_freq_window():
            window_span = max(0.0, float(params.marker_stop_hz - params.marker_start_hz))
            if abs(float(params.manual_span_hz) - window_span) > 1.0:
                params.clear_freq_window()
        params.sync_marker_window_from_span()
        return
    if not params.has_freq_window():
        params.sync_marker_window_from_span()


def patch_center_freq(params: SpectrumParams, center_hz: float) -> SpectrumParams:
    """Modo FC: la frecuencia indicada queda en el centro; el SPAN no cambia."""
    updated = params.copy()
    _set_center_preserve_window(updated, center_hz)
    refresh_capture_and_span_limits(updated)
    if updated.capture_mode == "iq" and updated.span_mode == "manual":
        updated.apply_span_as_sample_rate()
    if updated.freq_readout == "fc":
        updated.selected_freq_hz = updated.center_freq_hz
        if updated.operating_mode_enum().demod_enabled():
            updated.vfo_freq_hz = updated.center_freq_hz
    return updated


def active_marker_freq_hz(params: SpectrumParams) -> float:
    """Frecuencia del marcador activo (M1…M10); si está apagado, centro de la ventana."""
    from core.monitor.marker_bank import resolve_marker_frequency_hz

    freq = resolve_marker_frequency_hz(params, params.active_marker_id)
    if freq is not None:
        return float(freq)
    if params.freq_readout == "f":
        return float(params.selected_freq_hz)
    return float(params.center_freq_hz)


def ensure_marker_visible(params: SpectrumParams) -> SpectrumParams:
    """Modo F: desplaza la ventana para mantener F visible — estilo analizador."""
    if params.capture_mode == "iq":
        return params
    if params.freq_readout != "f" or not params.marker_auto_pan:
        return params
    start = params.freq_start_hz()
    stop = params.freq_stop_hz()
    if stop <= start:
        return params
    margin = max((stop - start) * 0.04, 1000.0)
    from core.monitor.marker_bank import resolve_marker_frequency_hz

    freq = resolve_marker_frequency_hz(params, params.active_marker_id)
    if freq is None:
        freq = params.selected_freq_hz
    if start + margin <= freq <= stop - margin:
        return params
    return patch_center_freq(params, freq)


def ref_level_step_index(
    ref_level_dbm: float,
    *,
    unit: str,
    ref_offset_db: float = 0.0,
    step_count: int | None = None,
) -> int:
    from core.monitor.amplitude_units import dbm_to_display, ref_level_display_range
    from core.monitor.marker_analysis import REF_LEVEL_STEP_COUNT

    steps = step_count or REF_LEVEL_STEP_COUNT
    low, high = ref_level_display_range(unit)
    display = dbm_to_display(ref_level_dbm, unit, ref_offset_db=ref_offset_db)
    ratio = (display - low) / max(high - low, 1e-9)
    return int(round(max(0.0, min(1.0, ratio)) * max(0, steps - 1)))


def ref_level_from_step_index(
    index: int,
    *,
    unit: str,
    ref_offset_db: float = 0.0,
    step_count: int | None = None,
) -> float:
    from core.monitor.amplitude_units import display_to_dbm, ref_level_display_range
    from core.monitor.marker_analysis import REF_LEVEL_STEP_COUNT

    steps = step_count or REF_LEVEL_STEP_COUNT
    low, high = ref_level_display_range(unit)
    idx = max(0, min(steps - 1, int(index)))
    ratio = idx / max(steps - 1, 1)
    display = low + ratio * (high - low)
    return display_to_dbm(display, unit, ref_offset_db=ref_offset_db)


def patch_selected_freq(
    params: SpectrumParams,
    freq_hz: float,
    *,
    clamp_visible: bool = False,
) -> SpectrumParams:
    """Modo F: fija la frecuencia del marcador activo sin mover ventana ni SPAN."""
    from core.monitor.marker_bank import patch_active_marker_frequency

    updated = params.copy()
    target = float(freq_hz)
    if clamp_visible:
        target = clamp_freq_to_visible_hz(updated, target)
    else:
        target = clamp_center_hz(updated, target)
    patch_active_marker_frequency(updated, target)
    if updated.operating_mode_enum().demod_enabled():
        from core.monitor.analog_demod_profiles import snap_vfo_freq_hz

        vfo = float(updated.selected_freq_hz)
        updated.vfo_freq_hz = snap_vfo_freq_hz(vfo, updated.demod_snap_interval)
        updated.selected_freq_hz = updated.vfo_freq_hz
    return ensure_marker_visible(updated)


def patch_manual_span(params: SpectrumParams, span_hz: float) -> SpectrumParams:
    """SPAN manual: modo centro+lapso (deja de usar FI/FF como anclaje)."""
    updated = params.copy()
    updated.clear_freq_window()
    center_before = updated.center_freq_hz
    selected_before = updated.selected_freq_hz
    updated.span_mode = "manual"
    updated.manual_span_hz = max(0.0, float(span_hz))
    refresh_capture_and_span_limits(updated)
    limit = float(updated.max_span_hz)
    updated.manual_span_hz = max(0.0, min(limit, float(span_hz)))
    minimum = span_min_hz(updated)
    updated.manual_span_hz = max(minimum, updated.manual_span_hz)
    refresh_capture_and_span_limits(updated)
    updated.center_freq_hz = center_before
    updated.selected_freq_hz = selected_before
    if updated.operating_mode_enum().demod_enabled():
        updated.vfo_freq_hz = selected_before if updated.freq_readout == "f" else center_before
    sync_span_geometry(updated)
    return updated


def zoom_manual_span(
    params: SpectrumParams,
    factor: float,
    *,
    anchor_hz: float | None = None,
) -> SpectrumParams:
    """factor > 1 acota SPAN (zoom in). anchor_hz fija el punto bajo el cursor."""
    current = display_span_hz(params)
    if current <= 0 or factor <= 0 or not math.isfinite(factor):
        return params
    new_span = clamp_span_hz(params, current / factor)
    if abs(new_span - current) < 1.0:
        return params
    updated = patch_manual_span(params, new_span)
    if anchor_hz is not None:
        anchor = float(anchor_hz)
        half_old = current * 0.5
        half_new = new_span * 0.5
        center = float(updated.center_freq_hz)
        offset = anchor - center
        if abs(offset) <= half_old + 1.0:
            ratio = offset / half_old if half_old > 0 else 0.0
            _set_center_preserve_window(updated, anchor - ratio * half_new)
    return updated


def patch_span_mode(params: SpectrumParams, mode: str) -> SpectrumParams:
    """Lapso manual / completo / cero / último — recalcula límites y modo captura."""
    updated = params.copy()
    center_before = updated.center_freq_hz
    selected_before = updated.selected_freq_hz
    if mode != "manual":
        updated.remember_span_before_mode_change()
    updated.span_mode = mode
    if mode == "full":
        center, span, _start = full_span_window_hz(updated.source_id)
        updated.center_freq_hz = center
        updated.manual_span_hz = span
        if updated.freq_readout == "fc":
            updated.selected_freq_hz = center
            if updated.operating_mode_enum().demod_enabled():
                updated.vfo_freq_hz = center
    elif mode == "manual" and updated.manual_span_hz <= 0:
        updated.manual_span_hz = max(updated.last_span_hz, ui_span_min_hz(updated))
    refresh_capture_and_span_limits(updated)
    if mode == "full":
        apply_full_span_freq_window(updated)
    else:
        updated.center_freq_hz = center_before
        updated.selected_freq_hz = selected_before
        if updated.operating_mode_enum().demod_enabled():
            updated.vfo_freq_hz = selected_before if updated.freq_readout == "f" else center_before
        _sync_marker_window(updated)
    from core.monitor.monitor_bw_sweep_logic import sync_analysis_chain

    sync_analysis_chain(updated)
    return updated


def patch_hackrf_lna(params: SpectrumParams, lna_db: int) -> SpectrumParams:
    from core.monitor.hackrf_rx_gains import snap_lna_db

    updated = params.copy()
    updated.lna_gain_db = snap_lna_db(int(lna_db))
    return updated


def patch_hackrf_vga(params: SpectrumParams, vga_db: int) -> SpectrumParams:
    from core.monitor.hackrf_rx_gains import snap_vga_db

    updated = params.copy()
    updated.vga_gain_db = snap_vga_db(int(vga_db))
    return updated


def patch_hackrf_amp(params: SpectrumParams, *, enabled: bool) -> SpectrumParams:
    from core.monitor.hackrf_rx_gains import snap_hackrf_params

    updated = params.copy()
    updated.rf_amp_enable = bool(enabled)
    return snap_hackrf_params(updated)


def patch_vga_gain(params: SpectrumParams, vga_db: int) -> SpectrumParams:
    return patch_hackrf_vga(params, vga_db)


def patch_ref_level(params: SpectrumParams, ref_level_dbm: float) -> SpectrumParams:
    updated = params.copy()
    updated.ref_scale_auto = False
    updated.ampt_mode = "ref_level"
    updated.ref_level_dbm = float(ref_level_dbm)
    return updated


def patch_ref_auto(params: SpectrumParams, *, enabled: bool = True) -> SpectrumParams:
    updated = params.copy()
    updated.ref_scale_auto = bool(enabled)
    if enabled:
        updated.ampt_mode = "ref_level"
    return updated


def patch_ref_range(
    params: SpectrumParams,
    range_db: float,
    *,
    db_div: float | None = None,
) -> SpectrumParams:
    updated = params.copy()
    updated.ref_scale_auto = False
    updated.ampt_mode = "ref_range"
    updated.ref_range_db = float(range_db)
    if db_div is not None and db_div > 0:
        updated.vertical_divisions = max(1, int(round(updated.ref_range_db / db_div)))
    return updated


def patch_rf_input(
    params: SpectrumParams,
    *,
    lna_gain_db: int | None = None,
    vga_gain_db: int | None = None,
    rf_amp_enable: bool | None = None,
) -> SpectrumParams:
    """Parche RF — cuantiza cada control sin acoplar LNA/VGA (HackRF nativo)."""
    from core.monitor.hackrf_rx_gains import snap_hackrf_params

    updated = params.copy()
    if lna_gain_db is not None:
        updated = patch_hackrf_lna(updated, int(lna_gain_db))
    if vga_gain_db is not None:
        updated = patch_hackrf_vga(updated, int(vga_gain_db))
    if rf_amp_enable is not None:
        updated = patch_hackrf_amp(updated, enabled=bool(rf_amp_enable))
    updated = snap_hackrf_params(updated)
    if updated.capture_mode == "sweep":
        updated.rf_attenuation_db = max(0.0, 40.0 - updated.lna_gain_db)
    return updated


def freq_slider_value(params: SpectrumParams) -> int:
    from core.monitor.display_scale import freq_in_span_to_slider, freq_to_slider_value

    if params.freq_readout == "f":
        start, stop = visible_freq_window_hz(params)
        return freq_in_span_to_slider(params.selected_freq_hz, start, stop)
    return freq_to_slider_value(params.center_freq_hz)


def selected_freq_from_slider_value(params: SpectrumParams, value: int) -> float:
    from core.monitor.display_scale import slider_to_freq_in_span

    if params.freq_readout != "f":
        from core.monitor.display_scale import slider_value_to_freq

        return slider_value_to_freq(value)
    start, stop = visible_freq_window_hz(params)
    return slider_to_freq_in_span(value, start, stop)


def span_slider_value(params: SpectrumParams) -> int:
    from core.monitor.display_scale import span_to_slider_value

    min_hz = ui_span_min_hz(params)
    span_hz = max(display_span_hz(params), min_hz)
    return span_to_slider_value(
        span_hz,
        max_span_hz=ui_max_span_hz(params),
        min_span_hz=min_hz,
    )


def span_zoom_viewport(params: SpectrumParams) -> tuple[float, float, float, float]:
    """Geometría del slider SPAN: (fmin_hz, range_hz, center_ratio, width_ratio).

    Analizador: pista = rango sintonizable del equipo; sombra = ventana SPAN+FC.
    SDR: pista = BW instantáneo (mín–máx, p. ej. 2–20 MHz); sombra = ancho BW actual.
    """
    from core.monitor.monitor_operating_mode import MonitorOperatingMode
    from core.monitor.monitor_mode_profile import ui_max_span_hz

    if params.operating_mode_enum() is MonitorOperatingMode.SDR:
        min_hz = ui_span_min_hz(params)
        max_hz = max(float(ui_max_span_hz(params)), min_hz + 1.0)
        range_hz = max(max_hz - min_hz, 1.0)
        span = min(max(float(display_span_hz(params)), min_hz), max_hz)
        width_ratio = min(1.0, (span - min_hz) / range_hz)
        if width_ratio >= 1.0 - 1e-9:
            return float(min_hz), range_hz, 0.5, 1.0
        center_ratio = 0.5
        half = width_ratio / 2.0
        center_ratio = max(half, min(1.0 - half, center_ratio))
        return float(min_hz), range_hz, center_ratio, width_ratio

    fmin, fmax = source_freq_limits_hz(params.source_id)
    range_hz = max(float(fmax - fmin), 1.0)
    span = max(float(display_span_hz(params)), 1.0)
    center = float(params.center_freq_hz)
    width_ratio = min(1.0, span / range_hz)
    if width_ratio >= 1.0 - 1e-9:
        return float(fmin), range_hz, 0.5, 1.0
    center_ratio = (center - fmin) / range_hz
    half = width_ratio / 2.0
    center_ratio = max(half, min(1.0 - half, center_ratio))
    return float(fmin), range_hz, center_ratio, width_ratio


def center_hz_from_span_zoom_ratio(params: SpectrumParams, center_ratio: float) -> float:
    """Convierte posición del cursor zoom a FC (Hz); en SDR la pista es solo BW."""
    from core.monitor.monitor_operating_mode import MonitorOperatingMode

    if params.operating_mode_enum() is MonitorOperatingMode.SDR:
        return float(params.center_freq_hz)
    fmin, range_hz, _, width_ratio = span_zoom_viewport(params)
    half = width_ratio / 2.0
    ratio = max(half, min(1.0 - half, float(center_ratio)))
    return fmin + ratio * range_hz
