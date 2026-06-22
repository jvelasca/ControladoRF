"""Tests decodificador RDS — rendimiento y límites."""
from __future__ import annotations

import time

import numpy as np

from core.monitor.wfm_rds import RdsDecoderState, feed_rds_mpx


def test_feed_rds_mpx_bounded_runtime() -> None:
    state = RdsDecoderState()
    mpx = np.random.randn(4000).astype(np.float64) * 0.02
    t0 = time.perf_counter()
    for _ in range(20):
        feed_rds_mpx(mpx, sample_rate_hz=228_000.0, state=state)
    elapsed = time.perf_counter() - t0
    assert elapsed < 1.5


def test_feed_rds_mpx_limits_bit_buffer() -> None:
    state = RdsDecoderState()
    mpx = np.random.randn(8000).astype(np.float64) * 0.05
    for _ in range(30):
        feed_rds_mpx(mpx, sample_rate_hz=228_000.0, state=state)
    assert len(state.raw_bits) <= 4096
