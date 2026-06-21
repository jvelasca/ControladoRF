"""Hilo de análisis digital — snapshot IQ sin competir con demodulación de audio."""
from __future__ import annotations

import threading
import time
from typing import Callable, Optional

from core.monitor.digital_analysis_branch import DigitalAnalysisBranch, DigitalAnalysisUiState
from core.monitor.spectrum_params import SpectrumParams
from core.monitor.spectrum_source import SpectrumSource

_DIGITAL_IQ_SAMPLES = 16_384
_UI_INTERVAL_SEC = 0.25


class DigitalAnalysisWorker:
    def __init__(
        self,
        *,
        source: SpectrumSource,
        branch: DigitalAnalysisBranch,
        get_params: Callable[[], SpectrumParams],
        stop_event: threading.Event,
        on_ui: Optional[Callable[[DigitalAnalysisUiState], None]] = None,
    ) -> None:
        self._source = source
        self._branch = branch
        self._get_params = get_params
        self._on_ui = on_ui
        self._stop = stop_event
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self._run,
            name="DigitalAnalysisWorker",
            daemon=True,
        )
        self._thread.start()

    def join(self, timeout: float = 2.0) -> None:
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
        self._thread = None

    def _run(self) -> None:
        last_ui = 0.0
        while not self._stop.is_set():
            params = self._get_params()
            if not params.digital_analysis_active() or params.capture_mode != "iq":
                self._branch.reset()
                time.sleep(0.05)
                continue
            read_snapshot = getattr(self._source, "read_iq_snapshot", None)
            if not callable(read_snapshot):
                time.sleep(0.1)
                continue
            samples = read_snapshot(params, _DIGITAL_IQ_SAMPLES)
            if samples is None or int(getattr(samples, "size", 0)) < 256:
                time.sleep(0.05)
                continue
            try:
                self._branch.process_iq(
                    samples,
                    params,
                    sample_rate_hz=params.sample_rate_hz,
                )
            except Exception:
                import logging

                logging.getLogger(__name__).exception("digital analysis failed")
                time.sleep(0.1)
                continue
            now = time.monotonic()
            if self._on_ui is not None and self._branch.last_analysis is not None:
                if now - last_ui >= _UI_INTERVAL_SEC:
                    ui_state = self._branch.ui_state()
                    if ui_state is not None:
                        self._on_ui(ui_state)
                    last_ui = now
            time.sleep(0.05)
