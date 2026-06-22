"""Tests del log de flujo Monitor y reconfigure selectivo."""
import time

import pytest

from core.monitor.monitor_flow_log import (
    DISPLAY_PARAM_KEYS,
    HARDWARE_PARAM_KEYS,
    RADIO_PANEL_PATCH_KEYS,
    RADIO_PANEL_STRUCTURAL_KEYS,
    RADIO_SOFT_PARAM_KEYS,
    changed_param_key_names,
    diff_param_keys,
    is_auto_tune_hw_unchanged,
    is_auto_tune_soft_only_patch,
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


def test_changed_param_key_names_returns_bare_keys():
    prev = SpectrumParams(rf_amp_enable=False, lna_gain_db=16)
    updated = prev.copy()
    updated.rf_amp_enable = True
    names = changed_param_key_names(prev, updated, ("rf_amp_enable", "lna_gain_db"))
    assert names == ["rf_amp_enable"]


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


def test_demod_panel_merge_preserves_live_center_freq():
    """Patrón de _apply_demod_params_from_panel: squelch del panel, FC/audio vivo del controlador."""
    live = SpectrumParams(
        center_freq_hz=87.6e6,
        selected_freq_hz=87.6e6,
        freq_input_mode="channel",
        squelch_db=-50.0,
        audio_enabled=True,
    )
    panel = live.copy()
    panel.center_freq_hz = 87.5e6
    panel.selected_freq_hz = 87.5e6
    panel.freq_input_mode = "frequency"
    panel.squelch_db = -35.0
    panel.audio_enabled = False
    merged = live.copy()
    for key in RADIO_PANEL_PATCH_KEYS:
        setattr(merged, key, getattr(panel, key))
    for key in RADIO_PANEL_STRUCTURAL_KEYS:
        setattr(merged, key, getattr(live, key))
    assert merged.center_freq_hz == pytest.approx(87.6e6)
    assert merged.freq_input_mode == "channel"
    assert merged.squelch_db == pytest.approx(-35.0)
    assert merged.audio_enabled is True


def test_demod_snap_and_freq_readout_are_soft_keys() -> None:
    assert "demod_snap_interval" in RADIO_SOFT_PARAM_KEYS
    assert "freq_readout" in RADIO_SOFT_PARAM_KEYS


def test_demod_panel_merge_only_changed_keys() -> None:
    """Patrón merge: solo claves que difieren; el parche soft solo envía RDS."""
    live = SpectrumParams(
        demod_wfm_rds=False,
        demod_snap_interval=100_000.0,
        demod_bandwidth_hz=200_000.0,
    )
    panel = live.copy()
    panel.demod_snap_interval = 25_000.0
    panel.demod_wfm_rds = True
    changed = changed_param_key_names(live, panel, RADIO_PANEL_PATCH_KEYS)
    assert "demod_wfm_rds" in changed
    assert "demod_snap_interval" in changed
    patch = {"demod_wfm_rds": True}
    merged = live.copy()
    for key, value in patch.items():
        setattr(merged, key, value)
    assert merged.demod_wfm_rds is True
    assert merged.demod_snap_interval == 100_000.0


def test_soft_patch_rds_only_does_not_touch_gains() -> None:
    live = SpectrumParams(lna_gain_db=40, demod_wfm_rds=False)
    patch = {"demod_wfm_rds": True}
    merged = live.copy()
    for key, value in patch.items():
        setattr(merged, key, value)
    assert merged.demod_wfm_rds is True
    assert merged.lna_gain_db == 40


def test_auto_tune_snap_change_is_soft_only_patch() -> None:
    prev = SpectrumParams(
        center_freq_hz=92e6,
        sample_rate_hz=2e6,
        span_hz=2e6,
        manual_span_hz=2e6,
        demod_snap_interval=25_000.0,
        freq_readout="fc",
        lna_gain_db=8,
    )
    tuned = prev.copy()
    tuned.demod_snap_interval = 100_000.0
    tuned.freq_readout = "f"
    tuned.lna_gain_db = 40
    assert is_auto_tune_soft_only_patch(prev, tuned)
    assert is_auto_tune_hw_unchanged(prev, tuned)
