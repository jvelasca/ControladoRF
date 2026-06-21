"""Validación de invariantes cadena RF → adquisición → análisis → visualización."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from core.monitor.monitor_bw_sweep_logic import effective_sweep_time_ms, sweep_bin_width_hz
from core.monitor.spectrum_params import SpectrumParams
from core.rf.acquisition.policy import DefaultAcquisitionPolicy
from core.rf.bridge import (
    analysis_config_from_params,
    enrich_acquisition_plan,
    operator_intent_from_params,
)
from core.rf.display import display_trace_bins
from core.rf.types import AcquisitionMode


@dataclass
class ChainCheck:
    name: str
    passed: bool
    detail: str = ""
    severity: str = "error"  # error | warn | info

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "detail": self.detail,
            "severity": self.severity,
        }


@dataclass
class ChainValidation:
    checks: list[ChainCheck] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.passed or c.severity != "error" for c in self.checks)

    @property
    def errors(self) -> list[ChainCheck]:
        return [c for c in self.checks if not c.passed and c.severity == "error"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "checks": [c.to_dict() for c in self.checks],
        }


def _is_power_of_two(n: int) -> bool:
    return n > 0 and (n & (n - 1)) == 0


def _policy_capture_mode(params: SpectrumParams) -> str:
    pol = DefaultAcquisitionPolicy()
    intent = operator_intent_from_params(params)
    plan = pol.plan(intent, device_id=intent.source_id)
    return "sweep" if plan.mode.value == "sweep" else "iq"


def validate_analysis_chain(params: SpectrumParams) -> ChainValidation:
    """Comprueba coherencia tras ``prepare_params_for_capture`` (estilo self-test R&S)."""
    result = ChainValidation()
    span = max(float(params.display_span_hz()), float(params.span_hz), 1.0)
    mode = str(params.capture_mode or "iq")
    policy_mode = _policy_capture_mode(params)

    result.checks.append(
        ChainCheck(
            "capture_mode_matches_policy",
            mode == policy_mode,
            f"capture_mode={mode} policy={policy_mode}",
        )
    )

    window = float(params.freq_stop_hz()) - float(params.freq_start_hz())
    result.checks.append(
        ChainCheck(
            "freq_window_matches_span",
            abs(window - span) < max(span * 0.01, 1000.0),
            f"window={window/1e6:.3f} MHz span={span/1e6:.3f} MHz",
        )
    )

    fft = int(params.fft_size)
    result.checks.append(
        ChainCheck(
            "fft_size_power_of_two",
            _is_power_of_two(fft),
            f"fft_size={fft}",
        )
    )
    result.checks.append(
        ChainCheck(
            "fft_size_in_range",
            256 <= fft <= 8192,
            f"fft_size={fft}",
        )
    )

    if mode == "iq":
        sr = float(params.sample_rate_hz)
        instant = float(params.instant_span_hz())
        if span > instant + 50_000.0:
            sr_ok = abs(sr - instant) < max(instant * 0.02, 50_000.0)
            span_ok = abs(span - float(params.display_span_hz())) < max(span * 0.02, 50_000.0)
            ok = sr_ok and span_ok
            detail = (
                f"sample_rate={sr/1e6:.3f} MHz instant={instant/1e6:.3f} MHz "
                f"display_span={params.display_span_hz()/1e6:.3f} MHz"
            )
        else:
            ok = abs(sr - span) < max(span * 0.02, 50_000.0)
            detail = f"sample_rate={sr/1e6:.3f} MHz span={span/1e6:.3f} MHz"
        result.checks.append(
            ChainCheck(
                "iq_sample_rate_matches_span",
                ok,
                detail,
            )
        )
        eff_rbw = float(params.effective_rbw_hz())
        derived = sr / max(fft, 1)
        result.checks.append(
            ChainCheck(
                "iq_rbw_equals_sr_over_fft",
                abs(eff_rbw - derived) / max(derived, 1.0) < 0.02,
                f"rbw={eff_rbw:.1f} Hz derived={derived:.1f} Hz",
            )
        )
        result.checks.append(
            ChainCheck(
                "iq_rbw_fft_auto_linked",
                params.rbw_auto == params.fft_auto,
                f"rbw_auto={params.rbw_auto} fft_auto={params.fft_auto}",
            )
        )
        rbw = eff_rbw
    else:
        rbw = float(sweep_bin_width_hz(params))
        result.checks.append(
            ChainCheck(
                "sweep_rbw_min_100k",
                rbw >= 99_000.0,
                f"rbw={rbw/1e3:.1f} kHz",
            )
        )
        swt = float(effective_sweep_time_ms(params))
        result.checks.append(
            ChainCheck(
                "sweep_time_positive",
                math.isfinite(swt) and swt >= 1.0,
                f"sweep_time_ms={swt:.1f}",
            )
        )

    bins = int(display_trace_bins(params))
    result.checks.append(
        ChainCheck(
            "display_bins_reasonable",
            64 <= bins <= 4096,
            f"display_bins={bins}",
        )
    )

    intent = operator_intent_from_params(params)
    analysis = analysis_config_from_params(params)
    pol = DefaultAcquisitionPolicy()
    plan = pol.plan(intent, device_id=intent.source_id)
    enriched = enrich_acquisition_plan(plan, params, analysis)

    if mode == "iq" and enriched.iq is not None:
        result.checks.append(
            ChainCheck(
                "plan_iq_fft_coherent",
                enriched.iq.fft_size == fft or abs(enriched.iq.fft_size - fft) <= fft * 0.5,
                f"plan_fft={enriched.iq.fft_size} params_fft={fft}",
            )
        )
        result.checks.append(
            ChainCheck(
                "plan_iq_rate_coherent",
                abs(enriched.iq.sample_rate_hz - params.sample_rate_hz) < 1000.0,
                f"plan_rate={enriched.iq.sample_rate_hz} params_rate={params.sample_rate_hz}",
            )
        )
    elif mode == "sweep" and enriched.sweep is not None:
        result.checks.append(
            ChainCheck(
                "plan_sweep_rbw_coherent",
                abs(enriched.sweep.bin_width_hz - rbw) < rbw * 0.05,
                f"plan_rbw={enriched.sweep.bin_width_hz} params_rbw={rbw}",
            )
        )
        result.checks.append(
            ChainCheck(
                "plan_mode_sweep",
                enriched.mode is AcquisitionMode.SWEEP,
                f"mode={enriched.mode}",
            )
        )

    return result
