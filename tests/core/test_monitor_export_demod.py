"""Tests rutas exportación Monitor y demodulación SDR."""
from __future__ import annotations

import numpy as np

from core.monitor.demod_branch import DemodBranch
from core.monitor.demod_dsp import demod_iq_to_audio, iq_samples_for_demod
from core.monitor.iq_constants import IQ_DEMOD_MAX_SAMPLES
from core.monitor.monitor_export_paths import (
    EXPORT_PNG_SPECTRUM,
    EXPORT_TRACE_CSV,
    configure_monitor_export_paths,
    export_directory,
    remember_save_path,
    resolve_save_path,
)
from core.monitor.spectrum_params import SpectrumParams


def test_export_paths_remember_per_type(tmp_path) -> None:
    stored: dict = {}

    def get_config():
        return stored

    def set_config(cfg):
        stored.clear()
        stored.update(cfg)

    configure_monitor_export_paths(get_config, set_config, default_dir=lambda: str(tmp_path))
    csv_dir = tmp_path / "trazas"
    png_dir = tmp_path / "capturas"
    csv_dir.mkdir()
    png_dir.mkdir()
    remember_save_path(EXPORT_TRACE_CSV, str(csv_dir / "a.csv"))
    remember_save_path(EXPORT_PNG_SPECTRUM, str(png_dir / "b.png"))
    assert export_directory(EXPORT_TRACE_CSV) == csv_dir
    assert export_directory(EXPORT_PNG_SPECTRUM) == png_dir
    suggested = resolve_save_path(EXPORT_TRACE_CSV, "monitor_trace_test.csv")
    assert suggested.endswith("monitor_trace_test.csv")
    assert export_directory(EXPORT_TRACE_CSV).as_posix() in suggested.replace("\\", "/")


def test_demod_fm_produces_level_and_waveform() -> None:
    rate = 2_000_000.0
    n = 8192
    t = np.arange(n) / rate
    offset_hz = 25_000.0
    tone = np.exp(2j * np.pi * offset_hz * t)
    audio = np.sin(2 * np.pi * 800.0 * t)
    phase_mod = 2.0 * np.pi * 8_000.0 * np.cumsum(audio) / rate
    samples = (0.5 * tone * np.exp(1j * phase_mod)).astype(np.complex64)
    params = SpectrumParams(
        center_freq_hz=100_000_000.0,
        vfo_freq_hz=100_025_000.0,
        demod_mode="fm",
        squelch_db=-80.0,
        operating_mode="sdr",
        audio_enabled=True,
    )
    result = demod_iq_to_audio(samples, params, sample_rate_hz=rate)
    assert result.waveform.size > 0
    assert result.scope.size > 0
    assert result.pcm.size > 0
    assert result.level_dbfs > -80.0
    assert result.peak_dbfs > -80.0
    assert result.squelch_open is True

    iq_n = iq_samples_for_demod(params, fft_size=2048)
    assert iq_n >= 2048
    t_long = np.arange(iq_n) / rate
    tone_long = np.exp(2j * np.pi * offset_hz * t_long)
    audio_long = np.sin(2 * np.pi * 800.0 * t_long)
    phase_long = 2.0 * np.pi * 8_000.0 * np.cumsum(audio_long) / rate
    long_block = (0.5 * tone_long * np.exp(1j * phase_long)).astype(np.complex64)
    long_result = demod_iq_to_audio(long_block, params, sample_rate_hz=rate)
    assert len(long_result.pcm) >= int(48_000 / 50)


def test_demod_branch_mock_path() -> None:
    branch = DemodBranch()
    rate = 2_000_000.0
    n = 8192
    t = np.arange(n) / rate
    offset_hz = 25_000.0
    tone = np.exp(2j * np.pi * offset_hz * t)
    audio = np.sin(2 * np.pi * 800.0 * t)
    phase_mod = 2.0 * np.pi * 8_000.0 * np.cumsum(audio) / rate
    samples = (0.5 * tone * np.exp(1j * phase_mod)).astype(np.complex64)
    params = SpectrumParams(
        center_freq_hz=100_000_000.0,
        vfo_freq_hz=100_025_000.0,
        sample_rate_hz=rate,
        demod_mode="fm",
        operating_mode="sdr",
        audio_enabled=True,
        squelch_db=-80.0,
    )
    branch.process_iq(samples, params, sample_rate_hz=rate)
    for _ in range(12):
        branch.process_iq(samples, params, sample_rate_hz=rate)
    state = branch.last_state
    assert state is not None
    assert state.squelch_open
    assert state.waveform.size > 0
    assert state.scope.size > 0
    assert state.level_dbfs > -80.0
    assert state.vu_dbfs > -80.0
    assert state.pcm.size > 0
