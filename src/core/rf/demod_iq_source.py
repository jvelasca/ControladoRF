"""IQ compartido motor RF v2 → demodulación / análisis digital (sin segundo hackrf_transfer)."""
from __future__ import annotations

from typing import Optional

import numpy as np

from core.monitor.hackrf_iq_capture import HackRfIqCapture
from core.monitor.iq_fft import iq_bytes_to_complex
from core.monitor.spectrum_params import SpectrumParams


class RfDemodIqSource:
    """Adapta HackRfIqCapture al contrato IQ que usan DemodStreamWorker y DigitalAnalysisWorker."""

    source_id = "hackrf"
    display_name = "HackRF IQ (motor RF v2)"

    def __init__(self, capture: HackRfIqCapture) -> None:
        self._capture = capture

    def read_iq_stream(self, params: SpectrumParams, num_samples: int) -> Optional[np.ndarray]:
        if params.capture_mode != "iq" or not self._capture.is_running:
            return None
        n = max(32, int(num_samples))
        block = self._capture.read_iq_consume(n, wait_sec=0.02)
        if block is None:
            return None
        return iq_bytes_to_complex(block, num_samples=n)

    def read_iq_snapshot(self, params: SpectrumParams, num_samples: int) -> Optional[np.ndarray]:
        if params.capture_mode != "iq" or not self._capture.is_running:
            return None
        n = max(256, int(num_samples))
        block = self._capture.read_iq_snapshot(n, wait_sec=0.05)
        if block is None:
            return None
        return iq_bytes_to_complex(block, num_samples=n)

    def consume_iq_gap_flag(self) -> bool:
        return bool(self._capture.consume_demod_gap_flag())

    def iq_stream_pending_samples(self) -> int:
        return int(self._capture.demod_pending_samples())
