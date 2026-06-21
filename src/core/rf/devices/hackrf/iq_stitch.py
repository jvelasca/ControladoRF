"""Captura IQ en varios pasos cuando el lapso visible supera el BW instantaneo."""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

import numpy as np

from core.monitor.iq_fft import iq_bytes_to_complex
from core.rf.acquisition.iq_stitch_plan import stitch_center_freqs
from core.rf.spectrum_fft import compute_iq_spectrum_frame
from core.rf.types import AcquisitionMode, AcquisitionPlan, FrameMetadata, SpectrumFrame

if TYPE_CHECKING:
    from core.rf.devices.hackrf.device import HackRfDevice
    from core.rf.types import RfHardwareConfig, RxGainConfig


def merge_spectrum_frames(frames: list[SpectrumFrame]) -> SpectrumFrame:
    """Fusiona trazos IQ solapados (max hold por bin de frecuencia)."""
    if not frames:
        raise ValueError("merge_spectrum_frames: lista vacia")
    if len(frames) == 1:
        return frames[0]

    all_f = np.concatenate([np.asarray(f.freqs_hz, dtype=float).reshape(-1) for f in frames])
    all_p = np.concatenate([np.asarray(f.power_db, dtype=float).reshape(-1) for f in frames])
    order = np.argsort(all_f, kind="mergesort")
    all_f = all_f[order]
    all_p = all_p[order]

    uniq_f, inv = np.unique(all_f, return_inverse=True)
    merged_p = np.full(uniq_f.size, -140.0, dtype=float)
    for idx, power in enumerate(all_p):
        slot = int(inv[idx])
        merged_p[slot] = max(merged_p[slot], float(power))

    meta = replace(
        frames[0].metadata,
        acquisition_reason="iq_stitch",
        acquisition_mode=AcquisitionMode.IQ_STREAM,
    )
    return SpectrumFrame(
        freqs_hz=np.asarray(uniq_f, dtype=np.float64),
        power_db=np.asarray(merged_p, dtype=np.float64),
        metadata=meta,
    )


def capture_stitched_iq_spectrum(
    device: "HackRfDevice",
    plan: AcquisitionPlan,
    *,
    hw: "RfHardwareConfig",
    gain: "RxGainConfig",
) -> SpectrumFrame:
    """Varias FFT IQ con distinto FC y fusion en un solo trazo."""
    if plan.iq is None:
        raise RuntimeError("IQ plan missing")

    iq = plan.iq
    window = plan.window
    span = max(float(window.span_hz), float(window.stop_hz) - float(window.start_hz))
    centers = stitch_center_freqs(window.center_hz, span, iq.sample_rate_hz)
    frames: list[SpectrumFrame] = []
    n_fft = max(256, int(iq.fft_size))
    rbw_hz = iq.sample_rate_hz / max(n_fft, 1)

    for center in centers:
        step = replace(iq, center_freq_hz=float(center))
        device._iq_stream.ensure_stream(hw, step)
        block = device._iq_stream.read_iq_block(n_fft)
        samples = iq_bytes_to_complex(block, num_samples=n_fft)
        frames.append(
            compute_iq_spectrum_frame(
                samples,
                center_freq_hz=step.center_freq_hz,
                sample_rate_hz=step.sample_rate_hz,
                rx_gain=gain,
                device_id=device.device_id,
                rbw_hz=rbw_hz,
            )
        )

    return merge_spectrum_frames(frames)
