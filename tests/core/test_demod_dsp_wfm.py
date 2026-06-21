"""Tests cadena demodulación WFM."""
from __future__ import annotations

import numpy as np

from core.monitor.demod_dsp import (
    DemodStreamState,
    _audio_lowpass_cutoff_hz,
    _channel_filter_cutoff_hz,
    demod_iq_to_audio,
)
from core.monitor.spectrum_params import SpectrumParams


def test_wfm_channel_filter_uses_broadcast_bandwidth() -> None:
    cutoff = _channel_filter_cutoff_hz("wfm", 20_000.0, 2_000_000.0)
    assert cutoff >= 60_000.0
    assert _audio_lowpass_cutoff_hz("wfm", 20_000.0) == 15_000.0


def test_wfm_demod_produces_audio_from_tone() -> None:
    sr = 2_000_000.0
    deviation = 50_000.0
    audio_tone = 1_000.0
    n = 8192
    t = np.arange(n, dtype=np.float64) / sr
    phase = 2.0 * np.pi * deviation / sr * np.cumsum(np.sin(2.0 * np.pi * audio_tone * t))
    iq = np.exp(1j * phase).astype(np.complex64)

    params = SpectrumParams(
        center_freq_hz=100e6,
        vfo_freq_hz=100e6,
        demod_mode="wfm",
        demod_bandwidth_hz=200_000.0,
        demod_deemphasis="50us",
        squelch_db=-120.0,
    )
    state = DemodStreamState()
    result = demod_iq_to_audio(iq, params, sample_rate_hz=sr, stream_state=state)
    assert result.pcm.size > 0
    assert result.level_dbfs > -80.0
