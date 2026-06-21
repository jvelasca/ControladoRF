"""Tests de análisis del marcador F (nivel interpolado y S/R)."""
import numpy as np

from core.monitor.marker_analysis import estimate_snr_db, interpolate_power_db


def test_interpolate_power_db_at_edges():
    freqs = np.array([100e6, 110e6, 120e6])
    power = np.array([-50.0, -40.0, -30.0])
    assert interpolate_power_db(freqs, power, 100e6) == -50.0
    assert interpolate_power_db(freqs, power, 120e6) == -30.0


def test_interpolate_power_db_midpoint():
    freqs = np.array([100e6, 120e6])
    power = np.array([-50.0, -30.0])
    level = interpolate_power_db(freqs, power, 110e6)
    assert level is not None
    assert abs(level - (-40.0)) < 0.01


def test_interpolate_power_db_empty():
    assert interpolate_power_db(np.array([]), np.array([]), 100e6) is None


def test_estimate_snr_db():
    power = np.array([-90.0, -88.0, -40.0, -89.0])
    snr = estimate_snr_db(power, -40.0)
    assert snr is not None
    assert snr > 40.0
