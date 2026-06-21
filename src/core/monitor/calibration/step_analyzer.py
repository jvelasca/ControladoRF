"""Análisis backend completo por paso — esperado vs real, cadena y diagnóstico."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.monitor.calibration.calibration_checklist import CalibrationStepDef, apply_step
from core.monitor.calibration.chain_validator import validate_analysis_chain
from core.monitor.spectrum_params import SpectrumParams
from core.rf.bridge import prepare_params_for_capture

# Campos trazables en el checklist (fácil de ampliar).
_TRACE_FIELDS: tuple[tuple[str, str, float], ...] = (
    ("capture_mode", "capture_mode", 0.0),
    ("span_hz", "span_mhz", 1e6),
    ("sample_rate_hz", "sample_rate_mhz", 1e6),
    ("fft_size", "fft_size", 0.0),
    ("fft_auto", "fft_auto", 0.0),
    ("rbw_hz", "rbw_khz", 1e3),
    ("rbw_auto", "rbw_auto", 0.0),
    ("sweep_auto", "sweep_auto", 0.0),
    ("sweep_time_ms", "sweep_ms", 0.0),
    ("ref_scale_auto", "ref_scale_auto", 0.0),
    ("ref_level_dbm", "ref_level_dbm", 0.0),
    ("ref_range_db", "ref_range_db", 0.0),
    ("lna_gain_db", "lna_gain_db", 0.0),
    ("vga_gain_db", "vga_gain_db", 0.0),
)

# Palabras clave en comentarios del operador → categoría de fallo (depuración).
_COMMENT_TAGS: dict[str, tuple[str, ...]] = {
    "escala": ("escala", "ref", "dbm", "rango", "satura", "clipping", "nivel"),
    "traza": ("traza", "trace", "salto", "parpadeo", "flicker", "corte", "reset"),
    "rbw_fft": ("rbw", "fft", "resoluc", "bin", "swt", "barrido", "sweep"),
    "span_modo": ("span", "mhz", "modo", "iq", "barrido", "20", "21", "ancho"),
    "ruido": ("ruido", "noise", "suelo", "floor", "dc"),
    "ganancia": ("lna", "vga", "gain", "ganancia", "amp"),
    "stream": ("play", "stop", "stream", "captura", "hackrf", "usb", "error"),
    "visual": ("waterfall", "cascada", "marcador", "grid", "pantalla", "display"),
}


@dataclass
class StepAnalysis:
    """Resultado estructurado del backend para un paso."""

    step_id: str
    backend_passed: bool
    chain_passed: bool
    step_checks_passed: bool
    expected: dict[str, Any] = field(default_factory=dict)
    actual: dict[str, Any] = field(default_factory=dict)
    mismatches: list[str] = field(default_factory=list)
    failed_checks: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    hints: list[str] = field(default_factory=list)
    diagnosis: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_snapshot(self) -> dict[str, Any]:
        return {
            "backend_passed": self.backend_passed,
            "chain_passed": self.chain_passed,
            "step_checks_passed": self.step_checks_passed,
            "expected": self.expected,
            "actual": self.actual,
            "mismatches": self.mismatches,
            "failed_checks": self.failed_checks,
            "warnings": self.warnings,
            "hints": self.hints,
            "diagnosis": self.diagnosis,
            "metrics": self.metrics,
        }

    def summary_lines(self) -> list[str]:
        lines = [
            f"══ BACKEND {'PASS' if self.backend_passed else 'FAIL'} ══",
            "",
            "— Estado actual —",
        ]
        act = self.actual
        lines.append(
            f"modo={act.get('capture_mode')}  SPAN={act.get('span_mhz', 0):.2f} MHz  "
            f"SR={act.get('sample_rate_mhz', 0):.2f} MHz"
        )
        lines.append(
            f"RBW={act.get('rbw_khz', 0):.1f} kHz  FFT={act.get('fft_size')}  "
            f"SWT={act.get('sweep_ms', 0):.0f} ms  "
            f"ref_auto={act.get('ref_scale_auto')}"
        )
        if self.mismatches:
            lines.append("")
            lines.append("— Esperado ≠ aplicado —")
            lines.extend(f"✗ {m}" for m in self.mismatches)
        if self.failed_checks:
            lines.append("")
            lines.append("— Cadena RF (invariantes) —")
            for chk in self.failed_checks:
                lines.append(f"✗ {chk.get('name')}: {chk.get('detail')}")
        if self.hints:
            lines.append("")
            lines.append("— Criterio del paso —")
            lines.extend(f"• {h}" for h in self.hints)
        if self.warnings:
            lines.append("")
            lines.extend(f"⚠ {w}" for w in self.warnings)
        if self.diagnosis:
            lines.append("")
            lines.append("— Diagnóstico —")
            lines.extend(f"→ {d}" for d in self.diagnosis)
        return lines


def param_snapshot(params: SpectrumParams) -> dict[str, Any]:
    prepared = prepare_params_for_capture(params.copy())
    snap: dict[str, Any] = {
        "capture_mode": str(prepared.capture_mode),
        "span_mhz": float(prepared.span_hz) / 1e6,
        "sample_rate_mhz": float(prepared.sample_rate_hz) / 1e6,
        "rbw_khz": float(prepared.effective_rbw_hz()) / 1e3,
        "fft_size": int(prepared.fft_size),
        "fft_auto": bool(prepared.fft_auto),
        "rbw_auto": bool(prepared.rbw_auto),
        "sweep_auto": bool(prepared.sweep_auto),
        "sweep_ms": float(prepared.sweep_time_ms),
        "ref_scale_auto": bool(prepared.ref_scale_auto),
        "ref_level_dbm": float(prepared.ref_level_dbm),
        "ref_range_db": float(prepared.ref_range_db),
        "lna_gain_db": int(prepared.lna_gain_db),
        "vga_gain_db": int(prepared.vga_gain_db),
        "center_mhz": float(prepared.center_freq_hz) / 1e6,
        "source_id": str(prepared.source_id or ""),
    }
    return snap


def _compare_snapshots(expected: dict[str, Any], actual: dict[str, Any]) -> list[str]:
    mismatches: list[str] = []
    for attr, key, scale in _TRACE_FIELDS:
        exp = expected.get(key)
        got = actual.get(key)
        if exp is None or got is None:
            continue
        if isinstance(exp, str) or scale == 0.0:
            if str(exp) != str(got):
                mismatches.append(f"{key}: esperado={exp} actual={got}")
        else:
            tol = max(abs(float(exp)) * 0.02, 1.0 / scale)
            if abs(float(got) - float(exp)) > tol:
                mismatches.append(f"{key}: esperado={exp} actual={got}")
    return mismatches


def _step_specific_hints(step: CalibrationStepDef, actual: dict[str, Any]) -> list[str]:
    hints: list[str] = []
    mode = actual.get("capture_mode")
    span = float(actual.get("span_mhz", 0))

    rules: dict[str, list[tuple[bool, str]]] = {
        "iq_span_10m": [(mode != "iq", "Se esperaba modo IQ")],
        "iq_fft_manual": [(actual.get("fft_size") != 4096, f"FFT debería ser 4096, es {actual.get('fft_size')}")],
        "iq_span_20m": [
            (mode != "iq", "A 20 MHz debe permanecer en IQ"),
            (abs(float(actual.get("sample_rate_mhz", 0)) - 20.0) > 0.2, "sample_rate debería ≈ 20 MHz"),
        ],
        "transition_19_21": [
            (mode != "sweep", "Tras 19→21 MHz debe pasar a barrido hackrf_sweep"),
            (abs(span - 21.0) > 0.2, f"SPAN debería ser 21 MHz, es {span:.2f}"),
        ],
        "sweep_span_50m": [(mode != "sweep", "Se esperaba barrido hackrf_sweep")],
        "sweep_rbw_manual": [
            (mode != "sweep", "RBW barrido manual requiere modo sweep"),
            (actual.get("sweep_auto") is True, "SWT debería estar manual al fijar RBW"),
        ],
        "hysteresis_18m": [(mode != "iq", "Tras bajar de 50→18 MHz debe volver a IQ simple")],
        "hysteresis_10m": [(mode != "iq", "A 10 MHz debe volver a IQ")],
        "iq_trace_signal": [(mode != "iq", "Debe estar en IQ para observar traza")],
        "display_ref_manual": [(actual.get("ref_scale_auto") is True, "ref_scale_auto debería ser False")],
        "display_ref_auto": [(actual.get("ref_scale_auto") is False, "ref_scale_auto debería ser True")],
    }
    for ok, msg in rules.get(step.id, []):
        if ok:
            hints.append(msg)
    return hints


def _build_diagnosis(
    step: CalibrationStepDef,
    *,
    chain_passed: bool,
    step_passed: bool,
    mismatches: list[str],
    failed_checks: list[dict],
) -> list[str]:
    diag: list[str] = []
    if not chain_passed:
        diag.append("La cadena RF→análisis→visualización incumple invariantes.")
    if mismatches:
        diag.append("Los parámetros en vivo no coinciden con lo que el paso configuró.")
    if not step_passed:
        diag.append(f"El criterio específico del paso «{step.id}» no se cumple.")
    if chain_passed and step_passed and not mismatches:
        if step.category == "visual":
            diag.append("Backend OK — validación visual pendiente del operador.")
        else:
            diag.append("Backend OK — parámetros y cadena coherentes.")
    if step.id == "transition_19_21" and mismatches:
        diag.append("Revisar politica span_exceeds_instant_bw y prepare_params_for_capture en ~20 MHz.")
    if step.id in ("sweep_rbw_manual", "iq_rbw_manual") and failed_checks:
        diag.append("Revisar acoplamiento RBW/FFT/SWT en monitor_bw_sweep_logic.")
    return diag


def analyze_step(
    step: CalibrationStepDef,
    live_params: SpectrumParams,
    *,
    base_before_apply: SpectrumParams | None = None,
) -> StepAnalysis:
    """Analiza estado en vivo vs configuración esperada del paso."""
    base = base_before_apply or live_params
    try:
        expected_params = apply_step(step, base.copy())
    except Exception as exc:
        return StepAnalysis(
            step_id=step.id,
            backend_passed=False,
            chain_passed=False,
            step_checks_passed=False,
            diagnosis=[f"Error al calcular configuración esperada: {exc}"],
        )

    expected = param_snapshot(expected_params)
    actual = param_snapshot(live_params)
    mismatches = _compare_snapshots(expected, actual)

    prepared = prepare_params_for_capture(live_params.copy())
    validation = validate_analysis_chain(prepared)
    chain_passed = validation.passed
    failed_checks = [c.to_dict() for c in validation.checks if not c.passed and c.severity == "error"]

    hints = _step_specific_hints(step, actual)
    if step.id in ("prep_device", "prep_play"):
        return StepAnalysis(
            step_id=step.id,
            backend_passed=True,
            chain_passed=True,
            step_checks_passed=True,
            expected=expected,
            actual=actual,
            hints=["Paso preparatorio — validación visual del operador"],
            diagnosis=["Backend OK — confirme dispositivo y PLAY visualmente."],
            metrics={"policy_capture_mode": _policy_mode(prepared)},
        )

    step_checks_passed = len(hints) == 0
    backend_passed = chain_passed and step_checks_passed and not mismatches

    warnings: list[str] = []
    if mismatches and chain_passed:
        warnings.append("Cadena OK pero parámetros GUI/hardware desalineados con el paso.")

    diagnosis = _build_diagnosis(
        step,
        chain_passed=chain_passed,
        step_passed=step_checks_passed,
        mismatches=mismatches,
        failed_checks=failed_checks,
    )

    return StepAnalysis(
        step_id=step.id,
        backend_passed=backend_passed,
        chain_passed=chain_passed,
        step_checks_passed=step_checks_passed,
        expected=expected,
        actual=actual,
        mismatches=mismatches,
        failed_checks=failed_checks,
        warnings=warnings,
        hints=hints,
        diagnosis=diagnosis,
        metrics={
            "display_span_mhz": float(prepared.display_span_hz()) / 1e6,
            "effective_rbw_hz": float(prepared.effective_rbw_hz()),
            "policy_capture_mode": _policy_mode(prepared),
        },
    )


def _policy_mode(params: SpectrumParams) -> str:
    from core.rf.acquisition.policy import DefaultAcquisitionPolicy
    from core.rf.bridge import operator_intent_from_params

    pol = DefaultAcquisitionPolicy()
    intent = operator_intent_from_params(params)
    plan = pol.plan(intent, device_id=intent.source_id)
    return "sweep" if plan.mode.value == "sweep" else "iq"


def analyze_operator_comment(text: str) -> dict[str, Any]:
    """Clasifica el comentario del operador para depuración estructurada."""
    raw = (text or "").strip()
    if not raw:
        return {"empty": True, "tags": [], "length": 0}
    lower = raw.lower()
    tags = [tag for tag, words in _COMMENT_TAGS.items() if any(w in lower for w in words)]
    return {
        "empty": False,
        "tags": tags,
        "length": len(raw),
        "text_preview": raw[:500],
    }


def evaluate_record_coherence(
    *,
    user_verdict: str,
    backend_passed: bool | None,
    user_comment: str,
) -> dict[str, Any]:
    """Cruza veredicto operador × backend × comentario."""
    comment_info = analyze_operator_comment(user_comment)
    issues: list[str] = []
    if user_verdict == "fail" and comment_info["empty"]:
        issues.append("Falla sin comentario — difícil de depurar.")
    if user_verdict == "pass" and backend_passed is False:
        issues.append("Operador OK pero backend FAIL — posible problema solo visual o falso positivo backend.")
    if user_verdict == "fail" and backend_passed is True:
        issues.append("Operador FAIL pero backend PASS — problema visual/stream no capturado por invariantes.")
    if user_verdict == "fail" and not comment_info["empty"] and not comment_info["tags"]:
        issues.append("Comentario sin etiquetas conocidas — revisar texto manualmente.")
    return {
        "coherent": len(issues) == 0,
        "issues": issues,
        "comment_analysis": comment_info,
    }
