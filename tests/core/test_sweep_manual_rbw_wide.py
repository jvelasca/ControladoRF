"""RBW manual en barrido amplio (>20 MHz)."""
from core.monitor.monitor_bw_sweep_logic import patch_rbw_hz, sync_analysis_chain
from core.monitor.spectrum_params import SpectrumParams
from core.rf.acquisition.policy import DefaultAcquisitionPolicy
from core.rf.bridge import operator_intent_from_params, prepare_params_for_capture


def test_sweep_manual_rbw_preserved_above_20mhz():
    params = SpectrumParams(
        capture_mode="sweep",
        span_hz=25_000_000.0,
        manual_span_hz=25_000_000.0,
        center_freq_hz=98_000_000.0,
        operating_mode="spectrum",
        source_id="hackrf",
        rbw_auto=False,
        rbw_hz=300_000.0,
    )
    updated = patch_rbw_hz(params, 300_000.0)
    sync_analysis_chain(updated)
    assert updated.rbw_auto is False
    assert updated.rbw_hz == 300_000.0

    prepared = prepare_params_for_capture(updated)
    assert prepared.rbw_auto is False
    assert prepared.rbw_hz == 300_000.0

    intent = operator_intent_from_params(prepared)
    plan = DefaultAcquisitionPolicy().plan(intent, device_id="hackrf")
    assert plan.sweep is not None
    assert plan.sweep.bin_width_hz == 300_000.0
