"""Serialización de SpectrumParams (persistencia proyecto / sesión).

Claves de suavizado de traza: ``trace_smooth_auto``, ``trace_smooth_bins``.
Proyectos antiguos con ``vbw_hz`` / ``vbw_auto`` se migran al cargar; ver
``migrate_legacy_vbw_fields`` y ``docs/monitor_bw_trace.md``.
"""
from __future__ import annotations

from typing import Any, Dict

from core.monitor.monitor_mode_profile import (
    instant_span_hz_for_source,
    max_span_hz_for_source,
    refresh_capture_and_span_limits,
    source_freq_limits_hz,
)
from core.monitor.spectrum_params import SpectrumParams

PERSIST_KEYS = (
    "center_freq_hz",
    "span_hz",
    "manual_span_hz",
    "last_span_hz",
    "analyzer_span_hz",
    "analyzer_span_mode",
    "max_span_hz",
    "span_mode",
    "ref_level_dbm",
    "ref_offset_db",
    "ref_range_db",
    "amplitude_unit",
    "ampt_mode",
    "rf_attenuation_db",
    "ref_scale_auto",
    "lna_gain_db",
    "vga_gain_db",
    "rf_amp_enable",
    "rf_bias_tee_enable",
    "source_id",
    "operating_mode",
    "freq_readout",
    "freq_pan_mode",
    "freq_step_hz",
    "freq_offset_hz",
    "freq_input_mode",
    "selected_freq_hz",
    "marker_start_hz",
    "marker_stop_hz",
    "status_show_start",
    "status_show_center",
    "status_show_stop",
    "status_show_step",
    "status_show_readout",
    "status_show_span",
    "status_show_rbw",
    "status_show_vbw",
    "status_show_sweep",
    "status_show_trace",
    "status_show_detector",
    "status_show_ref",
    "status_show_ref_range",
    "status_show_lna",
    "status_show_preamp",
    "status_show_vga",
    "status_show_att",
    "status_show_capture",
    "status_show_fps",
    "waterfall_min_db",
    "waterfall_max_db",
    "waterfall_auto_levels",
    "waterfall_contrast_auto",
    "waterfall_colormap",
    "display_span_viewport_color",
    "display_span_viewport_hi_color",
    "display_span_track_color",
    "display_span_handle_color",
    "display_trace_color",
    "display_trace_fill",
    "display_sdr_span_viewport_color",
    "display_sdr_span_viewport_hi_color",
    "display_sdr_span_track_color",
    "display_sdr_span_handle_color",
    "display_sdr_trace_color",
    "dock_collapse_mode",
    "dock_auto_collapse_sec",
    "marker_show_line",
    "marker_show_freq",
    "marker_show_level",
    "marker_show_snr",
    "marker_auto_pan",
    "active_marker_id",
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
    "squelch_enabled",
    "show_demod_bandwidth",
    "digital_analysis_enabled",
    "digital_profile",
    "digital_symbol_rate_hz",
    "digital_mod_order",
    "recorder_mode",
    "recorder_directory",
    "recorder_filename",
    "config_panel_collapsed",
    "waterfall_panel_collapsed",
    "audio_volume",
    "audio_muted",
    "sample_rate_hz",
    "baseband_filter_bw_hz",
    "baseband_filter_auto",
    "fft_size",
    "rbw_hz",
    "rbw_auto",
    "fft_auto",
    "trace_smooth_auto",
    "trace_smooth_bins",
    "sweep_time_ms",
    "sweep_auto",
    "sweep_mode",
    "sweep_trigger_mode",
    "sweep_trigger_period_sec",
    "trace_mode",
    "detector",
    "iq_trace_sharp",
    "capture_mode",
    "status_show_rbw",
    "status_show_vbw",
    "status_show_sweep",
    "status_show_trace",
    "status_show_detector",
)

LEGACY_VBW_KEYS = ("vbw_hz", "vbw_auto")


def migrate_legacy_demod_fields(params: SpectrumParams, data: Dict[str, Any]) -> None:
    """Convierte ``demod_mode=fm`` y proyectos sin campos analógicos nuevos."""
    mode = str(data.get("demod_mode", params.demod_mode) or "wfm").lower()
    if mode == "fm":
        params.demod_mode = "wfm"
    if "demod_snap_interval" not in data:
        from core.monitor.analog_demod_profiles import apply_analog_demod_defaults

        merged = apply_analog_demod_defaults(params, params.demod_mode)
        params.demod_snap_interval = merged.demod_snap_interval
        params.demod_deemphasis = merged.demod_deemphasis
        params.demod_noise_blanker_db = merged.demod_noise_blanker_db
        params.demod_agc_attack = merged.demod_agc_attack
        params.demod_agc_decay = merged.demod_agc_decay
        if "demod_bandwidth_hz" not in data and mode == "fm":
            params.demod_bandwidth_hz = merged.demod_bandwidth_hz
    demod_mode = str(params.demod_mode or "wfm").lower()
    if demod_mode in ("fm", "wfm") and float(params.demod_bandwidth_hz or 0) <= 25_000.0:
        params.demod_bandwidth_hz = 200_000.0


