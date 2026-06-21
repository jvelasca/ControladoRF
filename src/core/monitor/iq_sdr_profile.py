"""Modo IQ/SDR: separar hardware (SR, filtro FI, ganancias) de pantalla (RBW/VBW)."""
from __future__ import annotations

from core.monitor.spectrum_params import SpectrumParams


def uses_iq_sdr_profile(params: SpectrumParams) -> bool:
    return params.capture_mode == "iq"


def sync_iq_hardware(params: SpectrumParams) -> None:
    """Sample rate + filtro FI HackRF (no toca VBW ni suavizado de traza)."""
    if not uses_iq_sdr_profile(params):
        return
    params.sync_baseband_filter_bw()
    from core.monitor.monitor_iq_rf_logic import ensure_baseband_filter_valid

    ensure_baseband_filter_valid(params)
    params.sync_iq_display()


def sync_iq_rbw_label(params: SpectrumParams) -> None:
    """RBW en IQ = SR/FFT (SDR++); en AUTO recalcula FFT y rbw_hz."""
    from core.monitor.monitor_bw_sweep_logic import pick_auto_fft_size

    if not uses_iq_sdr_profile(params):
        return
    if params.fft_auto:
        params.fft_size = pick_auto_fft_size(params)
    params.rbw_hz = params.sample_rate_hz / max(params.fft_size, 1)
    params.rbw_auto = params.fft_auto


def prepare_iq_for_play(params: SpectrumParams) -> None:
    """Una vez al PLAY: barrido continuo y ventana de frecuencia limpia."""
    if not uses_iq_sdr_profile(params):
        return
    params.sweep_trigger_mode = "continuous"
    params.single_sweep_pending = False
    params.clear_freq_window()
    sync_iq_hardware(params)
    sync_iq_rbw_label(params)
