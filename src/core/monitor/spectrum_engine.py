"""Motor FFT en hilo de trabajo — desacoplado de la GUI PyQt6."""
from __future__ import annotations

import threading
import time
from typing import Callable, Optional

from core.monitor.demod_branch import DemodBranch, DemodState
from core.monitor.demod_stream_worker import DemodStreamWorker
from core.monitor.digital_analysis_branch import DigitalAnalysisBranch
from core.monitor.digital_analysis_worker import DigitalAnalysisWorker
from core.monitor.device_discovery import idle_message_for_source
from core.monitor.monitor_flow_log import (
    HARDWARE_PARAM_KEYS,
    ReconfigureTimer,
    log_reconfigure_done,
    log_reconfigure_scheduled,
    log_stream_restart,
    param_value_changed,
)
from core.monitor.iq_stream_resilience import is_fatal_iq_error
from core.monitor.spectrum_params import SpectrumFrame, SpectrumParams
from core.monitor.spectrum_source import SpectrumSource, create_spectrum_source


def is_fatal_capture_error(message: str) -> bool:
    """Errores que requieren detener captura."""
    if is_fatal_iq_error(message):
        return True
    lower = (message or "").strip().lower()
    return "captura interrumpida" in lower


class SpectrumEngine:
    """Captura frames en un hilo daemon; open/close nunca en hilo GUI."""

    def __init__(
        self,
        *,
        on_frame: Optional[Callable[[SpectrumFrame], None]] = None,
        on_status: Optional[Callable[[str], None]] = None,
        on_running_changed: Optional[Callable[[bool], None]] = None,
        on_demod_pcm: Optional[Callable[[DemodState], None]] = None,
        on_demod_ui: Optional[Callable[[DemodState], None]] = None,
        on_digital_ui: Optional[Callable[[object], None]] = None,
    ) -> None:
        self._params = SpectrumParams()
        self._params_lock = threading.Lock()
        self._source: SpectrumSource = create_spectrum_source("mock")
        self._demod = DemodBranch()
        self._digital = DigitalAnalysisBranch()
        self._on_frame = on_frame
        self._on_status = on_status
        self._on_running_changed = on_running_changed
        self._on_demod_pcm = on_demod_pcm
        self._on_demod_ui = on_demod_ui
        self._on_recording_iq = None
        self._on_digital_ui = on_digital_ui
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._running = False
        self._connecting = False
        self._reconfigure_at: float = 0.0
        self._capture_failures = 0
        self._last_exit_message = ""
        self._last_stream_error = ""
        self._iq_stall_count = 0
        self._reconfigure_timer = ReconfigureTimer()
        self._demod_worker: Optional[DemodStreamWorker] = None
        self._digital_worker: Optional[DigitalAnalysisWorker] = None
        self._iq_recover_failures = 0
        self._last_iq_recover_at = 0.0
        self._reconfiguring = False
        self._demod_auxiliary = False
        self._aux_source: SpectrumSource | None = None

    @property
    def last_exit_message(self) -> str:
        return self._last_exit_message

    @property
    def params(self) -> SpectrumParams:
        with self._params_lock:
            return self._params.copy()

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_demod_auxiliary(self) -> bool:
        return self._demod_auxiliary

    @property
    def is_connecting(self) -> bool:
        return self._connecting

    def set_params(self, *, request_hw_reconfigure: bool = True, **kwargs) -> None:
        changed_hw: list[str] = []
        with self._params_lock:
            prev_mode = self._params.capture_mode
            for key, value in kwargs.items():
                if not hasattr(self._params, key):
                    continue
                old = getattr(self._params, key)
                if param_value_changed(key, old, value):
                    if key in HARDWARE_PARAM_KEYS and key != "capture_mode":
                        changed_hw.append(f"{key}={old!r}->{value!r}")
                setattr(self._params, key, value)
            capture_changed = prev_mode != self._params.capture_mode
            if capture_changed:
                changed_hw.append(f"capture_mode={prev_mode!r}->{self._params.capture_mode!r}")
            if self._params.capture_mode == "iq":
                if "span_hz" in kwargs and "sample_rate_hz" not in kwargs:
                    self._params.apply_span_as_sample_rate()
                elif any(k in kwargs for k in ("sample_rate_hz", "capture_mode")):
                    self._params.sync_iq_display()
        if request_hw_reconfigure and self._running and changed_hw and not self._demod_auxiliary:
            self.request_reconfigure(changed_hw)

    def request_reconfigure(self, changed_hw: list[str] | None = None) -> None:
        """Marca cambios de hardware; se aplican en el hilo worker (no bloquea GUI)."""
        self._reconfigure_at = time.monotonic()
        if changed_hw:
            log_reconfigure_scheduled(changed_hw)

    @property
    def source_impl_id(self) -> str:
        return self._source.source_id

    def set_source(self, source_id: str) -> tuple[bool, str]:
        """Selecciona fuente sin abrir hardware (no bloqueante)."""
        base_id = source_id.split("_")[0] if source_id.startswith("hackrf") else source_id
        with self._params_lock:
            if self._params.source_id == base_id:
                return True, idle_message_for_source(base_id)
        if self._connecting:
            return True, idle_message_for_source(self.params.source_id)
        was_running = self._running or self._connecting
        if was_running:
            self.stop()
        try:
            self._source.close()
        except Exception:
            pass
        self._source = create_spectrum_source(base_id)
        with self._params_lock:
            self._params.source_id = base_id
        return True, idle_message_for_source(base_id)

    def start(self) -> tuple[bool, str]:
        if self._running:
            return True, "Ya en ejecución"
        if self._connecting:
            return True, "Conectando…"
        self._last_exit_message = ""
        self._stop.clear()
        self._connecting = True
        self._thread = threading.Thread(target=self._run_with_open, name="SpectrumEngine", daemon=True)
        self._thread.start()
        return True, "Conectando…"

    def start_demod_auxiliary(self, iq_source: SpectrumSource) -> None:
        """Demod/audio/digital sobre IQ ya abierto por motor RF v2 (sin segundo stream)."""
        if self._running or self._connecting or self._demod_auxiliary:
            return
        self._demod_auxiliary = True
        self._aux_source = self._source
        self._source = iq_source
        self._stop.clear()
        self._last_exit_message = ""
        self._start_demod_worker()
        self._start_digital_worker()
        self._running = True
        with self._params_lock:
            self._params.running = True
        self._emit_running(True)
        self._emit_status("Demodulación sobre motor RF v2")

    def stop(self) -> None:
        self._stop.set()
        self._reconfigure_at = 0.0
        if self._demod_auxiliary:
            self._stop_demod_worker()
            self._stop_digital_worker()
            self._demod.reset()
            self._digital.reset()
            if self._aux_source is not None:
                self._source = self._aux_source
                self._aux_source = None
            self._demod_auxiliary = False
            self._running = False
            self._connecting = False
            with self._params_lock:
                self._params.running = False
            self._emit_running(False)
            if not self._last_exit_message:
                self._emit_status("Detenido")
            return
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        self._thread = None
        try:
            self._source.close()
        except Exception:
            pass
        self._running = False
        self._connecting = False
        with self._params_lock:
            self._params.running = False
        self._demod.reset()
        self._digital.reset()
        self._stop_demod_worker()
        self._stop_digital_worker()
        self._emit_running(False)
        if not self._last_exit_message:
            self._emit_status("Detenido")

    def release_hardware(self) -> None:
        release = getattr(self._source, "release_iq_stream", None)
        if callable(release):
            release()

    def reset_demod_signal_chain(self) -> None:
        self._demod.reset_signal_chain()

    def read_iq_snapshot(self, params: SpectrumParams, num_samples: int):
        read = getattr(self._source, "read_iq_snapshot", None)
        if not callable(read):
            return None
        return read(params, int(num_samples))

    def _stop_digital_worker(self) -> None:
        if self._digital_worker is not None:
            self._digital_worker.join(timeout=2.0)
            self._digital_worker = None

    def _start_digital_worker(self) -> None:
        self._stop_digital_worker()
        self._digital_worker = DigitalAnalysisWorker(
            source=self._source,
            branch=self._digital,
            get_params=lambda: self.params,
            stop_event=self._stop,
            on_ui=self._on_digital_ui,
        )
        self._digital_worker.start()

    def set_recording_iq_handler(self, handler) -> None:
        self._on_recording_iq = handler

    def _stop_demod_worker(self) -> None:
        if self._demod_worker is not None:
            self._demod_worker.join(timeout=2.0)
            self._demod_worker = None

    def _start_demod_worker(self) -> None:
        self._stop_demod_worker()
        self._demod_worker = DemodStreamWorker(
            source=self._source,
            demod=self._demod,
            get_params=lambda: self.params,
            on_pcm=self._on_demod_pcm,
            on_ui=self._on_demod_ui,
            on_iq=self._on_recording_iq,
            stop_event=self._stop,
        )
        self._demod_worker.start()
        self._demod.relax_squelch()

    def _apply_live_reconfigure(self) -> None:
        self._reconfiguring = True
        self._reconfigure_timer.start()
        try:
            with self._params_lock:
                params = self._params.copy()
            prepare = getattr(self._source, "prepare_capture_mode", None)
            if callable(prepare):
                prepare(params)
            if params.capture_mode == "sweep":
                log_reconfigure_done(
                    ok=True,
                    msg="Modo barrido (sin stream IQ)",
                    elapsed_ms=self._reconfigure_timer.elapsed_ms(),
                    capture_mode="sweep",
                )
                return
            configure = getattr(self._source, "configure_stream", None)
            if not callable(configure):
                return
            ok, msg = configure(params)
            if ok:
                self._last_stream_error = ""
                self._iq_stall_count = 0
                self._iq_recover_failures = 0
                if msg not in ("Sin cambios",):
                    self._demod.reset()
                    if msg:
                        self._emit_status(msg)
                log_reconfigure_done(
                    ok=True,
                    msg=msg,
                    elapsed_ms=self._reconfigure_timer.elapsed_ms(),
                    capture_mode=params.capture_mode,
                )
                return
            self._last_stream_error = msg
            self._emit_status(msg)
            log_reconfigure_done(
                ok=False,
                msg=msg,
                elapsed_ms=self._reconfigure_timer.elapsed_ms(),
                capture_mode=params.capture_mode,
            )
            recover = getattr(self._source, "recover_iq_stream", None)
            if callable(recover):
                ok2, msg2 = recover(params)
                if ok2:
                    self._last_stream_error = ""
                    self._iq_stall_count = 0
                    self._iq_recover_failures = 0
                    self._demod.reset()
                    self._demod.relax_squelch()
                    self._emit_status(msg2)
                    log_reconfigure_done(
                        ok=True,
                        msg=f"recover: {msg2}",
                        elapsed_ms=self._reconfigure_timer.elapsed_ms(),
                        capture_mode=params.capture_mode,
                    )
                else:
                    fatal = msg2 or msg
                    self._last_stream_error = fatal
                    self._emit_status(fatal)
                    log_stream_restart(reason="recover_failed", detail=fatal)
                    if is_fatal_iq_error(fatal):
                        self._last_exit_message = fatal
                        self._stop.set()
        finally:
            self._reconfiguring = False

    def _ensure_capture_warmup(self) -> bool:
        """Primer trazo IQ válido; recupera stream si hace falta."""
        with self._params_lock:
            params = self._params.copy()
        if params.capture_mode == "sweep":
            return self._warmup_capture(max_sec=120.0)
        if self._warmup_capture():
            return True
        recover = getattr(self._source, "recover_iq_stream", None)
        if callable(recover):
            ok, msg = recover(params)
            if ok and self._warmup_capture():
                return True
            fatal = msg or "No se pudo iniciar captura IQ — pulse STOP y PLAY"
        else:
            fatal = "Esperando datos del equipo…"
        self._last_exit_message = fatal
        self._emit_status(fatal)
        return False

    def _maybe_reconfigure(self) -> None:
        if self._reconfigure_at <= 0:
            return
        if time.monotonic() - self._reconfigure_at < 0.12:
            return
        self._reconfigure_at = 0.0
        self._apply_live_reconfigure()

    def _warmup_capture(self, *, max_sec: float = 8.0) -> bool:
        """Primer trazo válido antes de dar por iniciada la captura (evita PLAY vacío)."""
        deadline = time.monotonic() + max_sec
        while time.monotonic() < deadline and not self._stop.is_set():
            with self._params_lock:
                params = self._params.copy()
            try:
                frame = self._source.read_frame(params)
            except Exception as exc:
                msg = str(exc)
                if is_fatal_capture_error(msg):
                    self._last_exit_message = msg
                    self._emit_status(msg)
                    return False
                time.sleep(0.08)
                continue
            if self._on_frame:
                self._on_frame(frame)
            return True
        return False

    def _run_with_open(self) -> None:
        try:
            ok, msg = self._source.open()
            if self._stop.is_set():
                try:
                    self._source.close()
                except Exception:
                    pass
                return
            if not ok:
                self._emit_status(msg)
                self._connecting = False
                self._emit_running(False)
                return
            self._apply_live_reconfigure()
            if not self._ensure_capture_warmup():
                self._emit_status("Esperando datos del equipo…")
            self._start_demod_worker()
            self._start_digital_worker()
            self._running = True
            with self._params_lock:
                self._params.running = True
            self._connecting = False
            self._emit_running(True)
            self._emit_status(msg)
            self._run_loop()
        finally:
            self._running = False
            self._connecting = False
            self._stop_demod_worker()
            self._stop_digital_worker()
            with self._params_lock:
                self._params.running = False
            try:
                self._source.close()
            except Exception:
                pass
            self._emit_running(False)

    def _try_recover_iq(self, params: SpectrumParams, reason: str) -> bool:
        """Reinicia hackrf_transfer sin detener la app (estilo SDR++/Soapy overflow recovery)."""
        if params.capture_mode != "iq" or self._reconfiguring:
            return False
        now = time.monotonic()
        if now - self._last_iq_recover_at < 0.8:
            return False
        recover = getattr(self._source, "recover_iq_stream", None)
        if not callable(recover):
            return False
        self._last_iq_recover_at = now
        ok, msg = recover(params)
        if ok:
            self._iq_recover_failures = 0
            self._capture_failures = 0
            self._demod.reset()
            self._demod.relax_squelch()
            if msg and msg not in ("Sin cambios",):
                self._emit_status(msg)
            return True
        self._iq_recover_failures += 1
        if msg:
            self._last_stream_error = msg
        if self._iq_recover_failures >= 12 and is_fatal_iq_error(msg or reason):
            self._last_exit_message = msg or reason
            self._emit_status(self._last_exit_message)
            self._stop.set()
        return False

    def _run_loop(self) -> None:
        while not self._stop.is_set():
            t0 = time.monotonic()
            self._maybe_reconfigure()
            with self._params_lock:
                params = self._params.copy()
            iq_interval = 1.0 / (30.0 if params.demod_enabled() else 50.0)
            if (
                params.capture_mode == "sweep"
                and params.sweep_mode == "single"
                and not params.single_sweep_pending
            ):
                time.sleep(0.08)
                continue
            try:
                frame = self._source.read_frame(params)
            except Exception as exc:
                msg = str(exc)
                if params.capture_mode == "iq" and self._try_recover_iq(params, msg):
                    time.sleep(0.05)
                    continue
                if is_fatal_capture_error(msg):
                    fatal = msg
                    self._last_exit_message = fatal
                    self._emit_status(fatal)
                    self._stop.set()
                    break
                self._capture_failures += 1
                if self._capture_failures >= 80:
                    if params.capture_mode == "iq" and self._try_recover_iq(params, msg):
                        self._capture_failures = 0
                        continue
                    fatal = "Captura interrumpida — compruebe la conexión USB del equipo"
                    self._last_exit_message = fatal
                    self._emit_status(fatal)
                    self._stop.set()
                    break
                if self._capture_failures in (5, 20, 40):
                    self._emit_status(msg)
                time.sleep(0.08 if params.capture_mode == "iq" else 0.2)
                continue
            self._capture_failures = 0
            if (
                params.capture_mode == "sweep"
                and params.sweep_mode == "single"
                and params.single_sweep_pending
            ):
                with self._params_lock:
                    self._params.single_sweep_pending = False
            if self._on_frame:
                self._on_frame(frame)
            if params.capture_mode == "sweep":
                self._emit_status(
                    f"Barrido {params.display_span_hz() / 1e6:.1f} MHz · "
                    f"{params.freq_start_hz() / 1e6:.1f}–{params.freq_stop_hz() / 1e6:.1f} MHz"
                )
                time.sleep(0.05)
            else:
                elapsed = time.monotonic() - t0
                time.sleep(max(0.0, iq_interval - elapsed))

    def _emit_status(self, message: str) -> None:
        if self._on_status:
            self._on_status(message)

    def _emit_running(self, running: bool) -> None:
        if self._on_running_changed:
            self._on_running_changed(running)
