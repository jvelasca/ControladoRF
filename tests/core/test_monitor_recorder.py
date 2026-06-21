"""Tests grabador Monitor."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np

from core.monitor.monitor_recorder import (
    MonitorRecorder,
    build_recording_filename,
    resolve_recording_path,
)
from core.monitor.spectrum_params import SpectrumParams


def test_build_recording_filename_baseband() -> None:
    params = SpectrumParams(
        vfo_freq_hz=92_200_000.0,
        sample_rate_hz=4_000_000.0,
        demod_mode="wfm",
    )
    when = datetime(2026, 6, 12, 15, 30, 0)
    name = build_recording_filename(params, "baseband", when=when)
    assert name.startswith("bb_92.200MHz_")
    assert name.endswith(".cf32")


def test_build_recording_filename_audio() -> None:
    params = SpectrumParams(vfo_freq_hz=100_000_000.0, demod_mode="nfm")
    when = datetime(2026, 6, 12, 15, 30, 0)
    name = build_recording_filename(params, "audio", when=when)
    assert "audio_100.000MHz_nfm" in name
    assert name.endswith(".wav")


def test_recorder_writes_cf32_and_wav(tmp_path: Path) -> None:
    bb_path = tmp_path / "test.cf32"
    recorder = MonitorRecorder()
    ok, _err = recorder.start(bb_path, "baseband")
    assert ok
    iq = np.array([1 + 1j, -1 + 0.5j], dtype=np.complex64)
    recorder.write_iq(iq)
    saved = recorder.stop()
    assert saved == bb_path
    assert bb_path.stat().st_size == iq.size * 8

    wav_path = tmp_path / "test.wav"
    ok, _err = recorder.start(wav_path, "audio")
    assert ok
    pcm = np.array([0.0, 0.5, -0.25], dtype=np.float32)
    recorder.write_pcm(pcm)
    saved = recorder.stop()
    assert saved == wav_path
    assert wav_path.stat().st_size > 44


def test_resolve_recording_path_uses_custom_name(tmp_path: Path) -> None:
    params = SpectrumParams(
        recorder_directory=str(tmp_path),
        recorder_filename="custom.wav",
        recorder_mode="audio",
    )
    path = resolve_recording_path(params, "audio")
    assert path.parent == tmp_path
    assert path.name == "custom.wav"
