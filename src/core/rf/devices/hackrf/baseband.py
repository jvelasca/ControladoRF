"""Filtro baseband MAX2837."""
from __future__ import annotations

from core.monitor.hackrf_baseband import (
    compute_hackrf_baseband_filter_bw,
    default_baseband_filter_for_sample_rate,
)

snap_filter_bw = compute_hackrf_baseband_filter_bw
default_filter_for_sample_rate = default_baseband_filter_for_sample_rate
