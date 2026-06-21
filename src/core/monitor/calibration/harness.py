"""Ejecutor de calibración con informe JSON/Markdown."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from core.monitor.calibration.chain_validator import ChainValidation, validate_analysis_chain
from core.monitor.calibration.scenario_matrix import (
    CalibrationScenario,
    build_params_for_scenario,
    iter_flag_scenarios,
    iter_span_scenarios,
    iter_transition_scenarios,
)
from core.monitor.spectrum_params import SpectrumParams
from core.rf.bridge import prepare_params_for_capture


@dataclass
class ScenarioResult:
    scenario_id: str
    label: str
    passed: bool
    capture_mode: str
    span_hz: float
    sample_rate_hz: float
    rbw_hz: float
    fft_size: int
    sweep_time_ms: float
    checks: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "label": self.label,
            "passed": self.passed,
            "capture_mode": self.capture_mode,
            "span_hz": self.span_hz,
            "sample_rate_hz": self.sample_rate_hz,
            "rbw_hz": self.rbw_hz,
            "fft_size": self.fft_size,
            "sweep_time_ms": self.sweep_time_ms,
            "checks": self.checks,
            "errors": self.errors,
        }


@dataclass
class CalibrationReport:
    started_at: str
    finished_at: str
    duration_sec: float
    total: int
    passed: int
    failed: int
    results: list[ScenarioResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.failed == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_sec": self.duration_sec,
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "ok": self.ok,
            "results": [r.to_dict() for r in self.results],
        }


def _snapshot_params(params: SpectrumParams, scenario: CalibrationScenario, validation: ChainValidation) -> ScenarioResult:
    errors = [f"{c.name}: {c.detail}" for c in validation.errors]
    if scenario.capture_mode_expected and params.capture_mode != scenario.capture_mode_expected:
        errors.append(
            f"capture_mode={params.capture_mode} expected={scenario.capture_mode_expected}"
        )
    passed = validation.passed and not errors
    return ScenarioResult(
        scenario_id=scenario.id,
        label=scenario.label,
        passed=passed,
        capture_mode=str(params.capture_mode),
        span_hz=float(params.span_hz),
        sample_rate_hz=float(params.sample_rate_hz),
        rbw_hz=float(params.effective_rbw_hz()),
        fft_size=int(params.fft_size),
        sweep_time_ms=float(params.sweep_time_ms),
        checks=[c.to_dict() for c in validation.checks],
        errors=errors,
    )


class CalibrationHarness:
    """Batería offline (sin hardware) de la cadena de parámetros."""

    def __init__(self, *, on_progress: Callable[[str], None] | None = None) -> None:
        self._on_progress = on_progress or (lambda _msg: None)

    def _run_scenario(self, scenario: CalibrationScenario, params: SpectrumParams | None = None) -> ScenarioResult:
        if params is None:
            params = build_params_for_scenario(scenario)
        else:
            params = prepare_params_for_capture(params)
        validation = validate_analysis_chain(params)
        return _snapshot_params(params, scenario, validation)

    def run_matrix(self, *, include_flags: bool = True) -> CalibrationReport:
        from core.monitor.calibration.capture_transition import reset_capture_profiles

        reset_capture_profiles()
        t0 = time.perf_counter()
        started = datetime.now(timezone.utc).isoformat()
        results: list[ScenarioResult] = []

        for scenario in iter_span_scenarios():
            self._on_progress(f"SPAN {scenario.span_hz/1e6:.1f} MHz")
            results.append(self._run_scenario(scenario))

        for scenario in iter_transition_scenarios():
            self._on_progress(f"Transición → {scenario.span_hz/1e6:.1f} MHz")
            results.append(self._run_scenario(scenario))

        if include_flags:
            for sid, label, params in iter_flag_scenarios():
                self._on_progress(label)
                scenario = CalibrationScenario(id=sid, label=label, span_hz=params.span_hz)
                results.append(self._run_scenario(scenario, params))

        duration = time.perf_counter() - t0
        finished = datetime.now(timezone.utc).isoformat()
        passed = sum(1 for r in results if r.passed)
        return CalibrationReport(
            started_at=started,
            finished_at=finished,
            duration_sec=duration,
            total=len(results),
            passed=passed,
            failed=len(results) - passed,
            results=results,
        )

    def write_reports(self, report: CalibrationReport, log_dir: Path) -> tuple[Path, Path]:
        log_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_path = log_dir / f"calibration_{stamp}.json"
        md_path = log_dir / f"calibration_{stamp}.md"
        json_path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
        md_path.write_text(self._markdown(report), encoding="utf-8")
        latest_json = log_dir / "calibration_latest.json"
        latest_md = log_dir / "calibration_latest.md"
        latest_json.write_text(json_path.read_text(encoding="utf-8"), encoding="utf-8")
        latest_md.write_text(md_path.read_text(encoding="utf-8"), encoding="utf-8")
        return json_path, md_path

    @staticmethod
    def _markdown(report: CalibrationReport) -> str:
        lines = [
            "# Informe calibración Monitor",
            "",
            f"- Inicio: {report.started_at}",
            f"- Fin: {report.finished_at}",
            f"- Duración: {report.duration_sec:.2f} s",
            f"- Escenarios: {report.total} — **PASS {report.passed}** / FAIL {report.failed}",
            "",
            "## Resultados",
            "",
            "| Escenario | Modo | SPAN MHz | RBW kHz | FFT | Estado |",
            "|-----------|------|----------|---------|-----|--------|",
        ]
        for r in report.results:
            status = "PASS" if r.passed else "FAIL"
            lines.append(
                f"| {r.scenario_id} | {r.capture_mode} | {r.span_hz/1e6:.2f} | "
                f"{r.rbw_hz/1e3:.1f} | {r.fft_size} | {status} |"
            )
        lines.append("")
        failed = [r for r in report.results if not r.passed]
        if failed:
            lines.append("## Fallos")
            lines.append("")
            for r in failed:
                lines.append(f"### {r.scenario_id} — {r.label}")
                for err in r.errors:
                    lines.append(f"- {err}")
                for chk in r.checks:
                    if not chk.get("passed"):
                        lines.append(f"- [{chk.get('name')}] {chk.get('detail')}")
                lines.append("")
        return "\n".join(lines)
