"""Tests analizador backend del wizard de calibración."""
from __future__ import annotations

from core.monitor.calibration.calibration_checklist import step_by_id
from core.monitor.calibration.step_analyzer import (
    analyze_operator_comment,
    analyze_step,
    evaluate_record_coherence,
)
from core.monitor.spectrum_params import SpectrumParams


def test_analyze_step_transition_19_21() -> None:
    step = step_by_id("transition_19_21")
    assert step is not None
    base = SpectrumParams(
        operating_mode="spectrum",
        center_freq_hz=500e6,
        source_id="hackrf",
        span_mode="manual",
    )
    from core.monitor.calibration.calibration_checklist import apply_step

    applied = apply_step(step, base)
    analysis = analyze_step(step, applied, base_before_apply=base)
    assert analysis.backend_passed
    assert analysis.actual.get("capture_mode") == "sweep"


def test_operator_comment_tags() -> None:
    info = analyze_operator_comment("La traza salta al pasar de 20 a 21 MHz y el RBW muestra 0")
    assert "traza" in info["tags"]
    assert "rbw_fft" in info["tags"] or "span_modo" in info["tags"]


def test_coherence_fail_without_comment() -> None:
    coh = evaluate_record_coherence(
        user_verdict="fail",
        backend_passed=True,
        user_comment="",
    )
    assert not coh["coherent"]
    assert any("comentario" in i.lower() for i in coh["issues"])


def test_coherence_user_fail_backend_pass() -> None:
    coh = evaluate_record_coherence(
        user_verdict="fail",
        backend_passed=True,
        user_comment="Escala AUTO no sigue la señal",
    )
    assert not coh["coherent"]
    assert "visual" in coh["comment_analysis"]["tags"] or "escala" in coh["comment_analysis"]["tags"]
