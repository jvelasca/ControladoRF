"""Preset FM broadcast — réplica de SDR++ en 93,2 MHz (referencia del usuario)."""
from __future__ import annotations

from core.monitor.analog_demod_profiles import apply_analog_demod_defaults, snap_vfo_freq_hz
from core.monitor.display_scale import snap_iq_sample_rate_hz
from core.monitor.hackrf_rx_gains import snap_hackrf_params
from core.monitor.monitor_operating_mode import MonitorOperatingMode
from core.monitor.spectrum_params import SpectrumParams

# SDR++ @ 105,2 MHz: span 2 MHz, LNA 40, VGA 18, P ON, IF NR ON, BW 200 kHz, snap 100 kHz, 50 µs.
SDRPP_FM_REFERENCE_HZ = 105_200_000.0
SDRPP_FM_SPAN_HZ = 2_000_000.0
SDRPP_FM_LNA_DB = 40
SDRPP_FM_VGA_DB = 18
SDRPP_FM_BW_HZ = 200_000.0
SDRPP_FM_SNAP_HZ = 100_000.0
SDRPP_FM_SQUELCH_DBFS = -81.0


def _tune_hz(params: SpectrumParams) -> float:
    if params.freq_readout == "f" and params.selected_freq_hz > 0:
        return float(params.selected_freq_hz)
    if params.vfo_freq_hz > 0:
        return float(params.vfo_freq_hz)
    return float(params.center_freq_hz)


def apply_sdrpp_wfm_reference(
    params: SpectrumParams,
    *,
    tune_hz: float | None = None,
) -> SpectrumParams:
    """Ajustes SDR++ WFM: 2 MHz IQ, LNA 40, VGA 18, P ON, sin Bias-T/IQ corr/invert, offset 0."""
    updated = apply_analog_demod_defaults(params.copy(), "wfm")
    updated.operating_mode = MonitorOperatingMode.SDR.value
    updated.capture_mode = "iq"
    updated.audio_enabled = True
    updated.demod_mode = "wfm"
    updated.demod_bandwidth_hz = SDRPP_FM_BW_HZ
    updated.demod_snap_interval = SDRPP_FM_SNAP_HZ
    updated.demod_deemphasis = "50us"
    updated.demod_noise_blanker_db = 8.0
    updated.demod_wfm_stereo = True
    updated.demod_wfm_rds = True
    updated.demod_wfm_lowpass = True
    updated.demod_iq_correction = False
    updated.demod_iq_invert = False
    updated.squelch_db = SDRPP_FM_SQUELCH_DBFS
    updated.ref_scale_auto = True
    updated.span_mode = "manual"
    updated.manual_span_hz = SDRPP_FM_SPAN_HZ
    updated.span_hz = SDRPP_FM_SPAN_HZ
    updated.sample_rate_hz = snap_iq_sample_rate_hz(SDRPP_FM_SPAN_HZ)
    updated.apply_span_as_sample_rate()
    updated.sync_iq_display()
    updated.baseband_filter_auto = True
    updated.sync_baseband_filter_bw()
    updated.freq_readout = "f"
    updated.freq_offset_hz = 0.0
    updated.lna_gain_db = SDRPP_FM_LNA_DB
    updated.vga_gain_db = SDRPP_FM_VGA_DB
    updated.rf_amp_enable = True
    updated.rf_bias_tee_enable = False

    hz = float(tune_hz if tune_hz is not None else _tune_hz(params))
    if hz <= 0.0:
        hz = SDRPP_FM_REFERENCE_HZ
    snapped = snap_vfo_freq_hz(hz, updated.demod_snap_interval)
    updated.vfo_freq_hz = snapped
    updated.selected_freq_hz = snapped
    updated.center_freq_hz = snapped
    return snap_hackrf_params(updated)


def apply_fm_broadcast_preset(params: SpectrumParams) -> SpectrumParams:
    """Preset FM Broad — parámetros SDR++ sin cambiar la frecuencia de sintonía actual."""
    return apply_sdrpp_wfm_reference(params)
