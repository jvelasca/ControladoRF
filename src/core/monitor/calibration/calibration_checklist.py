"""Checklist guiada de calibración — cadena señal → procesado → visualización."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from core.monitor.monitor_bw_sweep_logic import (
    patch_fft_manual,
    patch_rbw_hz,
)
from core.monitor.monitor_freq_span_logic import patch_manual_span
from core.monitor.monitor_operating_mode import MonitorOperatingMode
from core.monitor.spectrum_params import SpectrumParams
from core.rf.bridge import prepare_params_for_capture


@dataclass(frozen=True)
class CalibrationStepDef:
    """Un paso de la hoja de calibración interactiva."""

    id: str
    phase_key: str
    title_key: str
    body_key: str
    observe_key: str
    apply_fn: Callable[[SpectrumParams], SpectrumParams] = field(repr=False)
    requires_play: bool = True
    category: str = "chain"  # chain | visual | rf | mode


def _base(params: SpectrumParams) -> SpectrumParams:
    updated = params.copy()
    updated.operating_mode = MonitorOperatingMode.SPECTRUM.value
    updated.source_id = updated.source_id or "hackrf"
    updated.span_mode = "manual"
    updated.fft_auto = True
    updated.rbw_auto = True
    updated.sweep_auto = True
    updated.ref_scale_auto = True
    return updated


def _finish(params: SpectrumParams) -> SpectrumParams:
    return prepare_params_for_capture(params)


def _step_iq_10m(p: SpectrumParams) -> SpectrumParams:
    return _finish(patch_manual_span(_base(p), 10_000_000.0))


def _step_iq_fft_manual(p: SpectrumParams) -> SpectrumParams:
    s = _finish(patch_manual_span(_base(p), 10_000_000.0))
    s.fft_size = 4096
    return _finish(patch_fft_manual(s))


def _step_iq_rbw_manual(p: SpectrumParams) -> SpectrumParams:
    s = _finish(patch_manual_span(_base(p), 10_000_000.0))
    return _finish(patch_rbw_hz(s, 50_000.0))


def _step_iq_20m(p: SpectrumParams) -> SpectrumParams:
    return _finish(patch_manual_span(_base(p), 20_000_000.0))


def _step_sweep_21m(p: SpectrumParams) -> SpectrumParams:
    return _finish(patch_manual_span(_base(p), 21_000_000.0))


def _step_sweep_50m(p: SpectrumParams) -> SpectrumParams:
    return _finish(patch_manual_span(_base(p), 50_000_000.0))


def _step_sweep_rbw_manual(p: SpectrumParams) -> SpectrumParams:
    s = _finish(patch_manual_span(_base(p), 21_000_000.0))
    return _finish(patch_rbw_hz(s, 300_000.0))


def _step_sweep_fft_manual(p: SpectrumParams) -> SpectrumParams:
    s = _finish(patch_manual_span(_base(p), 21_000_000.0))
    s.fft_size = 1024
    return _finish(patch_fft_manual(s))


def _step_hysteresis_18m(p: SpectrumParams) -> SpectrumParams:
    wide = _finish(patch_manual_span(_base(p), 50_000_000.0))
    return _finish(patch_manual_span(wide, 18_000_000.0))


def _step_hysteresis_10m(p: SpectrumParams) -> SpectrumParams:
    return _finish(patch_manual_span(_base(p), 10_000_000.0))


def _step_ref_manual(p: SpectrumParams) -> SpectrumParams:
    s = _finish(patch_manual_span(_base(p), 10_000_000.0))
    s.ref_scale_auto = False
    s.ref_level_dbm = -40.0
    s.ref_range_db = 80.0
    return s


def _step_ref_auto(p: SpectrumParams) -> SpectrumParams:
    s = _finish(patch_manual_span(_base(p), 10_000_000.0))
    s.ref_scale_auto = True
    return s


def _step_gain_lna(p: SpectrumParams) -> SpectrumParams:
    s = _finish(patch_manual_span(_base(p), 10_000_000.0))
    s.lna_gain_db = 16 if s.lna_gain_db >= 24 else 32
    return s


def _step_gain_vga(p: SpectrumParams) -> SpectrumParams:
    s = _finish(patch_manual_span(_base(p), 10_000_000.0))
    s.vga_gain_db = 16 if s.vga_gain_db >= 24 else 32
    return s


def _step_transition_19_21(p: SpectrumParams) -> SpectrumParams:
    mid = _finish(patch_manual_span(_base(p), 19_000_000.0))
    return _finish(patch_manual_span(mid, 21_000_000.0))


def _step_prep_device(p: SpectrumParams) -> SpectrumParams:
    return p.copy()


CALIBRATION_STEPS: tuple[CalibrationStepDef, ...] = (
    CalibrationStepDef(
        "prep_device",
        "cal_phase_prep",
        "cal_step_prep_device_title",
        "cal_step_prep_device_body",
        "cal_step_prep_device_observe",
        requires_play=False,
        apply_fn=_step_prep_device,
        category="visual",
    ),
    CalibrationStepDef(
        "prep_play",
        "cal_phase_prep",
        "cal_step_prep_play_title",
        "cal_step_prep_play_body",
        "cal_step_prep_play_observe",
        requires_play=True,
        apply_fn=_step_prep_device,
        category="visual",
    ),
    CalibrationStepDef(
        "iq_span_10m",
        "cal_phase_iq",
        "cal_step_iq_span_10m_title",
        "cal_step_iq_span_10m_body",
        "cal_step_iq_span_10m_observe",
        apply_fn=_step_iq_10m,
    ),
    CalibrationStepDef(
        "iq_trace_signal",
        "cal_phase_iq",
        "cal_step_iq_trace_title",
        "cal_step_iq_trace_body",
        "cal_step_iq_trace_observe",
        apply_fn=_step_iq_10m,
        category="visual",
    ),
    CalibrationStepDef(
        "iq_fft_manual",
        "cal_phase_iq",
        "cal_step_iq_fft_title",
        "cal_step_iq_fft_body",
        "cal_step_iq_fft_observe",
        apply_fn=_step_iq_fft_manual,
    ),
    CalibrationStepDef(
        "iq_rbw_manual",
        "cal_phase_iq",
        "cal_step_iq_rbw_title",
        "cal_step_iq_rbw_body",
        "cal_step_iq_rbw_observe",
        apply_fn=_step_iq_rbw_manual,
    ),
    CalibrationStepDef(
        "iq_span_20m",
        "cal_phase_boundary",
        "cal_step_iq_20m_title",
        "cal_step_iq_20m_body",
        "cal_step_iq_20m_observe",
        apply_fn=_step_iq_20m,
    ),
    CalibrationStepDef(
        "transition_19_21",
        "cal_phase_boundary",
        "cal_step_trans_19_21_title",
        "cal_step_trans_19_21_body",
        "cal_step_trans_19_21_observe",
        apply_fn=_step_transition_19_21,
    ),
    CalibrationStepDef(
        "sweep_span_50m",
        "cal_phase_sweep",
        "cal_step_sweep_50m_title",
        "cal_step_sweep_50m_body",
        "cal_step_sweep_50m_observe",
        apply_fn=_step_sweep_50m,
    ),
    CalibrationStepDef(
        "sweep_rbw_manual",
        "cal_phase_sweep",
        "cal_step_sweep_rbw_title",
        "cal_step_sweep_rbw_body",
        "cal_step_sweep_rbw_observe",
        apply_fn=_step_sweep_rbw_manual,
    ),
    CalibrationStepDef(
        "sweep_fft_manual",
        "cal_phase_sweep",
        "cal_step_sweep_fft_title",
        "cal_step_sweep_fft_body",
        "cal_step_sweep_fft_observe",
        apply_fn=_step_sweep_fft_manual,
    ),
    CalibrationStepDef(
        "hysteresis_18m",
        "cal_phase_sweep",
        "cal_step_hyst_18m_title",
        "cal_step_hyst_18m_body",
        "cal_step_hyst_18m_observe",
        apply_fn=_step_hysteresis_18m,
    ),
    CalibrationStepDef(
        "hysteresis_10m",
        "cal_phase_sweep",
        "cal_step_hyst_10m_title",
        "cal_step_hyst_10m_body",
        "cal_step_hyst_10m_observe",
        apply_fn=_step_hysteresis_10m,
    ),
    CalibrationStepDef(
        "display_ref_auto",
        "cal_phase_display",
        "cal_step_ref_auto_title",
        "cal_step_ref_auto_body",
        "cal_step_ref_auto_observe",
        apply_fn=_step_ref_auto,
        category="visual",
    ),
    CalibrationStepDef(
        "display_ref_manual",
        "cal_phase_display",
        "cal_step_ref_manual_title",
        "cal_step_ref_manual_body",
        "cal_step_ref_manual_observe",
        apply_fn=_step_ref_manual,
        category="visual",
    ),
    CalibrationStepDef(
        "rf_gain_lna",
        "cal_phase_rf",
        "cal_step_gain_lna_title",
        "cal_step_gain_lna_body",
        "cal_step_gain_lna_observe",
        apply_fn=_step_gain_lna,
        category="rf",
    ),
    CalibrationStepDef(
        "rf_gain_vga",
        "cal_phase_rf",
        "cal_step_gain_vga_title",
        "cal_step_gain_vga_body",
        "cal_step_gain_vga_observe",
        apply_fn=_step_gain_vga,
        category="rf",
    ),
)


def step_by_id(step_id: str) -> CalibrationStepDef | None:
    for step in CALIBRATION_STEPS:
        if step.id == step_id:
            return step
    return None


def step_index(step_id: str) -> int:
    for i, step in enumerate(CALIBRATION_STEPS):
        if step.id == step_id:
            return i
    return -1


def apply_step(step: CalibrationStepDef, params: SpectrumParams) -> SpectrumParams:
    return step.apply_fn(params)


@dataclass
class StepBackendReport:
    step_id: str
    passed: bool
    capture_mode: str
    span_mhz: float
    sample_rate_mhz: float
    rbw_khz: float
    fft_size: int
    sweep_ms: float
    checks: list[dict]
    hints: list[str] = field(default_factory=list)

    def summary_lines(self) -> list[str]:
        lines = [
            f"modo={self.capture_mode}  SPAN={self.span_mhz:.2f} MHz  SR={self.sample_rate_mhz:.2f} MHz",
            f"RBW={self.rbw_khz:.1f} kHz  FFT={self.fft_size}  SWT={self.sweep_ms:.0f} ms",
            f"backend={'PASS' if self.passed else 'FAIL'}",
        ]
        for hint in self.hints:
            lines.append(f"• {hint}")
        for chk in self.checks:
            if not chk.get("passed"):
                lines.append(f"✗ {chk.get('name')}: {chk.get('detail')}")
        return lines


def evaluate_step_backend(step: CalibrationStepDef, params: SpectrumParams) -> StepBackendReport:
    """API legacy — delega en ``analyze_step``."""
    from core.monitor.calibration.step_analyzer import analyze_step

    analysis = analyze_step(step, params)
    return StepBackendReport(
        step_id=analysis.step_id,
        passed=analysis.backend_passed,
        capture_mode=str(analysis.actual.get("capture_mode", "")),
        span_mhz=float(analysis.actual.get("span_mhz", 0)),
        sample_rate_mhz=float(analysis.actual.get("sample_rate_mhz", 0)),
        rbw_khz=float(analysis.actual.get("rbw_khz", 0)),
        fft_size=int(analysis.actual.get("fft_size", 0)),
        sweep_ms=float(analysis.actual.get("sweep_ms", 0)),
        checks=analysis.failed_checks,
        hints=analysis.hints + analysis.mismatches,
    )
