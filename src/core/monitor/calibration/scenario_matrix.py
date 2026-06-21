"""Matriz de escenarios de calibración (SPAN, transiciones, AUTO/MANUAL)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

from core.monitor.monitor_freq_span_logic import patch_manual_span
from core.monitor.monitor_bw_sweep_logic import (
    patch_fft_auto,
    patch_fft_manual,
    patch_rbw_auto,
    patch_rbw_hz,
    patch_rbw_manual,
)
from core.monitor.spectrum_params import SpectrumParams
from core.rf.bridge import prepare_params_for_capture

# Cruces críticos HackRF: BW instantáneo 20 MHz; barrido (hackrf_sweep) si SPAN > 20 MHz.
SPAN_GRID_HZ = (
    1_000_000.0,
    2_000_000.0,
    5_000_000.0,
    10_000_000.0,
    15_000_000.0,
    18_000_000.0,
    19_000_000.0,
    19_500_000.0,
    20_000_000.0,
    20_500_000.0,
    21_000_000.0,
    25_000_000.0,
    30_000_000.0,
    31_000_000.0,
    40_000_000.0,
    80_000_000.0,
    100_000_000.0,
)

SPAN_TRANSITIONS = (
    (19_000_000.0, 21_000_000.0),
    (21_000_000.0, 19_000_000.0),
    (20_000_000.0, 50_000_000.0),
    (50_000_000.0, 10_000_000.0),
    (18_000_000.0, 25_000_000.0),
    (25_000_000.0, 18_000_000.0),
)


@dataclass(frozen=True)
class CalibrationScenario:
    id: str
    label: str
    span_hz: float
    capture_mode_expected: str | None = None


def _base_params(**overrides) -> SpectrumParams:
    params = SpectrumParams(
        operating_mode="spectrum",
        center_freq_hz=500_000_000.0,
        manual_span_hz=10_000_000.0,
        span_mode="manual",
        source_id="hackrf",
        capture_mode="iq",
        fft_auto=True,
        rbw_auto=True,
        sweep_auto=True,
    )
    for key, value in overrides.items():
        setattr(params, key, value)
    return params


def _expected_mode(span_hz: float) -> str:
    from core.rf.acquisition.iq_stitch_plan import prefers_hackrf_sweep

    return "sweep" if prefers_hackrf_sweep(span_hz, 20_000_000.0) else "iq"


def iter_span_scenarios() -> Iterator[CalibrationScenario]:
    for span in SPAN_GRID_HZ:
        yield CalibrationScenario(
            id=f"span_{int(span/1e6)}m",
            label=f"SPAN {span/1e6:.1f} MHz AUTO",
            span_hz=span,
            capture_mode_expected=_expected_mode(span),
        )


def iter_transition_scenarios() -> Iterator[CalibrationScenario]:
    for idx, (a, b) in enumerate(SPAN_TRANSITIONS):
        yield CalibrationScenario(
            id=f"trans_{idx}_{int(a/1e6)}_{int(b/1e6)}",
            label=f"Transición {a/1e6:.0f}→{b/1e6:.0f} MHz",
            span_hz=b,
            capture_mode_expected=_expected_mode(b),
        )


def iter_flag_scenarios() -> Iterator[tuple[str, str, SpectrumParams]]:
    """Escenarios RBW/FFT AUTO/MANUAL en IQ y barrido."""
    iq_span = 10_000_000.0
    sweep_span = 21_000_000.0

    cases = (
        ("iq_all_auto", "IQ todo AUTO", iq_span, {}),
        ("iq_manual_fft", "IQ FFT manual 4096", iq_span, {"fft_auto": False, "fft_size": 4096}),
        ("iq_manual_rbw", "IQ RBW manual 50 kHz", iq_span, {"rbw_auto": False, "fft_auto": False, "rbw_hz": 50_000.0}),
        ("sweep_all_auto", "Barrido todo AUTO", sweep_span, {}),
        ("sweep_manual_rbw", "Barrido RBW manual 300 kHz", sweep_span, {"rbw_auto": False, "rbw_hz": 300_000.0}),
        ("sweep_manual_fft", "Barrido FFT manual 1024", sweep_span, {"fft_auto": False, "fft_size": 1024}),
    )
    for sid, label, span, flags in cases:
        params = _base_params()
        params = patch_manual_span(params, span)
        for key, val in flags.items():
            setattr(params, key, val)
        if flags.get("rbw_auto") is False and span <= 20e6:
            params = patch_rbw_hz(params, flags.get("rbw_hz", params.rbw_hz))
        elif flags.get("fft_auto") is False:
            params = patch_fft_manual(params)
        elif flags.get("rbw_auto") is False and span > 20e6:
            params = patch_rbw_manual(params)
        yield sid, label, params


def build_params_for_scenario(scenario: CalibrationScenario) -> SpectrumParams:
    from core.monitor.calibration.capture_transition import reset_capture_profiles

    reset_capture_profiles()
    params = _base_params()
    if scenario.id.startswith("trans_"):
        parts = scenario.id.split("_")
        prev_span = float(parts[2]) * 1_000_000.0
        params = patch_manual_span(params, prev_span)
        params = prepare_params_for_capture(params)
    params = patch_manual_span(params, scenario.span_hz)
    return prepare_params_for_capture(params)


def all_scenario_ids() -> list[str]:
    ids = [s.id for s in iter_span_scenarios()]
    ids += [s.id for s in iter_transition_scenarios()]
    ids += [sid for sid, _, _ in iter_flag_scenarios()]
    return ids
