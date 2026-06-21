"""Puente SpectrumParams (proyecto) ↔ OperatorIntent (motor RF)."""
from __future__ import annotations

from dataclasses import replace

from core.monitor.monitor_freq_span_logic import display_span_hz
from core.monitor.monitor_operating_mode import MonitorOperatingMode
from core.monitor.spectrum_params import SpectrumFrame, SpectrumParams
from core.rf.acquisition.policy import DefaultAcquisitionPolicy
from core.rf.types import (
    AcquisitionMode,
    AcquisitionPlan,
    AnalysisConfig,
    BasebandConfig,
    DisplayConfig,
    FrequencyWindow,
    OperatingMode,
    OperatorIntent,
    RfFrontendConfig,
    RfHardwareConfig,
    RxGainConfig,
    SpectrumDisplayFrame,
)


def frequency_window_from_params(params: SpectrumParams) -> FrequencyWindow:
    """Ventana de frecuencia coherente con FI/FF o centro+SPAN."""
    if params.uses_start_stop_window():
        return FrequencyWindow.from_start_stop(params.freq_start_hz(), params.freq_stop_hz())
    from core.monitor.monitor_mode_profile import _target_span_hz

    span = max(float(_target_span_hz(params)), 1.0)
    center = float(params.center_freq_hz)
    return FrequencyWindow.from_center_span(center, span)


def operator_intent_from_params(params: SpectrumParams) -> OperatorIntent:
    mode = (
        OperatingMode.SDR
        if params.operating_mode_enum() is MonitorOperatingMode.SDR
        else OperatingMode.SPECTRUM
    )
    hw = RfHardwareConfig(
        center_freq_hz=float(params.center_freq_hz),
        frontend=RfFrontendConfig(
            rf_amp_enable=bool(params.rf_amp_enable),
            bias_tee_enable=bool(params.rf_bias_tee_enable),
        ),
        rx_gain=RxGainConfig(
            lna_db=int(params.lna_gain_db),
            vga_db=int(params.vga_gain_db),
            rf_amp_enable=bool(params.rf_amp_enable),
        ),
        baseband=BasebandConfig(
            sample_rate_hz=float(params.sample_rate_hz or params.span_hz or 10_000_000.0),
            filter_bw_hz=int(params.baseband_filter_bw_hz or 7_000_000),
            filter_auto=bool(params.baseband_filter_auto),
        ),
    )
    analysis = AnalysisConfig(
        rbw_hz=float(params.rbw_hz),
        rbw_auto=bool(params.rbw_auto),
        fft_size=int(params.fft_size),
        fft_auto=bool(params.fft_auto),
        sweep_time_ms=float(params.sweep_time_ms),
        sweep_auto=bool(params.sweep_auto),
        trace_smooth_bins=int(params.trace_smooth_bins),
        trace_smooth_auto=bool(params.trace_smooth_auto),
        detector=str(params.detector or "rms"),
        trace_mode=str(params.trace_mode or "clear_write"),
    )
    display = DisplayConfig(
        ref_level_dbm=float(params.ref_level_dbm),
        ref_range_db=float(params.ref_range_db),
        ref_auto=bool(params.ref_scale_auto),
        amplitude_unit=str(params.amplitude_unit or "dBm"),
        ref_offset_db=float(params.ref_offset_db),
    )
    source = params.source_id or "mock"
    if source == "mock":
        base = "mock"
    elif source.startswith("hackrf"):
        base = "hackrf"
    else:
        base = source.split("_")[0]
    return OperatorIntent(
        window=frequency_window_from_params(params),
        operating_mode=mode,
        hardware=hw,
        analysis=analysis,
        display=display,
        source_id=base,
    )


def prepare_params_for_capture(
    params: SpectrumParams,
    *,
    preserve_iq_span: bool = False,
) -> SpectrumParams:
    """Modo captura + hardware IQ + cadena de analisis (sin resetear RBW/SWT del usuario)."""
    from core.monitor.monitor_bw_sweep_logic import sync_analysis_chain

    updated = params.copy()
    prev_capture = str(updated.capture_mode or "iq")
    if not preserve_iq_span:
        sync_params_capture_mode_from_v2(updated)
    new_capture = str(updated.capture_mode or "iq")
    if not preserve_iq_span:
        if new_capture == "iq":
            updated.clear_freq_window()
            updated.apply_span_as_sample_rate()
            from core.monitor.iq_sdr_profile import sync_iq_hardware

            sync_iq_hardware(updated)
        elif new_capture == "sweep" and prev_capture != new_capture:
            from core.monitor.monitor_freq_span_logic import sync_span_geometry

            sync_span_geometry(updated)
    sync_analysis_chain(updated)
    return updated


