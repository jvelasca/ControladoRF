"""Captura IQ continua HackRF — libhackrf (SDR++) o hackrf_transfer (fallback)."""
from __future__ import annotations

import subprocess
import sys
import threading
import time
from typing import Optional, Tuple

from core.monitor.hackrf_lib import HackRfLibSession, libhackrf_available
from core.monitor.hackrf_paths import ensure_hackrf_on_path, resolve_hackrf_tool
from core.monitor.hackrf_rx_gains import snap_gains
from core.monitor.iq_constants import IQ_DEMOD_MAX_SAMPLES, IQ_RING_MAX_SAMPLES
from utils.subprocess_platform import popen_hidden, run_hidden


class IqSnapshotBuffer:
    """Buffer circular solo lectura «latest» — para FFT sin competir con demod."""

    def __init__(self, *, max_samples: int = IQ_RING_MAX_SAMPLES) -> None:
        self._max_bytes = max(4096, max_samples * 2)
        self._data = bytearray()
        self._lock = threading.Lock()

    def write(self, chunk: bytes) -> None:
        if not chunk:
            return
        with self._lock:
            self._data.extend(chunk)
            if len(self._data) > self._max_bytes:
                del self._data[: len(self._data) - self._max_bytes]

    def read_latest(self, num_samples: int) -> Optional[bytes]:
        need = num_samples * 2
        with self._lock:
            if len(self._data) < need:
                return None
            return bytes(self._data[-need:])

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


