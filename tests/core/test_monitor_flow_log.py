"""Tests del log de flujo Monitor y reconfigure selectivo."""
import time

from core.monitor.monitor_flow_log import (
    DISPLAY_PARAM_KEYS,
    HARDWARE_PARAM_KEYS,
    diff_param_keys,
    param_value_changed,
)
from core.monitor.spectrum_engine import SpectrumEngine
from core.monitor.spectrum_params import SpectrumParams


def test_param_value_changed_freq_and_db():
    assert param_value_changed("center_freq_hz", 100_000_000.0, 100_000_000.4) is False
    assert param_value_changed("center_freq_hz", 100_000_000.0, 100_000_001.0) is True
    assert param_value_changed("ref_level_dbm", -20.0, -20.04) is False
    assert param_value_changed("ref_level_dbm", -20.0, -20.1) is True
    assert param_value_changed("rf_amp_enable", False, True) is True


def test_diff_param_keys_separates_display_and_hardware():
    prev = SpectrumParams(ref_level_dbm=-30.0, lna_gain_db=24)
    updated = prev.copy()
    updated.ref_level_dbm = -40.0
    updated.lna_gain_db = 32
    disp = diff_param_keys(prev, updated, DISPLAY_PARAM_KEYS)
    hw = diff_param_keys(prev, updated, HARDWARE_PARAM_KEYS)
    assert any("ref_level_dbm" in item for item in disp)
    assert any("lna_gain_db" in item for item in hw)
    assert not any("lna_gain_db" in item for item in disp)


def test_set_params_display_only_does_not_schedule_reconfigure():
    engine = SpectrumEngine()
    ok, _ = engine.start()
    assert ok
    time.sleep(0.15)
    assert engine.is_running
    reconfigure_at = engine._reconfigure_at
    params = engine.params
    engine.set_params(ref_level_dbm=params.ref_level_dbm - 5.0, ref_range_db=params.ref_range_db + 2.0)
    assert engine._reconfigure_at == reconfigure_at
    engine.stop()


def test_set_params_fft_size_change_does_not_schedule_reconfigure():
    engine = SpectrumEngine()
    ok, _ = engine.start()
    assert ok
    time.sleep(0.15)
    reconfigure_at = engine._reconfigure_at
    params = engine.params
    new_fft = 8192 if params.fft_size != 8192 else 4096
    engine.set_params(fft_size=new_fft, rbw_hz=100.0, rbw_auto=False)
    assert engine._reconfigure_at == reconfigure_at
    engine.stop()


def test_patch_rbw_hz_does_not_schedule_reconfigure():
    from core.monitor.monitor_bw_sweep_logic import patch_rbw_hz, sync_analysis_chain

    engine = SpectrumEngine()
    ok, _ = engine.start()
    assert ok
    time.sleep(0.15)
    reconfigure_at = engine._reconfigure_at
    updated = patch_rbw_hz(engine.params, 100.0)
    sync_analysis_chain(updated)
    engine.set_params(
        fft_size=updated.fft_size,
        rbw_hz=updated.rbw_hz,
        rbw_auto=updated.rbw_auto,
        trace_smooth_auto=updated.trace_smooth_auto,
        trace_smooth_bins=updated.trace_smooth_bins,
        sweep_time_ms=updated.sweep_time_ms,
    )
    assert engine._reconfigure_at == reconfigure_at
    engine.stop()


def test_set_params_hardware_change_schedules_reconfigure():
    engine = SpectrumEngine()
    ok, _ = engine.start()
    assert ok
    time.sleep(0.15)
    params = engine.params
    reconfigure_at = engine._reconfigure_at
    engine.set_params(lna_gain_db=params.lna_gain_db + 8)
    assert engine._reconfigure_at >= reconfigure_at
    engine.stop()
