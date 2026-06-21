"""Diagnóstico continuidad PCM demod FM (sin GUI)."""
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


def _mock_fm_chunk(
    *,
    start: int,
    n: int,
    rate: float,
    center_hz: float,
    vfo_hz: float,
) -> np.ndarray:
    idx = np.arange(start, start + n, dtype=np.float64)
    t = idx / rate
    offset = vfo_hz - center_hz
    audio = 0.55 * np.sin(2.0 * np.pi * 800.0 * t)
    dev_hz = 12_000.0
    phase = 2.0 * np.pi * offset * t + 2.0 * np.pi * dev_hz * np.cumsum(audio) / rate
    return (0.45 * np.exp(1j * phase)).astype(np.complex64)


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
    pcm_all: list[np.ndarray] = []
    t0 = time.perf_counter()
    target_sec = 3.0
    chunks = 0
    while time.perf_counter() - t0 < target_sec:
        iq = _mock_fm_chunk(
            start=iq_index,
            n=IQ_DEMOD_CHUNK_SAMPLES,
            rate=rate,
            center_hz=params.center_freq_hz,
            vfo_hz=params.vfo_freq_hz,
        )
        iq_index += IQ_DEMOD_CHUNK_SAMPLES
        branch.process_iq(iq, params, sample_rate_hz=rate)
        state = branch.last_state
        if state is not None and state.pcm.size > 0:
            pcm_all.append(state.pcm.copy())
        chunks += 1

    pcm = np.concatenate(pcm_all) if pcm_all else np.zeros(0)
    elapsed = time.perf_counter() - t0
    pcm_rate = pcm.size / elapsed
    expected = AUDIO_RATE_HZ
    gaps = 0
    if pcm.size > 1:
        jumps = np.abs(np.diff(pcm))
        gaps = int(np.sum(jumps > 0.5))

    wav_path = ROOT / "scripts" / "demod_test.wav"
    if pcm.size > 0:
        from wave import open as wav_open

        pcm16 = np.clip(pcm, -1.0, 1.0)
        pcm16 = (pcm16 * 32767.0).astype(np.int16)
        with wav_open(str(wav_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(int(AUDIO_RATE_HZ))
            wf.writeframes(pcm16.tobytes())

    state = branch.last_state
    print(f"chunks={chunks} pcm_samples={pcm.size} rate={pcm_rate:.0f} expected={expected:.0f}")
    print(f"ratio={pcm_rate/expected:.3f} large_jumps={gaps} squelch_open={state.squelch_open if state else False}")
    print(f"level_dbfs={state.level_dbfs if state else -999:.1f} vu={state.vu_dbfs if state else -999:.1f}")
    if pcm.size > 0:
        print(f"wav={wav_path}")
    if pcm_rate < expected * 0.95:
        print("FAIL: insufficient PCM rate")
        sys.exit(1)
    if gaps > pcm.size * 0.01:
        print("WARN: many discontinuities in PCM")
    print("OK")


if __name__ == "__main__":
    main()
