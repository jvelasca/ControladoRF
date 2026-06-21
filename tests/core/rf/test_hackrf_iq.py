"""Tests FFT IQ y captura HackRF v2 (sin hardware)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np

from core.rf.devices.hackrf.device import HackRfDevice
from core.rf.spectrum_fft import compute_iq_spectrum_frame
from core.rf.types import (
    AcquisitionMode,
    AcquisitionPlan,
    FrequencyWindow,
    IqStreamPlan,
    RfFrontendConfig,
    RfHardwareConfig,
    RxGainConfig,
)


def test_compute_iq_spectrum_frame_shape():
    tone = np.exp(2j * np.pi * 0.05 * np.arange(1024))
    frame = compute_iq_spectrum_frame(
        tone.astype(np.complex64),
        center_freq_hz=100e6,
        sample_rate_hz=10e6,
        rx_gain=RxGainConfig(lna_db=32, vga_db=40),
    )
    assert frame.freqs_hz.shape == (1024,)
    assert frame.power_db.shape == (1024,)
    assert frame.metadata.acquisition_mode is AcquisitionMode.IQ_STREAM
    assert abs(frame.freqs_hz[0] - (100e6 - 5e6)) < 50_000


def test_hackrf_capture_iq_spectrum_mocked():
    device = HackRfDevice()
    device.open()
    hw = RfHardwareConfig(
        center_freq_hz=98e6,
        frontend=RfFrontendConfig(),
        rx_gain=RxGainConfig(lna_db=32, vga_db=40),
    )
    device.configure(hw, window_center_hz=98e6)

    iq_plan = IqStreamPlan(center_freq_hz=98e6, sample_rate_hz=10e6, fft_size=1024)
    acq = AcquisitionPlan(
        mode=AcquisitionMode.IQ_STREAM,
        window=FrequencyWindow.from_center_span(98e6, 8e6),
        iq=iq_plan,
    )

    fake_block = (np.random.randint(-127, 127, size=1024 * 2, dtype=np.int8)).tobytes()
    mock_stream = MagicMock()
    mock_stream.ensure_stream = MagicMock()
    mock_stream.read_iq_block = MagicMock(return_value=fake_block)
    device._iq_stream = mock_stream

    frame = device.capture_iq_spectrum(acq)
    assert frame.freqs_hz.size == 1024
    mock_stream.ensure_stream.assert_called_once()
    mock_stream.read_iq_block.assert_called_once_with(1024)


def test_hackrf_capture_sweep_stops_iq_stream():
    device = HackRfDevice()
    device.open()
    mock_stream = MagicMock()
    device._iq_stream = mock_stream

    from core.rf.types import SweepPlan

    sweep = SweepPlan(
        start_hz=88e6,
        stop_hz=108e6,
        bin_width_hz=100_000,
        lna_db=32,
        vga_db=40,
        rf_amp_enable=False,
        bias_tee_enable=False,
    )
    legacy_frame = MagicMock()
    legacy_frame.freqs_hz = np.linspace(88e6, 108e6, 801)
    legacy_frame.power_db = np.full(801, -80.0)

    with patch("core.monitor.hackrf_sweep_source.run_hackrf_sweep", return_value=legacy_frame):
        frame = device.capture_sweep(sweep)

    mock_stream.stop.assert_called_once()
    assert frame.freqs_hz.size == 801
