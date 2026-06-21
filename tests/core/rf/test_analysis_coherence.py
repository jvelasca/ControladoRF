"""Tests coherencia RBW/FFT/SWT/SUAV legacy ↔ v2."""
from __future__ import annotations

from core.monitor.monitor_bw_sweep_logic import patch_fft_size, patch_rbw_hz, sync_analysis_chain
from core.monitor.spectrum_params import SpectrumParams
from core.rf.acquisition.policy import DefaultAcquisitionPolicy
from core.rf.bridge import (
    analysis_config_from_params,
    enrich_acquisition_plan,
    operator_intent_from_params,
    prepare_params_for_capture,
)
from core.rf.types import AcquisitionMode


def test_manual_fft_iq_flows_to_enriched_plan():
    params = SpectrumParams(
        operating_mode="spectrum",
        source_id="hackrf",
        center_freq_hz=98_000_000.0,
        manual_span_hz=20_000_000.0,
        span_hz=20_000_000.0,
        span_mode="manual",
        capture_mode="iq",
        sample_rate_hz=20_000_000.0,
    )
    params = patch_fft_size(params, 4096)
    prepared = prepare_params_for_capture(params)
    assert prepared.capture_mode == "iq"
    assert prepared.fft_size == 4096
    intent = operator_intent_from_params(prepared)
    acq = DefaultAcquisitionPolicy().plan(intent, device_id="hackrf")
    assert acq.mode is AcquisitionMode.IQ_STREAM
    analysis = analysis_config_from_params(prepared)
    assert analysis.fft_size == 4096
    enriched = enrich_acquisition_plan(acq, prepared, analysis)
    assert enriched.iq is not None
    assert enriched.iq.fft_size == 4096


def test_manual_rbw_sweep_flows_to_bin_width():
    params = SpectrumParams(
        operating_mode="spectrum",
        source_id="hackrf",
        center_freq_hz=500_000_000.0,
        manual_span_hz=80_000_000.0,
        span_hz=80_000_000.0,
        span_mode="manual",
        marker_start_hz=460_000_000.0,
        marker_stop_hz=540_000_000.0,
        capture_mode="sweep",
    )
    params = patch_rbw_hz(params, 300_000.0)
    sync_analysis_chain(params)
    intent = operator_intent_from_params(params)
    acq = DefaultAcquisitionPolicy().plan(intent, device_id="hackrf")
    analysis = analysis_config_from_params(params)
    enriched = enrich_acquisition_plan(acq, params, analysis)
    assert enriched.sweep is not None
    assert enriched.sweep.bin_width_hz == 300_000.0


def test_manual_fft_sweep_display_bins_in_plan():
    params = SpectrumParams(
        operating_mode="spectrum",
        source_id="hackrf",
        center_freq_hz=98_000_000.0,
        manual_span_hz=80_000_000.0,
        span_hz=80_000_000.0,
        span_mode="manual",
        marker_start_hz=58_000_000.0,
        marker_stop_hz=138_000_000.0,
        capture_mode="sweep",
        rbw_auto=False,
    )
    params = patch_fft_size(params, 2048)
    assert params.fft_auto is False
    intent = operator_intent_from_params(params)
    acq = DefaultAcquisitionPolicy().plan(intent, device_id="hackrf")
    analysis = analysis_config_from_params(params)
    enriched = enrich_acquisition_plan(acq, params, analysis)
    assert enriched.sweep is not None
    assert enriched.sweep.display_bins == 2048


def test_fine_rbw_in_sweep_switches_to_iq_when_span_fits():
    from core.monitor.monitor_bw_sweep_logic import patch_rbw_hz

    params = SpectrumParams(
        operating_mode="spectrum",
        source_id="hackrf",
        center_freq_hz=98_000_000.0,
        manual_span_hz=20_000_000.0,
        span_hz=20_000_000.0,
        span_mode="manual",
        capture_mode="sweep",
    )
    updated = patch_rbw_hz(params, 30_000.0)
    assert updated.capture_mode == "iq"
    assert updated.rbw_hz == 30_000.0


def test_manual_sweep_time_in_analysis_config():
    params = SpectrumParams(
        operating_mode="spectrum",
        source_id="hackrf",
        capture_mode="sweep",
        center_freq_hz=98_000_000.0,
        manual_span_hz=20_000_000.0,
        span_hz=20_000_000.0,
        sweep_auto=False,
        sweep_time_ms=2000.0,
    )
    sync_analysis_chain(params)
    analysis = analysis_config_from_params(params)
    assert analysis.sweep_time_ms == 2000.0


def test_manual_fft_preserved_after_sync_chain():
    params = SpectrumParams(
        operating_mode="spectrum",
        source_id="hackrf",
        center_freq_hz=98_000_000.0,
        manual_span_hz=20_000_000.0,
        span_hz=20_000_000.0,
        span_mode="manual",
        marker_start_hz=88_000_000.0,
        marker_stop_hz=108_000_000.0,
        capture_mode="sweep",
    )
    from core.monitor.monitor_bw_sweep_logic import patch_fft_size, sync_analysis_chain

    params = patch_fft_size(params, 1024)
    params.rbw_auto = False
    params.rbw_hz = 300_000.0
    assert params.fft_size == 1024
    rbw = params.rbw_hz
    sync_analysis_chain(params)
    assert params.fft_size == 1024
    assert params.rbw_hz == rbw