class IqRingBuffer:
    """Buffer circular de bytes IQ (I/Q int8 intercalados)."""

    def __init__(self, *, max_samples: int = IQ_RING_MAX_SAMPLES) -> None:
        self._max_bytes = max(4096, max_samples * 2)
        self._data = bytearray()
        self._consume_pos = 0
        self._lock = threading.Lock()
        self.gap_detected = False

    def write(self, chunk: bytes) -> None:
        if not chunk:
            return
        with self._lock:
            self._data.extend(chunk)
            self._compact_if_needed()

    def _compact_if_needed(self) -> None:
        if self._consume_pos > self._max_bytes // 2:
            del self._data[: self._consume_pos]
            self._consume_pos = 0
        pending = len(self._data) - self._consume_pos
        if pending > self._max_bytes:
            excess = pending - self._max_bytes
            self._consume_pos += excess
            self.gap_detected = True

    def pending_samples(self) -> int:
        with self._lock:
            return max(0, (len(self._data) - self._consume_pos) // 2)

    def read_consume(self, num_samples: int) -> Optional[bytes]:
        need = num_samples * 2
        with self._lock:
            if len(self._data) - self._consume_pos < need:
                return None
            start = self._consume_pos
            self._consume_pos += need
            return bytes(self._data[start : start + need])

    def read_latest(self, num_samples: int) -> Optional[bytes]:
        need = num_samples * 2
        with self._lock:
            if len(self._data) < need:
                return None
            return bytes(self._data[-need:])

    def has_samples(self, num_samples: int) -> bool:
        need = num_samples * 2
        with self._lock:
            return len(self._data) >= need

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
            self._consume_pos = 0
            self.gap_detected = False


class HackRfIqCapture:
    """RX IQ continuo — libhackrf en proceso (ganancias en caliente) o hackrf_transfer."""

    def __init__(self) -> None:
        self._proc: Optional[subprocess.Popen] = None
        self._reader: Optional[threading.Thread] = None
        self._lib: Optional[HackRfLibSession] = None
        self._backend: Optional[str] = None
        self._fft_buffer = IqSnapshotBuffer()
        self._demod_buffer = IqRingBuffer()
        self._stop = threading.Event()
        self._error: Optional[str] = None
        self._center_hz = 100_000_000.0
        self._sample_rate_hz = 2_000_000.0
        self._baseband_filter_bw_hz = 1_750_000
        self._lna_gain = 32
        self._vga_gain = 40
        self._rf_amp_enable = False
        self._rf_bias_tee_enable = False
        self._applied_lna_gain = 32
        self._applied_vga_gain = 40
        self._applied_rf_amp_enable = False
        self._applied_rf_bias_tee_enable = False

    def _mark_rx_gains_applied(self) -> None:
        self._applied_lna_gain = self._lna_gain
        self._applied_vga_gain = self._vga_gain
        self._applied_rf_amp_enable = self._rf_amp_enable
        self._applied_rf_bias_tee_enable = self._rf_bias_tee_enable

    def _restore_rx_targets_from_applied(self) -> None:
        self._lna_gain = self._applied_lna_gain
        self._vga_gain = self._applied_vga_gain
        self._rf_amp_enable = self._applied_rf_amp_enable
        self._rf_bias_tee_enable = self._applied_rf_bias_tee_enable

    @property
    def is_running(self) -> bool:
        if self._backend == "lib" and self._lib is not None:
            return self._lib.is_streaming
        return self._proc is not None and self._proc.poll() is None

    @property
    def backend(self) -> Optional[str]:
        return self._backend

    def _on_iq_chunk(self, chunk: bytes) -> None:
        if chunk:
            self._fft_buffer.write(chunk)
            self._demod_buffer.write(chunk)

    @property
    def last_error(self) -> Optional[str]:
        return self._error

    def configure(
        self,
        *,
        center_freq_hz: float,
        sample_rate_hz: float,
        lna_gain: int = 24,
        vga_gain: int = 34,
        rf_amp_enable: bool = False,
        rf_bias_tee_enable: bool = False,
        baseband_filter_bw_hz: float | None = None,
    ) -> None:
        self._center_hz = max(0.0, center_freq_hz)
        self._sample_rate_hz = _clamp_sample_rate(sample_rate_hz)
        g = snap_gains(lna_gain, vga_gain, rf_amp_enable)
        self._lna_gain = g.lna_db
        self._vga_gain = g.vga_db
        self._rf_amp_enable = g.amp_enable
        self._rf_bias_tee_enable = bool(rf_bias_tee_enable)
        if baseband_filter_bw_hz is not None:
            from core.monitor.hackrf_baseband import snap_hackrf_baseband_filter_bw

            self._baseband_filter_bw_hz = snap_hackrf_baseband_filter_bw(baseband_filter_bw_hz)
        else:
            from core.monitor.hackrf_baseband import default_baseband_filter_for_sample_rate

            self._baseband_filter_bw_hz = default_baseband_filter_for_sample_rate(
                self._sample_rate_hz
            )

    @staticmethod
    def _release_orphan_transfer() -> None:
        if sys.platform != "win32":
            return
        try:
            run_hidden(
                ["taskkill", "/F", "/IM", "hackrf_transfer.exe"],
                capture_output=True,
                timeout=4.0,
                check=False,
            )
        except OSError:
            pass
        time.sleep(0.25)

    def start(self) -> Tuple[bool, str]:
        self.stop()
        self._release_orphan_transfer()
        self._error = None
        self._stop.clear()
        self._fft_buffer.clear()
        self._demod_buffer.clear()

        ensure_hackrf_on_path()
        if libhackrf_available():
            ok, msg = self._start_lib()
            if ok:
                return ok, msg
            self._error = None

        return self._start_transfer()

    def _start_lib(self) -> Tuple[bool, str]:
        session = HackRfLibSession()
        try:
            session.open()
            session.configure(
                center_freq_hz=self._center_hz,
                sample_rate_hz=self._sample_rate_hz,
                lna_gain=self._lna_gain,
                vga_gain=self._vga_gain,
                rf_amp_enable=self._rf_amp_enable,
                rf_bias_tee_enable=self._rf_bias_tee_enable,
                baseband_filter_bw_hz=int(self._baseband_filter_bw_hz),
            )
            session.start_rx(self._on_iq_chunk)
            self._mark_rx_gains_applied()
        except RuntimeError as exc:
            try:
                session.close()
            except Exception:
                pass
            return False, str(exc)

        self._lib = session
        self._backend = "lib"

        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            if self._fft_buffer.read_latest(256) is not None:
                break
            time.sleep(0.02)
        if self._fft_buffer.read_latest(256) is None:
            self.stop()
            return False, "Sin muestras IQ al iniciar (libhackrf)"

        return True, self._status_message(backend="libhackrf")

    def _start_transfer(self) -> Tuple[bool, str]:
        self._backend = "transfer"
        exe = resolve_hackrf_tool("hackrf_transfer")
        if exe is None:
            return False, "hackrf_transfer no encontrado — ejecute install_hackrf_windows.ps1"

        freq = int(self._center_hz)
        rate = int(self._sample_rate_hz)
        cmd = [
            str(exe),
            "-r",
            "-",
            "-f",
            str(freq),
            "-s",
            str(rate),
            "-l",
            str(self._lna_gain),
            "-g",
            str(self._vga_gain),
            "-a",
            "1" if self._rf_amp_enable else "0",
            "-p",
            "1" if self._rf_bias_tee_enable else "0",
            "-b",
            str(int(self._baseband_filter_bw_hz)),
        ]
        try:
            self._proc = popen_hidden(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                bufsize=65536,
            )
        except OSError as exc:
            return False, str(exc)

        self._reader = threading.Thread(target=self._read_loop, name="HackRfIqReader", daemon=True)
        self._reader.start()
        time.sleep(0.35)

        if self._proc.poll() is not None:
            err = self._read_process_error() or "hackrf_transfer terminó al iniciar"
            self.stop()
            return False, err
        if self._error:
            err = self._error
            self.stop()
            return False, err[:300]

        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            if self._error or not self.is_running:
                break
            if self._fft_buffer.read_latest(256) is not None:
                break
            time.sleep(0.02)

        if self._error or not self.is_running:
            err = self._error or self._read_process_error() or "hackrf_transfer terminó al iniciar"
            self.stop()
            return False, err[:300]
        if self._fft_buffer.read_latest(256) is None:
            err = self._read_process_error() or "Sin muestras IQ al iniciar"
            self.stop()
            return False, err[:300]

        self._mark_rx_gains_applied()
        return True, self._status_message(backend="hackrf_transfer")

    def _status_message(self, *, backend: str) -> str:
        mhz = self._center_hz / 1e6
        rate_mhz = self._sample_rate_hz / 1e6
        bb_mhz = self._baseband_filter_bw_hz / 1e6
        pre = "P+" if self._rf_amp_enable else "P−"
        return (
            f"RX IQ ({backend}) {mhz:.3f} MHz · {rate_mhz:.2f} Msps · BB {bb_mhz:.2f} MHz · "
            f"LNA {self._lna_gain} · VGA {self._vga_gain} · {pre}"
        )

    def stop(self) -> None:
        self._stop.set()
        lib = self._lib
        self._lib = None
        if lib is not None:
            try:
                lib.close()
            except Exception:
                pass
        self._backend = None
        proc = self._proc
        self._proc = None
        if proc is not None:
            if proc.stdout is not None:
                try:
                    proc.stdout.close()
                except OSError:
                    pass
            if proc.stderr is not None:
                try:
                    proc.stderr.close()
                except OSError:
                    pass
            if proc.poll() is None:
                try:
                    proc.terminate()
                    proc.wait(timeout=1.5)
                except (subprocess.TimeoutExpired, OSError):
                    try:
                        proc.kill()
                    except OSError:
                        pass
        if self._reader and self._reader.is_alive():
            self._reader.join(timeout=1.0)
        self._reader = None
        self._fft_buffer.clear()
        self._demod_buffer.clear()
        self._demod_buffer.gap_detected = True
        self._error = None
        time.sleep(0.08)

    def restart_if_needed(
        self,
        *,
        center_freq_hz: float,
        sample_rate_hz: float,
        lna_gain: int = 24,
        vga_gain: int = 34,
        rf_amp_enable: bool = False,
        rf_bias_tee_enable: bool = False,
        baseband_filter_bw_hz: float | None = None,
    ) -> Tuple[bool, str]:
        rate = _clamp_sample_rate(sample_rate_hz)
        g = snap_gains(lna_gain, vga_gain, rf_amp_enable)
        lna = g.lna_db
        vga = g.vga_db
        amp = g.amp_enable
        bias_tee = bool(rf_bias_tee_enable)
        from core.monitor.hackrf_baseband import (
            default_baseband_filter_for_sample_rate,
            snap_hackrf_baseband_filter_bw,
        )

        bb = (
            default_baseband_filter_for_sample_rate(rate)
            if baseband_filter_bw_hz is None
            else snap_hackrf_baseband_filter_bw(baseband_filter_bw_hz)
        )
        freq_changed = abs(self._center_hz - center_freq_hz) >= 1.0
        rate_changed = abs(self._sample_rate_hz - rate) >= 1.0
        bb_changed = int(self._baseband_filter_bw_hz) != int(bb)
        gains_changed = (
            self._applied_lna_gain != lna
            or self._applied_vga_gain != vga
            or self._applied_rf_amp_enable != amp
        )
        bias_changed = self._applied_rf_bias_tee_enable != bias_tee
        if (
            self.is_running
            and not freq_changed
            and not rate_changed
            and not bb_changed
            and not gains_changed
            and not bias_changed
        ):
            return True, "Sin cambios"

        if self._backend == "lib" and self._lib is not None and self._lib.is_streaming:
            return self._apply_lib_params_live(
                center_freq_hz=center_freq_hz,
                sample_rate_hz=rate,
                lna_gain=lna,
                vga_gain=vga,
                rf_amp_enable=amp,
                rf_bias_tee_enable=bias_tee,
                baseband_filter_bw_hz=int(bb),
                freq_changed=freq_changed,
                rate_changed=rate_changed,
                bb_changed=bb_changed,
                gains_changed=gains_changed,
                bias_changed=bias_changed,
            )

        self.configure(
            center_freq_hz=center_freq_hz,
            sample_rate_hz=rate,
            lna_gain=lna,
            vga_gain=vga,
            rf_amp_enable=amp,
            rf_bias_tee_enable=bias_tee,
            baseband_filter_bw_hz=float(bb),
        )

        from core.monitor.monitor_flow_log import log_stream_restart

        log_stream_restart(
            reason="params_changed",
            detail=(
                f"fc={center_freq_hz:.0f} sr={rate:.0f} "
                f"lna={lna} vga={vga} amp={amp} bias={bias_tee}"
            ),
        )
        self.stop()
        time.sleep(0.25)
        return self.start()

    def _apply_lib_params_live(
        self,
        *,
        center_freq_hz: float,
        sample_rate_hz: float,
        lna_gain: int,
        vga_gain: int,
        rf_amp_enable: bool,
        rf_bias_tee_enable: bool,
        baseband_filter_bw_hz: int,
        freq_changed: bool,
        rate_changed: bool,
        bb_changed: bool,
        gains_changed: bool,
        bias_changed: bool,
    ) -> Tuple[bool, str]:
        """Aplica cambios sin reiniciar el proceso (libhackrf / SDR++)."""
        lib = self._lib
        if lib is None:
            return False, "Stream IQ detenido"
        try:
            if (gains_changed or bias_changed) and not (freq_changed or rate_changed or bb_changed):
                lib.apply_gains(
                    lna_gain=lna_gain,
                    vga_gain=vga_gain,
                    rf_amp_enable=rf_amp_enable,
                    rf_bias_tee_enable=rf_bias_tee_enable,
                )
            elif freq_changed and not (rate_changed or bb_changed):
                lib.apply_center_freq(center_freq_hz)
                if gains_changed or bias_changed:
                    lib.apply_gains(
                        lna_gain=lna_gain,
                        vga_gain=vga_gain,
                        rf_amp_enable=rf_amp_enable,
                        rf_bias_tee_enable=rf_bias_tee_enable,
                    )
            else:
                lib.stop_rx()
                self._fft_buffer.clear()
                self._demod_buffer.clear()
                lib.configure(
                    center_freq_hz=center_freq_hz,
                    sample_rate_hz=sample_rate_hz,
                    lna_gain=lna_gain,
                    vga_gain=vga_gain,
                    rf_amp_enable=rf_amp_enable,
                    rf_bias_tee_enable=rf_bias_tee_enable,
                    baseband_filter_bw_hz=baseband_filter_bw_hz,
                )
                lib.start_rx(self._on_iq_chunk)

            self.configure(
                center_freq_hz=center_freq_hz,
                sample_rate_hz=sample_rate_hz,
                lna_gain=lna_gain,
                vga_gain=vga_gain,
                rf_amp_enable=rf_amp_enable,
                rf_bias_tee_enable=rf_bias_tee_enable,
                baseband_filter_bw_hz=float(baseband_filter_bw_hz),
            )
            self._mark_rx_gains_applied()
            if freq_changed or rate_changed or bb_changed:
                return True, self._status_message(backend="libhackrf")
            return True, "Sin cambios"
        except RuntimeError as exc:
            self._restore_rx_targets_from_applied()
            self._error = str(exc)
            return False, str(exc)

    def read_iq_snapshot(self, num_samples: int, *, wait_sec: float = 0.08) -> Optional[bytes]:
        """Últimas N muestras IQ — para FFT (no consume el buffer de audio)."""
        num_samples = max(1, min(int(num_samples), IQ_RING_MAX_SAMPLES))
        deadline = time.monotonic() + wait_sec
        while time.monotonic() < deadline:
            if self._error:
                return None
            if not self.is_running:
                return None
            block = self._fft_buffer.read_latest(num_samples)
            if block is not None:
                return block
            time.sleep(0.003)
        if self._error or not self.is_running:
            return None
        return None

    def read_iq_consume(self, num_samples: int, *, wait_sec: float = 0.02) -> Optional[bytes]:
        """Muestras IQ secuenciales — para demodulación de audio continua."""
        num_samples = max(1, min(int(num_samples), IQ_DEMOD_MAX_SAMPLES))
        deadline = time.monotonic() + wait_sec
        while time.monotonic() < deadline:
            if self._error:
                return None
            if not self.is_running:
                return None
            block = self._demod_buffer.read_consume(num_samples)
            if block is not None:
                return block
            time.sleep(0.002)
        return None

    def demod_pending_samples(self) -> int:
        return self._demod_buffer.pending_samples()

    def consume_demod_gap_flag(self) -> bool:
        if self._demod_buffer.gap_detected:
            self._demod_buffer.gap_detected = False
            return True
        return False

    def read_iq_block(self, num_samples: int, *, wait_sec: float = 0.08) -> Optional[bytes]:
        return self.read_iq_snapshot(num_samples, wait_sec=wait_sec)

    def _read_process_error(self) -> Optional[str]:
        proc = self._proc
        if proc is None or proc.stderr is None:
            return self._error
        try:
            raw = proc.stderr.read(4096)
            if raw:
                text = raw.decode("utf-8", errors="replace").strip()
                if text:
                    return text.splitlines()[0][:300]
        except OSError:
            pass
        return self._error

    def _read_loop(self) -> None:
        proc = self._proc
        if proc is None or proc.stdout is None:
            return
        try:
            while not self._stop.is_set() and proc.poll() is None:
                chunk = proc.stdout.read(65536)
                if not chunk:
                    if proc.poll() is not None:
                        if not self._stop.is_set():
                            detail = self._read_process_error()
                            self._error = detail or "Stream IQ detenido"
                        self._fft_buffer.clear()
                        self._demod_buffer.clear()
                    break
                self._fft_buffer.write(chunk)
                self._demod_buffer.write(chunk)
        except OSError as exc:
            self._error = str(exc)
            self._fft_buffer.clear()
            self._demod_buffer.clear()


def _clamp_sample_rate(sample_rate_hz: float) -> float:
    from core.monitor.display_scale import snap_iq_sample_rate_hz

    return snap_iq_sample_rate_hz(float(sample_rate_hz))
