"""Simula llegada IQ en tiempo real y mide tasa PCM."""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from core.monitor.demod_branch import DemodBranch
from core.monitor.demod_dsp import AUDIO_RATE_HZ
from core.monitor.iq_constants import IQ_DEMOD_CHUNK_SAMPLES
from core.monitor.spectrum_params import SpectrumParams


def main() -> None:
    rate = 2_000_000.0
    params = SpectrumParams(
        center_freq_hz=92_000_000.0,
        vfo_freq_hz=92_200_000.0,
        sample_rate_hz=rate,
        demod_mode="fm",
        demod_bandwidth_hz=150_000.0,
        squelch_db=-90.0,
        operating_mode="sdr",
        audio_enabled=True,
    )
    branch = DemodBranch()
    iq_index = 0
    pcm_count = 0
    chunk_sec = IQ_DEMOD_CHUNK_SAMPLES / rate
    t0 = time.perf_counter()
    target = 5.0
    while time.perf_counter() - t0 < target:
        t_chunk = time.perf_counter()
        idx = np.arange(iq_index, iq_index + IQ_DEMOD_CHUNK_SAMPLES, dtype=np.float64)
        t = idx / rate
        offset = params.vfo_freq_hz - params.center_freq_hz
        mod = 0.35 * np.sin(2.0 * np.pi * 800.0 * t)
        iq = (0.45 * np.exp(1j * (2.0 * np.pi * offset * t + mod))).astype(np.complex64)
        iq_index += IQ_DEMOD_CHUNK_SAMPLES
        branch.process_iq(iq, params, sample_rate_hz=rate)
        state = branch.last_state
        if state is not None:
            pcm_count += state.pcm.size
        elapsed_chunk = time.perf_counter() - t_chunk
        wait = chunk_sec - elapsed_chunk
        if wait > 0:
            time.sleep(wait)
    elapsed = time.perf_counter() - t0
    pcm_rate = pcm_count / elapsed
    print(f"realtime pcm_rate={pcm_rate:.0f} target={AUDIO_RATE_HZ:.0f} ratio={pcm_rate/AUDIO_RATE_HZ:.3f}")
    if abs(pcm_rate - AUDIO_RATE_HZ) / AUDIO_RATE_HZ > 0.08:
        sys.exit(1)
    print("OK realtime")


if __name__ == "__main__":
    main()
