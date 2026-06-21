"""Filtro baseband HackRF — paridad libhackrf / SDR++."""
from __future__ import annotations

from core.monitor.hackrf_baseband import (
    compute_hackrf_baseband_filter_bw,
    default_baseband_filter_for_sample_rate,
)


def test_default_filter_2mhz_sample_rate():
    assert default_baseband_filter_for_sample_rate(2_000_000) == 1_750_000


def test_default_filter_10mhz_sample_rate():
    assert default_baseband_filter_for_sample_rate(10_000_000) == 7_000_000


def test_compute_rounds_down():
    assert compute_hackrf_baseband_filter_bw(1_500_000) == 1_750_000
    assert compute_hackrf_baseband_filter_bw(2_000_000) == 1_750_000
    assert compute_hackrf_baseband_filter_bw(2_500_000) == 2_500_000
