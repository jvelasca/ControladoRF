"""Tests squelch en demodulación."""
from core.monitor.demod_dsp import DemodStreamState, _update_squelch


def test_squelch_closes_below_threshold():
    state = DemodStreamState()
    state.squelch_open = True
    _update_squelch(state, -52.0, -40.0)
    assert state.squelch_open is False


def test_squelch_opens_above_threshold():
    state = DemodStreamState()
    _update_squelch(state, -35.0, -81.0)
    assert state.squelch_open is True


def test_squelch_hysteresis():
    state = DemodStreamState()
    _update_squelch(state, -40.0, -45.0)
    assert state.squelch_open is True
    _update_squelch(state, -42.0, -45.0)
    assert state.squelch_open is True
    _update_squelch(state, -52.0, -45.0)
    assert state.squelch_open is False


def test_squelch_respects_threshold_while_open():
    state = DemodStreamState()
    _update_squelch(state, -25.0, -40.0)
    assert state.squelch_open is True
    _update_squelch(state, -25.0, -20.0)
    assert state.squelch_open is False


def test_squelch_disabled_always_open():
    state = DemodStreamState()
    state.squelch_open = False
    assert _update_squelch(state, -90.0, -40.0, enabled=False) is True


def test_squelch_minimum_threshold_stays_open():
    state = DemodStreamState()
    state.squelch_open = False
    state.squelch_noise_floor_dbfs = -50.0
    for level in (-90.0, -60.0, -30.0):
        assert _update_squelch(state, level, -120.0) is True


def test_squelch_passes_audio_disabled():
    from core.monitor.demod_dsp import squelch_passes_audio

    assert squelch_passes_audio(squelch_enabled=False, squelch_db=-40.0, squelch_open=False)
    assert squelch_passes_audio(squelch_enabled=True, squelch_db=-120.0, squelch_open=False)
    assert not squelch_passes_audio(squelch_enabled=True, squelch_db=-40.0, squelch_open=False)
    assert squelch_passes_audio(squelch_enabled=True, squelch_db=-40.0, squelch_open=True)


def test_squelch_low_threshold_opens_after_strong_signal():
    state = DemodStreamState()
    _update_squelch(state, -25.0, -50.0)
    assert state.squelch_open is True
    assert _update_squelch(state, -25.0, -120.0) is True
