"""Hilo de captura espectro — analizador y SDR."""
from __future__ import annotations

import threading
import time
from collections import deque
from typing import Callable, Optional

from core.monitor.spectrum_engine import is_fatal_capture_error
from core.monitor.spectrum_params import SpectrumFrame, SpectrumParams
from core.rf.bridge import legacy_frame_from_display, operator_intent_from_params
from core.rf.session import RfSession
from core.rf.types import RfTelemetry

_IQ_TARGET_FPS = 50.0


class RfSpectrumRunner:
    """Hilo de captura espectro — analizador y SDR."""

    def __init__(
        self,
        *,
        on_frame: Optional[Callable[[SpectrumFrame], None]] = None,
        on_status: Optional[Callable[[str], None]] = None,
        on_running_changed: Optional[Callable[[bool], None]] = None,
    ) -> None:
        self._session = RfSession()
        self._on_frame = on_frame
        self._on_status = on_status
        self._on_running_changed = on_running_changed
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._running = False
        self._connecting = False
        self._last_exit_message = ""
        self._params = SpectrumParams()
        self._params_lock = threading.Lock()
        self._source_id = "mock"
        self._capture_failures = 0
        self._frame_times: deque[float] = deque(maxlen=32)
        self._capture_ms_ema: float | None = None
        self._fps = 0.0

    @property
    def last_exit_message(self) -> str:
        return self._last_exit_message

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_connecting(self) -> bool:
        return self._connecting

    @property
    def fps(self) -> float:
        return float(self._fps)

    @property
    def session(self) -> RfSession:
        return self._session

    def set_params(self, **kwargs: object) -> None:
        with self._params_lock:
            for key, value in kwargs.items():
                if hasattr(self._params, key):
                    setattr(self._params, key, value)

    def get_params(self) -> SpectrumParams:
        with self._params_lock:
            return self._params.copy()

    def sync_from_params(self, params: SpectrumParams) -> None:
        with self._params_lock:
            self._params = params.copy()
        intent = operator_intent_from_params(params)
        self._source_id = intent.source_id
        if self._session.device is None or self._session.device.device_id != intent.source_id:
            self._session.attach_source(intent.source_id)
        self._session.set_intent(intent)

    def telemetry(self) -> RfTelemetry:
        base = self._session.telemetry()
        return RfTelemetry(
            acquisition_mode=base.acquisition_mode,
            acquisition_reason=base.acquisition_reason,
            device_id=base.device_id,
            window_start_hz=base.window_start_hz,
            window_stop_hz=base.window_stop_hz,
            center_hz=base.center_hz,
            sample_rate_hz=base.sample_rate_hz,
            sweep_rbw_hz=base.sweep_rbw_hz,
            lna_db=base.lna_db,
            vga_db=base.vga_db,
            amp_on=base.amp_on,
            bb_filter_hz=base.bb_filter_hz,
            frame_bins=base.frame_bins,
            rbw_effective_hz=base.rbw_effective_hz,
            last_capture_ms=base.last_capture_ms,
            fps=self._fps,
        )

    def start(self) -> tuple[bool, str]:
        if self._running or self._connecting:
            return True, "Ya en ejecución"
        self._connecting = True
        self._emit_running(False)
        self._stop.clear()
        self._last_exit_message = ""
        self._capture_failures = 0
        self._frame_times.clear()
        self._capture_ms_ema = None
        self._fps = 0.0
        try:
            self._session.attach_source(self._source_id)
            self._session.open()
        except Exception as exc:
            self._connecting = False
            self._last_exit_message = str(exc)
            return False, self._last_exit_message
        self._thread = threading.Thread(target=self._run_loop, name="RfSpectrumRunner", daemon=True)
        self._thread.start()
        self._connecting = False
        self._running = True
        self._emit_running(True)
        if self._on_status:
            self._on_status("Captura RF activa")
        return True, "Captura RF iniciada"

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None
        try:
            self._session.close()
        except Exception:
            pass
        was_running = self._running
        self._running = False
        self._connecting = False
        if was_running:
            self._emit_running(False)

    def release_hardware(self) -> None:
        self.stop()

    def create_demod_iq_source(self):
        return self._session.create_demod_iq_source()

    def _emit_running(self, running: bool) -> None:
        if self._on_running_changed:
            self._on_running_changed(running)

    def _record_frame_timing(self, *, elapsed_sec: float) -> None:
        now = time.monotonic()
        self._frame_times.append(now)
        if len(self._frame_times) >= 2:
            window = self._frame_times[-1] - self._frame_times[0]
            if window > 0.05:
                self._fps = (len(self._frame_times) - 1) / window
        capture_ms = max(0.0, elapsed_sec * 1000.0)
        if self._capture_ms_ema is None:
            self._capture_ms_ema = capture_ms
        else:
            self._capture_ms_ema = self._capture_ms_ema * 0.82 + capture_ms * 0.18

    def _pace_after_frame(self, *, params: SpectrumParams, elapsed_sec: float) -> None:
        if params.capture_mode == "sweep":
            from core.monitor.monitor_bw_sweep_logic import effective_sweep_time_ms

            configured = effective_sweep_time_ms(params) / 1000.0
            # hackrf_sweep ya tarda lo que tarda; no añadir SWT si la captura superó el objetivo.
            if elapsed_sec >= configured:
                return
            time.sleep(max(0.0, configured - elapsed_sec))
            return
        iq_interval = 1.0 / _IQ_TARGET_FPS
        time.sleep(max(0.0, iq_interval - elapsed_sec))

    def _run_loop(self) -> None:
        while not self._stop.is_set():
            t0 = time.monotonic()
            try:
                with self._params_lock:
                    params = self._params.copy()
                self._session.set_intent(operator_intent_from_params(params))
                display = self._session.capture_once(legacy_params=params)
                frame = legacy_frame_from_display(
                    display,
                    center_freq_hz=params.center_freq_hz,
                    span_hz=max(params.span_hz, params.display_span_hz()),
                )
                self._capture_failures = 0
                if self._on_frame:
                    self._on_frame(frame)
            except Exception as exc:
                msg = str(exc)
                self._last_exit_message = msg
                if is_fatal_capture_error(msg):
                    if self._on_status:
                        self._on_status(msg)
                    self._stop.set()
                    break
                self._capture_failures += 1
                if self._capture_failures >= 80:
                    fatal = "Captura interrumpida — compruebe la conexión USB del equipo"
                    self._last_exit_message = fatal
                    if self._on_status:
                        self._on_status(fatal)
                    self._stop.set()
                    break
                if self._capture_failures in (5, 20, 40) and self._on_status:
                    self._on_status(msg)
                with self._params_lock:
                    capture_mode = self._params.capture_mode
                time.sleep(0.08 if capture_mode == "iq" else 0.2)
                continue
            elapsed = time.monotonic() - t0
            self._record_frame_timing(elapsed_sec=elapsed)
            with self._params_lock:
                params = self._params.copy()
            self._pace_after_frame(params=params, elapsed_sec=elapsed)
        self._running = False
        self._emit_running(False)
