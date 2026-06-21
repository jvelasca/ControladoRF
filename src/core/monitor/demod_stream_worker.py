"""Hilo de demodulación continua — desacoplado del espectro (estilo SDR++/GQRX)."""
from __future__ import annotations

import threading
import time
from typing import Callable, Optional, Any

from core.monitor.demod_branch import DemodBranch, DemodState, DemodUiState
from core.monitor.iq_constants import IQ_DEMOD_CHUNK_SAMPLES
from core.monitor.spectrum_params import SpectrumParams
from core.monitor.spectrum_source import SpectrumSource


class DemodStreamWorker:
    """Consume IQ secuencialmente y alimenta audio/VU sin bloquear la FFT."""

    def __init__(
        self,
        *,
        source: SpectrumSource,
        demod: DemodBranch,
        get_params: Callable[[], SpectrumParams],
        stop_event: threading.Event,
        on_pcm: Optional[Callable[[DemodState], None]] = None,
        on_ui: Optional[Callable[[DemodUiState], None]] = None,
        on_iq: Optional[Callable[[Any, float], None]] = None,
    ) -> None:
        self._source = source
        self._demod = demod
        self._get_params = get_params
        self._on_pcm = on_pcm
        self._on_ui = on_ui
        self._on_iq = on_iq
        self._stop = stop_event
        self._thread: Optional[threading.Thread] = None
        self._chain_key: tuple[float, float, float, float, str] | None = None
        self._last_squelch_db: float | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self._run,
            name="DemodStreamWorker",
            daemon=True,
        )
        self._thread.start()

    def join(self, timeout: float = 2.0) -> None:
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
        self._thread = None
        self._chain_key = None
        self._last_squelch_db = None

    def _sync_chain_to_params(self, params: SpectrumParams) -> None:
        key = (
            float(params.sample_rate_hz),
            float(params.center_freq_hz),
            float(params.vfo_freq_hz),
            float(params.demod_bandwidth_hz),
            (params.demod_mode or "fm").lower(),
        )
        if self._chain_key != key:
            if self._chain_key is not None and self._chain_key[0] == key[0]:
                self._demod.reset_signal_chain()
            elif self._chain_key is not None:
                self._demod.reset()
            self._chain_key = key

        squelch = float(params.squelch_db)
        if squelch <= -112.0 or (
            self._last_squelch_db is not None and squelch < self._last_squelch_db - 0.25
        ):
            self._demod.relax_squelch()
        self._last_squelch_db = squelch

    def _run(self) -> None:
        last_ui_emit = 0.0
        while not self._stop.is_set():
            params = self._get_params()
            if not params.demod_enabled() or params.capture_mode != "iq":
                self._demod.reset()
                self._chain_key = None
                self._last_squelch_db = None
                time.sleep(0.03)
                continue

            self._sync_chain_to_params(params)

            read_stream = getattr(self._source, "read_iq_stream", None)
            pending_fn = getattr(self._source, "iq_stream_pending_samples", None)
            if not callable(read_stream):
                time.sleep(0.05)
                continue

            chunks = 0
            gap_reset = getattr(self._source, "consume_iq_gap_flag", None)
            rate = max(float(params.sample_rate_hz), 1.0)
            chunk_sec = IQ_DEMOD_CHUNK_SAMPLES / rate
            max_chunks = max(1, min(8, int(0.030 / max(chunk_sec, 1e-6))))
            if callable(pending_fn) and pending_fn() > IQ_DEMOD_CHUNK_SAMPLES * 4:
                max_chunks = min(12, max_chunks + 2)
            while chunks < max_chunks and not self._stop.is_set():
                if callable(gap_reset) and gap_reset():
                    self._demod.reset_signal_chain()
                samples = read_stream(params, IQ_DEMOD_CHUNK_SAMPLES)
                if samples is None or int(getattr(samples, "size", 0)) < 32:
                    break
                self._demod.process_iq(
                    samples,
                    params,
                    sample_rate_hz=params.sample_rate_hz,
                )
                if self._on_iq is not None:
                    self._on_iq(samples, rate)
                state = self._demod.last_state
                if state is not None:
                    if state.pcm.size > 0 and self._on_pcm is not None:
                        self._on_pcm(state)
                    now = time.monotonic()
                    if self._on_ui is not None and now - last_ui_emit >= 0.1:
                        self._on_ui(DemodUiState.from_state(state))
                        last_ui_emit = now
                chunks += 1

            if chunks == 0:
                time.sleep(0.004)
            else:
                time.sleep(0.001)