def migrate_legacy_vbw_fields(params: SpectrumParams, data: Dict[str, Any]) -> None:
    """Convierte ``vbw_*`` de proyectos guardados antes de la migración SUAV.

    Reglas:
    - ``vbw_auto=True`` → suavizado OFF (``trace_smooth_auto=True``, bins=1).
    - ``vbw_auto=False`` + ``vbw_hz`` → bins ≈ RBW / VBW (clamp al tamaño FFT).
    - Si ``vbw_hz`` ≥ RBW → OFF (equivalente a suavizado nulo).
    """
    if "trace_smooth_auto" in data or "trace_smooth_bins" in data:
        return
    if not any(key in data for key in LEGACY_VBW_KEYS):
        return

    vbw_auto = bool(data.get("vbw_auto", True))
    if vbw_auto:
        params.trace_smooth_auto = True
        params.trace_smooth_bins = 1
        return

    vbw_hz = float(data.get("vbw_hz", 0.0))
    rbw = max(float(params.effective_rbw_hz()), 1.0)
    if vbw_hz <= 0.0 or vbw_hz >= rbw * 0.98:
        params.trace_smooth_auto = True
        params.trace_smooth_bins = 1
        return

    from core.monitor.monitor_bw_sweep_logic import clamp_trace_smooth_bins

    bins = max(1, int(round(rbw / vbw_hz)))
    params.trace_smooth_auto = False
    params.trace_smooth_bins = clamp_trace_smooth_bins(params, bins)


def params_to_dict(params: SpectrumParams) -> Dict[str, Any]:
    from core.monitor.marker_bank import markers_to_dict

    data: Dict[str, Any] = {}
    for key in PERSIST_KEYS:
        if hasattr(params, key):
            value = getattr(params, key)
            if isinstance(value, (int, float, str, bool)):
                data[key] = value
    data["active_marker_id"] = int(params.active_marker_id)
    data["markers"] = markers_to_dict(params.markers)
    return data


def params_from_dict(data: Dict[str, Any], *, base: SpectrumParams | None = None) -> SpectrumParams:
    params = base.copy() if base else SpectrumParams()
    if not isinstance(data, dict):
        return params
    for key in PERSIST_KEYS:
        if key not in data:
            continue
        value = data[key]
        if not hasattr(params, key):
            continue
        current = getattr(params, key)
        if isinstance(current, bool):
            params.__dict__[key] = bool(value)
        elif isinstance(current, int):
            params.__dict__[key] = int(value)
        elif isinstance(current, float):
            params.__dict__[key] = float(value)
        elif isinstance(current, str):
            params.__dict__[key] = str(value)
    params.apply_operating_mode()
    if "status_show_vga" not in data and "status_show_att" in data:
        params.status_show_vga = bool(data.get("status_show_att"))
    refresh_capture_and_span_limits(params)
    if params.capture_mode == "iq":
        from core.monitor.display_scale import snap_iq_sample_rate_hz

        params.sample_rate_hz = snap_iq_sample_rate_hz(params.sample_rate_hz)
        params.sync_iq_display()
        params.clear_freq_window()
        params.marker_auto_pan = False
    if params.has_freq_window():
        from core.monitor.monitor_freq_span_logic import sync_span_geometry

        window_span = max(0.0, float(params.marker_stop_hz - params.marker_start_hz))
        if params.span_mode == "manual" and params.manual_span_hz > window_span + 1.0:
            sync_span_geometry(params)
        else:
            from core.monitor.monitor_freq_span_logic import _apply_start_stop_window

            params = _apply_start_stop_window(
                params,
                params.marker_start_hz,
                params.marker_stop_hz,
                edit_edge="center",
            )
    else:
        params.sync_marker_window_from_span()
    from core.monitor.monitor_bw_sweep_logic import sync_analysis_chain

    sync_analysis_chain(params)
    migrate_legacy_vbw_fields(params, data)
    migrate_legacy_demod_fields(params, data)
    from core.monitor.marker_bank import markers_from_dict, migrate_legacy_marker_bank

    if isinstance(data.get("markers"), list):
        params.markers = markers_from_dict(data.get("markers"), center_hz=params.center_freq_hz)
    else:
        migrate_legacy_marker_bank(params, data)
    if "active_marker_id" in data:
        params.active_marker_id = max(1, min(10, int(data["active_marker_id"])))
    if (params.demod_mode or "").lower() == "dig":
        if "digital_analysis_enabled" in data:
            params.digital_analysis_enabled = bool(data["digital_analysis_enabled"])
        if params.digital_analysis_enabled:
            params.capture_mode = "iq"
            params.audio_enabled = False
    params.sync_receive_mode_effects()
    params.running = False
    return params