def analysis_config_from_params(params: SpectrumParams) -> AnalysisConfig:
    """RBW/FFT/SWT/SUAV efectivos tras ``sync_analysis_chain`` (coherente con GUI)."""
    from core.monitor.monitor_bw_sweep_logic import effective_sweep_time_ms, sweep_bin_width_hz

    if params.capture_mode == "sweep":
        rbw_hz = float(sweep_bin_width_hz(params))
    else:
        rbw_hz = float(params.effective_rbw_hz())
    return AnalysisConfig(
        rbw_hz=rbw_hz,
        rbw_auto=bool(params.rbw_auto),
        fft_size=int(params.fft_size),
        fft_auto=bool(params.fft_auto),
        sweep_time_ms=float(effective_sweep_time_ms(params)),
        sweep_auto=bool(params.sweep_auto),
        trace_smooth_bins=int(params.effective_trace_smooth_bins()),
        trace_smooth_auto=bool(params.trace_smooth_auto),
        detector=str(params.detector or "rms"),
        trace_mode=str(params.trace_mode or "clear_write"),
    )


def enrich_acquisition_plan(
    acquisition: AcquisitionPlan,
    params: SpectrumParams,
    analysis: AnalysisConfig,
) -> AcquisitionPlan:
    """Aplica FFT/RBW/SWT resueltos al plan de captura hardware."""
    from core.rf.display import display_trace_bins
    from core.monitor.monitor_mode_profile import sweep_timeout_sec

    if acquisition.mode is AcquisitionMode.SWEEP and acquisition.sweep is not None:
        from core.monitor.monitor_bw_sweep_logic import sweep_bin_width_hz

        sweep = replace(
            acquisition.sweep,
            start_hz=float(params.freq_start_hz()),
            stop_hz=float(params.freq_stop_hz()),
            bin_width_hz=max(float(sweep_bin_width_hz(params)), 100_000.0),
            lna_db=int(params.lna_gain_db),
            vga_db=int(params.vga_gain_db),
            rf_amp_enable=bool(params.rf_amp_enable),
            bias_tee_enable=bool(params.rf_bias_tee_enable),
            sweep_time_ms=analysis.sweep_time_ms,
            sweep_auto=analysis.sweep_auto,
            fft_size=int(params.fft_size),
            display_bins=int(display_trace_bins(params)),
            rf_attenuation_db=float(params.rf_attenuation_db),
            timeout_sec=float(sweep_timeout_sec(params)),
        )
        return replace(acquisition, sweep=sweep)

    if acquisition.iq is not None:
        iq = replace(
            acquisition.iq,
            center_freq_hz=float(params.center_freq_hz),
            sample_rate_hz=float(params.sample_rate_hz),
            fft_size=max(256, int(analysis.fft_size)),
        )
        return replace(acquisition, iq=iq)
    return acquisition


def sync_params_capture_mode_from_v2(params: SpectrumParams, *, policy: DefaultAcquisitionPolicy | None = None) -> None:
    """Alinea capture_mode legacy con la politica v2 (solo etiqueta UI/motor)."""
    pol = policy or DefaultAcquisitionPolicy()
    intent = operator_intent_from_params(params)
    plan = pol.plan(intent, device_id=intent.source_id)
    new_mode = "sweep" if plan.mode.value == "sweep" else "iq"
    params.capture_mode = new_mode


def legacy_frame_from_display(
    display: SpectrumDisplayFrame,
    *,
    center_freq_hz: float,
    span_hz: float,
) -> SpectrumFrame:
    inner = display.frame
    return SpectrumFrame(
        freqs_hz=inner.freqs_hz,
        power_db=inner.power_db,
        center_freq_hz=center_freq_hz,
        span_hz=span_hz,
        ref_level_dbm=display.ref_level_dbm,
        ref_range_db=display.ref_range_db,
    )
