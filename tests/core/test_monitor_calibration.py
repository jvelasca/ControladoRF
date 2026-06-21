"""Tests calibracion cadena analizador — IQ compuesto vs barrido."""
from __future__ import annotations

import pytest

from core.monitor.calibration.capture_transition import reset_capture_profiles
from core.monitor.calibration.harness import CalibrationHarness
from core.monitor.calibration.scenario_matrix import build_params_for_scenario, iter_span_scenarios
from core.monitor.monitor_freq_span_logic import patch_manual_span
from core.monitor.spectrum_params import SpectrumParams
from core.rf.bridge import prepare_params_for_capture


def _spectrum_params(span_hz: float, *, capture_mode: str = "iq") -> SpectrumParams:
    params = SpectrumParams(
        operating_mode="spectrum",
        center_freq_hz=500_000_000.0,
        manual_span_hz=span_hz,
        span_mode="manual",
        source_id="hackrf",
        capture_mode=capture_mode,
        fft_auto=True,
        rbw_auto=True,
    )
    return params


def test_span_21mhz_uses_sweep() -> None:
    reset_capture_profiles()
    params = _spectrum_params(21_000_000.0)
    out = prepare_params_for_capture(params)
    assert out.capture_mode == "sweep"
    assert abs(out.manual_span_hz - 21_000_000.0) < 1.0


def test_span_19mhz_stays_iq() -> None:
    reset_capture_profiles()
    params = _spectrum_params(19_000_000.0)
    out = prepare_params_for_capture(params)
    assert out.capture_mode == "iq"


def test_span_20mhz_boundary_iq() -> None:
    reset_capture_profiles()
    params = _spectrum_params(20_000_000.0)
    out = prepare_params_for_capture(params)
    assert out.capture_mode == "iq"
    assert abs(out.sample_rate_hz - 20_000_000.0) < 100_000.0


def test_span_80mhz_uses_sweep() -> None:
    reset_capture_profiles()
    params = _spectrum_params(80_000_000.0)
    out = prepare_params_for_capture(params)
    assert out.capture_mode == "sweep"


def test_transition_19_to_21_mhz_uses_sweep() -> None:
    reset_capture_profiles()
    params = _spectrum_params(19_000_000.0)
    params = prepare_params_for_capture(params)
    assert params.capture_mode == "iq"
    params = patch_manual_span(params, 21_000_000.0)
    params = prepare_params_for_capture(params)
    assert params.capture_mode == "sweep"


def test_manual_fft_preserved_across_stitch_span() -> None:
    reset_capture_profiles()
    iq = _spectrum_params(10_000_000.0)
    iq.fft_size = 4096
    iq.fft_auto = False
    iq.rbw_auto = False
    iq = prepare_params_for_capture(iq)
    assert iq.fft_size == 4096

    wide = patch_manual_span(iq, 31_000_000.0)
    wide = prepare_params_for_capture(wide)
    assert wide.capture_mode == "sweep"
    assert wide.fft_size == 4096

    sweep = patch_manual_span(wide, 80_000_000.0)
    sweep = prepare_params_for_capture(sweep)
    assert sweep.capture_mode == "sweep"
    assert sweep.fft_size == 4096


def test_calibration_matrix_all_pass() -> None:
    harness = CalibrationHarness()
    report = harness.run_matrix(include_flags=True)
    failed = [r for r in report.results if not r.passed]
    assert report.ok, f"Fallos: {[f'{r.scenario_id}: {r.errors}' for r in failed]}"


@pytest.mark.parametrize(
    "span_mhz,expected",
    [
        (10.0, "iq"),
        (20.0, "iq"),
        (21.0, "sweep"),
        (40.0, "sweep"),
        (80.0, "sweep"),
    ],
)
def test_span_grid_expected_mode(span_mhz: float, expected: str) -> None:
    reset_capture_profiles()
    for scenario in iter_span_scenarios():
        if abs(scenario.span_hz - span_mhz * 1e6) < 1.0:
            params = build_params_for_scenario(scenario)
            assert params.capture_mode == expected
            return
    pytest.fail(f"Escenario span {span_mhz} no encontrado")


def test_wizard_checklist_transition_backend() -> None:
    from core.monitor.calibration.calibration_checklist import (
        apply_step,
        evaluate_step_backend,
        step_by_id,
    )

    step = step_by_id("transition_19_21")
    assert step is not None
    base = SpectrumParams(
        operating_mode="spectrum",
        center_freq_hz=500e6,
        source_id="hackrf",
        span_mode="manual",
    )
    prepared = apply_step(step, base)
    report = evaluate_step_backend(step, prepared)
    assert report.capture_mode == "sweep"
    assert report.passed
