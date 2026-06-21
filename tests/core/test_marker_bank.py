"""Tests del banco de marcadores M1–M10."""
from __future__ import annotations

import numpy as np

from core.monitor.marker_bank import (
    MARKER_COUNT,
    default_marker_bank,
    ensure_default_marker_on_f_readout,
    markers_from_dict,
    markers_to_dict,
    migrate_legacy_marker_bank,
    resolve_marker_delta,
    resolve_marker_frequency_hz,
)
from core.monitor.spectrum_params import SpectrumParams
from core.monitor.spectrum_params_io import params_from_dict, params_to_dict


def test_default_bank_has_ten_markers():
    bank = default_marker_bank(100e6)
    assert len(bank) == MARKER_COUNT
    assert bank[0].enabled is False


def test_delta_marker_frequency():
    params = SpectrumParams(center_freq_hz=100e6)
    params.markers[0].enabled = True
    params.markers[0].freq_hz = 100e6
    params.markers[1].enabled = True
    params.markers[1].mode = "delta"
    params.markers[1].ref_marker_id = 1
    params.markers[1].freq_hz = 25_000.0
    assert resolve_marker_frequency_hz(params, 2) == 100_025_000.0


def test_markers_persist_roundtrip():
    params = SpectrumParams(center_freq_hz=433.92e6)
    params.markers[2].enabled = True
    params.markers[2].mode = "delta"
    params.markers[2].ref_marker_id = 1
    params.markers[2].color = "#AABBCC"
    params.active_marker_id = 3
    data = params_to_dict(params)
    restored = params_from_dict(data)
    assert restored.active_marker_id == 3
    assert restored.markers[2].enabled is True
    assert restored.markers[2].mode == "delta"
    assert restored.markers[2].color == "#AABBCC"


def test_legacy_migration_from_f_readout():
    params = params_from_dict(
        {
            "center_freq_hz": 100e6,
            "selected_freq_hz": 145.5e6,
            "freq_readout": "f",
            "marker_show_snr": True,
        }
    )
    assert params.markers[0].enabled is False
    assert abs(params.markers[0].freq_hz - 145.5e6) < 1.0
    assert params.markers[0].show_snr is True


def test_delta_level_on_trace():
    freqs = np.linspace(99.9e6, 100.1e6, 512)
    power = np.full(512, -80.0, dtype=float)
    power[256] = -40.0
    power[300] = -50.0
    params = SpectrumParams(center_freq_hz=100e6)
    params.markers[0].enabled = True
    params.markers[0].freq_hz = 100e6
    params.markers[1].enabled = True
    params.markers[1].mode = "delta"
    params.markers[1].ref_marker_id = 1
    params.markers[1].freq_hz = freqs[300] - freqs[256]
    delta_f, delta_level = resolve_marker_delta(params, 2, freqs=freqs, power=power)
    assert delta_f is not None
    assert abs(delta_f - (freqs[300] - freqs[256])) < 500.0
    assert delta_level is not None
    assert abs(delta_level) > 0.5


def test_ensure_default_marker_on_f_readout_activates_m1():
    params = SpectrumParams(center_freq_hz=100e6, freq_readout="fc")
    params.active_marker_id = 3
    for marker in params.markers:
        marker.enabled = False
    ensure_default_marker_on_f_readout(params)
    assert params.active_marker_id == 1
    assert params.markers[0].enabled is True
    assert abs(params.markers[0].freq_hz - 100e6) < 1.0
    assert abs(params.selected_freq_hz - 100e6) < 1.0


def test_ensure_default_marker_keeps_valid_active():
    params = SpectrumParams(center_freq_hz=100e6, freq_readout="fc")
    params.active_marker_id = 2
    params.markers[1].enabled = True
    params.markers[1].freq_hz = 145.5e6
    ensure_default_marker_on_f_readout(params)
    assert params.active_marker_id == 2
    assert abs(params.markers[1].freq_hz - 145.5e6) < 1.0
