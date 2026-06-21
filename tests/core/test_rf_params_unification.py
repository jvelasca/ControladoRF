"""Params unificados — runner, histéresis, patch SPAN."""
from core.monitor.monitor_flow_log import RF_GAIN_PARAM_KEYS
from core.monitor.monitor_mode_profile import refresh_capture_and_span_limits
from core.monitor.spectrum_params import SpectrumParams
from core.rf.bridge import sync_params_capture_mode_from_v2
from gui.monitor.monitor_rf_view_model import MonitorRfViewModel
from core.rf.runner import RfSpectrumRunner


def test_view_model_uses_runner_session_only():
    runner = RfSpectrumRunner()
    vm = MonitorRfViewModel()
    vm.bind_runner(runner)
    assert vm.session is runner.session


def test_sync_capture_mode_sweep_above_instant_bw():
    """SPAN > 20 MHz → barrido hackrf_sweep (lapso ancho correcto)."""
    params = SpectrumParams(
        operating_mode="spectrum",
        center_freq_hz=500_000_000.0,
        manual_span_hz=50_000_000.0,
        span_mode="manual",
        capture_mode="iq",
        source_id="hackrf",
    )
    refresh_capture_and_span_limits(params)
    assert params.capture_mode == "sweep"

    params.manual_span_hz = 21_000_000.0
    refresh_capture_and_span_limits(params)
    assert params.capture_mode == "sweep"

    params.manual_span_hz = 20_000_000.0
    refresh_capture_and_span_limits(params)
    assert params.capture_mode == "iq"


def test_spectrum_engine_skips_hw_reconfigure_when_demod_auxiliary():
    from core.monitor.spectrum_engine import SpectrumEngine

    engine = SpectrumEngine()
    engine._demod_auxiliary = True
    engine._running = True
    engine._reconfigure_at = 0.0
    engine.set_params(request_hw_reconfigure=True, lna_gain_db=16)
    assert engine._reconfigure_at == 0.0


def test_rf_gain_keys_cover_preamp():
    assert "rf_amp_enable" in RF_GAIN_PARAM_KEYS
