"""Tests evaluación nominal vs referencia."""
from __future__ import annotations

from core.monitor.supervision.measurement_engine import ChannelMeasurement
from core.monitor.supervision.rule_evaluator import evaluate_channel_health_from_checks
from core.monitor.supervision.supervision_models import ChannelReferenceCapture
from core.monitor.supervision.threshold_checks import CHECK_SNR, ThresholdCheckConfig


def test_nominal_delta_warning_on_3db_drop():
    checks = {
        CHECK_SNR: ThresholdCheckConfig(
            enabled=True,
            warning_raise=3.0,
            critical_raise=6.0,
        )
    }
    reference = ChannelReferenceCapture(snr_above_noise_db=20.0)
    measurement = ChannelMeasurement(
        channel_key="ch1",
        label="Test",
        frequency_hz=500e6,
        snr_above_noise_db=16.5,
    )
    health = evaluate_channel_health_from_checks(
        measurement,
        checks,
        threshold_mode="nominal_delta",
        reference=reference,
    )
    assert health == "aviso"


def test_nominal_mer_drop_warning() -> None:
    from core.monitor.supervision.digital_rule_evaluator import evaluate_digital_health_from_checks
    from core.monitor.supervision.supervision_models import ChannelReferenceCapture, SupervisionRules
    from core.monitor.supervision.threshold_checks import CHECK_MER, ThresholdCheckConfig

    checks = {
        CHECK_MER: ThresholdCheckConfig(
            enabled=True,
            warning_raise=3.0,
            critical_raise=6.0,
        )
    }
    reference = ChannelReferenceCapture(mer_db=24.0)
    health = evaluate_digital_health_from_checks(
        mer_db=20.5,
        sync_ok=True,
        checks=checks,
        rules=SupervisionRules(digital_metrics_enabled=True),
        threshold_mode="nominal_delta",
        reference=reference,
    )
    assert health == "aviso"


def test_nominal_mer_hysteresis_stays_warning_until_clear() -> None:
    from core.monitor.supervision.digital_rule_evaluator import evaluate_digital_health_from_checks
    from core.monitor.supervision.supervision_models import ChannelReferenceCapture, SupervisionRules
    from core.monitor.supervision.threshold_checks import CHECK_MER, ThresholdCheckConfig

    checks = {
        CHECK_MER: ThresholdCheckConfig(
            enabled=True,
            warning_raise=3.0,
            warning_clear=2.0,
            critical_raise=6.0,
        )
    }
    reference = ChannelReferenceCapture(mer_db=24.0)
    kwargs = dict(
        sync_ok=True,
        checks=checks,
        rules=SupervisionRules(digital_metrics_enabled=True),
        threshold_mode="nominal_delta",
        reference=reference,
    )
    assert evaluate_digital_health_from_checks(mer_db=21.5, **kwargs, committed="aviso") == "aviso"
    assert evaluate_digital_health_from_checks(mer_db=23.5, **kwargs, committed="aviso") == "ok"


def test_nominal_delta_critical_on_6db_drop():
    checks = {
        CHECK_SNR: ThresholdCheckConfig(
            enabled=True,
            warning_raise=3.0,
            critical_raise=6.0,
        )
    }
    reference = ChannelReferenceCapture(snr_above_noise_db=20.0)
    measurement = ChannelMeasurement(
        channel_key="ch1",
        label="Test",
        frequency_hz=500e6,
        snr_above_noise_db=13.0,
    )
    health = evaluate_channel_health_from_checks(
        measurement,
        checks,
        threshold_mode="nominal_delta",
        reference=reference,
    )
    assert health == "critica"
