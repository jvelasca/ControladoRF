"""Tests squelch en demodulación."""
from core.monitor.demod_dsp import DemodStreamState, _update_squelch


def test_squelch_closes_below_threshold():
    state = DemodStreamState()
    state.squelch_open = True
    _update_squelch(state, -52.0, -40.0)
    assert state.squelch_open is False


def test_squelch_opens_above_threshold():
    state = DemodStreamState()
    for _ in range(20):
        _update_squelch(state, -58.0, -81.0)
    for level in (-35.0, -30.0, -25.0):
        _update_squelch(state, level, -81.0)
    assert state.squelch_open is True


def test_squelch_hysteresis():
    state = DemodStreamState()
    _update_squelch(state, -40.0, -45.0)
    assert state.squelch_open is True
    _update_squelch(state, -42.0, -45.0)
    assert state.squelch_open is True
    _update_squelch(state, -52.0, -45.0)
    assert state.squelch_open is False


def test_squelch_blocks_fm_noise_without_station():
    """Ruido FM de fondo (~-55 dBFS) no abre aunque el umbral absoluto sea bajo."""
    state = DemodStreamState()
    for _ in range(80):
        _update_squelch(state, -55.0, -81.0)
    assert state.squelch_open is False
    assert state.squelch_noise_floor_dbfs > -60.0


def test_squelch_opens_when_signal_above_noise_floor():
    state = DemodStreamState()
    for _ in range(40):
        _update_squelch(state, -58.0, -81.0)
    assert state.squelch_open is False
    for _ in range(10):
        _update_squelch(state, -28.0, -81.0)
    assert state.squelch_open is True


def test_squelch_minimum_threshold_stays_open():
    state = DemodStreamState()
    state.squelch_open = False
    state.squelch_noise_floor_dbfs = -50.0
    for level in (-90.0, -60.0, -30.0):
        assert _update_squelch(state, level, -120.0) is True


def test_squelch_low_threshold_opens_after_strong_signal():
    state = DemodStreamState()
    for _ in range(5):
        _update_squelch(state, -25.0, -50.0)
    assert state.squelch_open is True
    assert _update_squelch(state, -25.0, -120.0) is True
