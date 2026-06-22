"""Traza fina IQ: remuestreo, detector y FFT AUTO."""
import numpy as np

from core.monitor.monitor_bw_profile import iq_trace_sharp_active, plot_resample_method
from core.monitor.monitor_bw_sweep_logic import patch_iq_trace_sharp
from core.monitor.spectrum_params import SpectrumParams
from core.monitor.spectrum_plot_mapping import resample_power_to_grid
from core.rf.analysis.pipeline import apply_detector
from core.rf.display import pick_auto_fft_size
from core.rf.types import AcquisitionMode


def test_apply_detector_does_not_smooth_iq_bins():
    power = np.array([-80.0, -40.0, -80.0], dtype=float)
    out = apply_detector(power, "rms", acquisition_mode=AcquisitionMode.IQ_STREAM)
    assert np.allclose(out, power)


def test_apply_detector_smooths_sweep_rms():
    power = np.array([-80.0, -40.0, -80.0], dtype=float)
    out = apply_detector(power, "rms", acquisition_mode=AcquisitionMode.SWEEP)
    assert not np.allclose(out, power)
    assert -80.0 < float(out[1]) < -40.0


def test_resample_peak_keeps_narrow_spike():
    freqs = np.linspace(100e6, 102e6, 256)
    power = np.full(256, -90.0)
    power[128] = -30.0
    linear = resample_power_to_grid(
        freqs, power, start_hz=freqs[0], stop_hz=freqs[-1], num_columns=64, method="linear"
    )
    peak = resample_power_to_grid(
        freqs, power, start_hz=freqs[0], stop_hz=freqs[-1], num_columns=64, method="peak"
    )
    assert float(np.max(peak)) >= float(np.max(linear))
    assert float(np.max(peak)) >= -31.0


def test_sharp_mode_uses_peak_resample_and_larger_fft():
    base = SpectrumParams(
        capture_mode="iq",
        sample_rate_hz=18_000_000.0,
        span_hz=18_000_000.0,
        fft_auto=True,
    )
    assert pick_auto_fft_size(base) == 1024
    assert plot_resample_method(base) == "linear"
    sharp = patch_iq_trace_sharp(base, enabled=True)
    assert sharp.iq_trace_sharp is True
    assert sharp.detector == "peak"
    assert sharp.trace_smooth_auto is False
    assert sharp.trace_smooth_bins == 3
    assert pick_auto_fft_size(sharp) == 2048
    assert iq_trace_sharp_active(sharp) is True
    assert plot_resample_method(sharp) == "peak"
