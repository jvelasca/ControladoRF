"""Tests motor RF v2."""
from __future__ import annotations

import numpy as np

from core.rf.acquisition.policy import DefaultAcquisitionPolicy
from core.rf.analysis.policy import DefaultAnalysisPolicy
from core.rf.registry import create_device
from core.rf.session import RfSession
from core.rf.types import (
    FrequencyWindow,
    OperatingMode,
    OperatorIntent,
    RfHardwareConfig,
)


def test_frequency_window_from_center_span():
    w = FrequencyWindow.from_center_span(98e6, 20e6)
    assert abs(w.start_hz - 88e6) < 1.0
    assert abs(w.stop_hz - 108e6) < 1.0


def test_acquisition_fm_20mhz_prefers_iq():
    policy = DefaultAcquisitionPolicy()
    intent = OperatorIntent(
        window=FrequencyWindow.from_center_span(98e6, 20e6),
        operating_mode=OperatingMode.SPECTRUM,
        source_id="hackrf",
    )
    plan = policy.plan(intent, device_id="hackrf")
    assert plan.mode.value == "iq_stream"
    assert plan.iq is not None
    assert plan.iq.sample_rate_hz >= 15_000_000.0
    assert plan.reason == "iq_within_instant_bw"


def test_acquisition_wide_span_uses_sweep():
    policy = DefaultAcquisitionPolicy()
    intent = OperatorIntent(
        window=FrequencyWindow.from_center_span(500e6, 80e6),
        operating_mode=OperatingMode.SPECTRUM,
        source_id="hackrf",
    )
    plan = policy.plan(intent, device_id="hackrf")
    assert plan.mode.value == "sweep"
    assert plan.sweep is not None


def test_mock_session_capture_once():
    session = RfSession()
    session.attach_source("mock")
    session.open()
    session.set_intent(
        OperatorIntent(
            window=FrequencyWindow.from_center_span(100e6, 10e6),
            source_id="mock",
        )
    )
    display = session.capture_once()
    assert display.frame.freqs_hz.size >= 64
    assert display.frame.power_db.shape == display.frame.freqs_hz.shape
    tel = session.telemetry()
    assert tel.device_id == "mock"
    assert tel.frame_bins > 0


def test_create_device_hackrf():
    dev = create_device("hackrf_0")
    assert dev.device_id == "hackrf"


def test_analysis_policy_sweep_rbw_stable():
    policy = DefaultAnalysisPolicy()
    from core.rf.types import AcquisitionMode, AcquisitionPlan, SweepPlan

    acq = AcquisitionPlan(
        mode=AcquisitionMode.SWEEP,
        window=FrequencyWindow.from_center_span(98e6, 19e6),
        sweep=SweepPlan(
            start_hz=88e6,
            stop_hz=107e6,
            bin_width_hz=100_000,
            lna_db=32,
            vga_db=40,
            rf_amp_enable=False,
            bias_tee_enable=False,
        ),
    )
    intent = OperatorIntent(window=acq.window, source_id="hackrf")
    a19 = policy.resolve(intent, acq)
    acq21 = AcquisitionPlan(
        mode=AcquisitionMode.SWEEP,
        window=FrequencyWindow.from_center_span(98e6, 21e6),
        sweep=SweepPlan(
            start_hz=87e6,
            stop_hz=109e6,
            bin_width_hz=100_000,
            lna_db=32,
            vga_db=40,
            rf_amp_enable=False,
            bias_tee_enable=False,
        ),
    )
    intent21 = OperatorIntent(window=acq21.window, source_id="hackrf")
    a21 = policy.resolve(intent21, acq21)
    assert a19.rbw_hz == a21.rbw_hz
