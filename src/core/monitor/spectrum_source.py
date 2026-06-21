"""Fuentes IQ / FFT para el Monitor."""
from __future__ import annotations

import math
import subprocess
import sys
import time
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

import numpy as np

from core.monitor.device_discovery import SourceDescriptor, detect_sources as discover_sources
from core.monitor.hackrf_iq_capture import HackRfIqCapture
from core.monitor.spectrum_params import SpectrumFrame, SpectrumParams


class SpectrumSource(ABC):
    """Interfaz común: mock, HackRF, etc."""

    @property
    @abstractmethod
    def source_id(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def display_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def open(self) -> Tuple[bool, str]:
        """Abre el dispositivo. Devuelve (ok, mensaje)."""

    @abstractmethod
    def close(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def read_frame(self, params: SpectrumParams) -> SpectrumFrame:
        raise NotImplementedError

    def probe(self) -> Tuple[bool, str]:
        """Comprueba disponibilidad sin abrir de forma persistente."""
        return True, self.display_name


class MockSpectrumSource(SpectrumSource):
    """Generador sintético para desarrollo sin hardware."""

    source_id = "mock"
    display_name = "Simulación"

    def __init__(self) -> None:
        self._open = False
        self._t0 = time.monotonic()
        self._mock_sample_index = 0

    def _mock_iq_samples(
        self,
        params: SpectrumParams,
        *,
        num_samples: int,
        start_index: int = 0,
    ) -> np.ndarray:
        rate = max(float(params.sample_rate_hz), 1.0)
        idx = np.arange(start_index, start_index + num_samples, dtype=np.float64)
        t = idx / rate
        t_mono = time.monotonic() - self._t0
        offset_hz = float(params.vfo_freq_hz) - float(params.center_freq_hz)
        tone = np.exp(2j * np.pi * offset_hz * t)
        audio_mod = 0.55 * np.sin(2.0 * np.pi * 1000.0 * t + t_mono * 0.4)
        if (params.demod_mode or "fm").lower() == "am":
            carrier = 0.45 * (1.0 + 0.55 * audio_mod)
            samples = carrier * tone
        else:
            dev_hz = 12_000.0
            phase_mod = 2.0 * np.pi * dev_hz * np.cumsum(audio_mod) / rate
            samples = 0.45 * tone * np.exp(1j * phase_mod)
        noise = 0.03 * (np.random.randn(num_samples) + 1j * np.random.randn(num_samples))
        return (samples + noise).astype(np.complex64)

    def open(self) -> Tuple[bool, str]:
        self._open = True
        self._t0 = time.monotonic()
        self._mock_sample_index = 0
        return True, "Fuente simulada activa"

    def close(self) -> None:
        self._open = False

    def read_iq_stream(self, params: SpectrumParams, num_samples: int) -> Optional[np.ndarray]:
        if not self._open:
            self.open()
        n = max(32, int(num_samples))
        samples = self._mock_iq_samples(
            params,
            num_samples=n,
            start_index=self._mock_sample_index,
        )
        self._mock_sample_index += n
        return samples

    def read_iq_snapshot(self, params: SpectrumParams, num_samples: int) -> Optional[np.ndarray]:
        if not self._open:
            self.open()
        n = max(256, int(num_samples))
        start = max(0, self._mock_sample_index - n)
        return self._mock_iq_samples(params, num_samples=n, start_index=start)

    def read_frame(self, params: SpectrumParams) -> SpectrumFrame:
        if not self._open:
            self.open()

        if params.capture_mode == "iq":
            from core.monitor.iq_fft import compute_spectrum_frame

            n_fft = max(256, params.fft_size)
            start = max(0, self._mock_sample_index - n_fft)
            samples = self._mock_iq_samples(
                params,
                num_samples=n_fft,
                start_index=start,
            )
            frame = compute_spectrum_frame(samples, params)
            return SpectrumFrame(
                freqs_hz=frame.freqs_hz,
                power_db=frame.power_db,
                center_freq_hz=params.center_freq_hz,
                span_hz=params.display_span_hz(),
                ref_level_dbm=params.ref_level_dbm,
                ref_range_db=params.ref_range_db,
            )

        n = max(256, params.fft_size)
        t = time.monotonic() - self._t0
        freqs = np.linspace(params.freq_start_hz(), params.freq_stop_hz(), n)
        noise = np.random.normal(-95.0, 2.0, n)

        peaks = (
            (params.center_freq_hz - params.span_hz * 0.25, -42.0, 0.0008),
            (params.center_freq_hz + params.span_hz * 0.1, -55.0 + 3.0 * math.sin(t * 0.7), 0.0012),
            (params.center_freq_hz + params.span_hz * 0.35, -48.0, 0.0006),
        )
        power = noise.copy()
        for peak_hz, level_dbm, width in peaks:
            power += level_dbm * np.exp(-0.5 * ((freqs - peak_hz) / (width * params.span_hz)) ** 2)

        power -= params.rf_attenuation_db
        return SpectrumFrame(
            freqs_hz=freqs,
            power_db=power,
            center_freq_hz=params.center_freq_hz,
            span_hz=params.span_hz,
            ref_level_dbm=params.ref_level_dbm,
            ref_range_db=params.ref_range_db,
        )


class HackRFSpectrumSource(SpectrumSource):
    """HackRF One — IQ continuo (≤20 MHz) o barrido (lapso analizador)."""

    source_id = "hackrf"
    display_name = "HackRF One"

    def __init__(self) -> None:
        self._capture = HackRfIqCapture()
        self._open = False
        self._stream_fail_until = 0.0
        self._capture_mode = "iq"

    def read_iq_stream(self, params: SpectrumParams, num_samples: int) -> Optional[np.ndarray]:
        if not self._open or params.capture_mode != "iq" or not self._capture.is_running:
            return None
        from core.monitor.iq_fft import iq_bytes_to_complex

        n = max(32, int(num_samples))
        block = self._capture.read_iq_consume(n, wait_sec=0.02)
        if block is None:
            return None
        return iq_bytes_to_complex(block, num_samples=n)

    def read_iq_snapshot(self, params: SpectrumParams, num_samples: int) -> Optional[np.ndarray]:
        if not self._open or params.capture_mode != "iq" or not self._capture.is_running:
            return None
        from core.monitor.iq_fft import iq_bytes_to_complex

        n = max(256, int(num_samples))
        block = self._capture.read_iq_snapshot(n, wait_sec=0.05)
        if block is None:
            return None
        return iq_bytes_to_complex(block, num_samples=n)

    def consume_iq_gap_flag(self) -> bool:
        if self._capture.consume_demod_gap_flag():
            return True
        return False

    def iq_stream_pending_samples(self) -> int:
        return self._capture.demod_pending_samples()

    def release_iq_stream(self) -> None:
        self._capture.stop()
        time.sleep(0.55 if sys.platform == "win32" else 0.35)

    def recover_iq_stream(self, params: SpectrumParams) -> Tuple[bool, str]:
        """Reinicio completo del stream IQ tras fallo de ganancia o USB ocupado."""
        self.release_iq_stream()
        if params.capture_mode == "sweep":
            return True, "Modo barrido"
        params.sync_iq_display()
        ok, msg = self._capture.restart_if_needed(
            center_freq_hz=params.center_freq_hz,
            sample_rate_hz=params.sample_rate_hz,
            lna_gain=params.lna_gain_db,
            vga_gain=params.vga_gain_db,
            rf_amp_enable=params.rf_amp_enable,
            rf_bias_tee_enable=params.rf_bias_tee_enable,
            baseband_filter_bw_hz=params.baseband_filter_bw_hz,
        )
        if ok:
            return True, msg
        return False, msg or "Stream IQ detenido — reinicie captura (STOP/PLAY)"

    def prepare_capture_mode(self, params: SpectrumParams) -> None:
        mode = params.capture_mode
        if mode == self._capture_mode:
            return
        if mode == "sweep" or self._capture_mode == "sweep":
            self.release_iq_stream()
        self._capture_mode = mode

    def probe(self) -> Tuple[bool, str]:
        from core.monitor.device_discovery import enumerate_hackrf_usb
        from core.monitor.hackrf_paths import resolve_hackrf_tool

        usb = enumerate_hackrf_usb()
        if not usb:
            return False, "HackRF no detectado por USB"
        dev = usb[0]
        transfer = resolve_hackrf_tool("hackrf_transfer")
        usb_msg = f"{dev.friendly_name} · USB {dev.status}"
        if dev.serial:
            usb_msg += f" · S/N {dev.serial}"
        if transfer:
            return True, f"{usb_msg} · hackrf_transfer OK"
        return True, f"{usb_msg} · instale libhackrf (scripts/install_hackrf_windows.ps1)"

    def open(self) -> Tuple[bool, str]:
        from core.monitor.device_discovery import enumerate_hackrf_usb
        from core.monitor.hackrf_paths import ensure_hackrf_on_path, resolve_hackrf_tool

        ensure_hackrf_on_path()
        transfer = resolve_hackrf_tool("hackrf_transfer")
        if not transfer:
            return False, "hackrf_transfer no encontrado — ejecute install_hackrf_windows.ps1"
        usb = enumerate_hackrf_usb()
        if not usb:
            return False, "HackRF no detectado por USB"
        self._open = True
        return True, "HackRF listo (modo IQ nativo)"

    def close(self) -> None:
        self.release_iq_stream()
        self._open = False

    def configure_stream(self, params: SpectrumParams) -> Tuple[bool, str]:
        if not self._open:
            return False, "HackRF no abierto"
        if params.capture_mode == "sweep":
            self.release_iq_stream()
            return True, "Modo barrido"
        params.apply_span_as_sample_rate()
        params.sync_iq_display()
        return self._capture.restart_if_needed(
            center_freq_hz=params.center_freq_hz,
            sample_rate_hz=params.sample_rate_hz,
            lna_gain=params.lna_gain_db,
            vga_gain=params.vga_gain_db,
            rf_amp_enable=params.rf_amp_enable,
            rf_bias_tee_enable=params.rf_bias_tee_enable,
            baseband_filter_bw_hz=params.baseband_filter_bw_hz,
        )

    def read_frame(self, params: SpectrumParams) -> SpectrumFrame:
        if not self._open:
            ok, msg = self.open()
            if not ok:
                raise RuntimeError(msg)

        self.prepare_capture_mode(params)

        if params.capture_mode == "sweep":
            from core.monitor.hackrf_sweep_source import run_hackrf_sweep

            try:
                return run_hackrf_sweep(params)
            except RuntimeError as exc:
                if "ocupado" in str(exc).lower() or "busy" in str(exc).lower():
                    self.release_iq_stream()
                raise

        if not self._capture.is_running:
            now = time.monotonic()
            if now < self._stream_fail_until:
                raise RuntimeError("Iniciando captura IQ…")
            ok, msg = self.configure_stream(params)
            if not ok:
                self._stream_fail_until = now + 1.5
                raise RuntimeError(msg)
            self._stream_fail_until = 0.0
        if not self._capture.is_running:
            raise RuntimeError("Reiniciando captura IQ…")
        from core.monitor.iq_fft import compute_spectrum_frame, iq_bytes_to_complex

        n_fft = max(256, params.fft_size)
        block = self._capture.read_iq_block(n_fft, wait_sec=0.35)
        if block is None:
            block = self._capture.read_iq_block(n_fft, wait_sec=1.0)
        if block is None:
            if not self._capture.is_running:
                raise RuntimeError("Reiniciando captura IQ…")
            err = self._capture.last_error or "Sin muestras IQ"
            raise RuntimeError(err)
        if not self._capture.is_running:
            raise RuntimeError("Reiniciando captura IQ…")
        samples_fft = iq_bytes_to_complex(block, num_samples=n_fft)
        frame = compute_spectrum_frame(samples_fft, params)
        frame = SpectrumFrame(
            freqs_hz=frame.freqs_hz,
            power_db=frame.power_db,
            center_freq_hz=params.center_freq_hz,
            span_hz=params.display_span_hz(),
            ref_level_dbm=params.ref_level_dbm,
            ref_range_db=params.ref_range_db,
        )
        return frame


class _NativeSdrStub(SpectrumSource):
    """Base para backends nativos aún no integrados del todo."""

    def __init__(self, *, source_id: str, display_name: str, setup_hint: str) -> None:
        self._source_id = source_id
        self._display_name = display_name
        self._setup_hint = setup_hint
        self._open = False

    @property
    def source_id(self) -> str:
        return self._source_id

    @property
    def display_name(self) -> str:
        return self._display_name

    def probe(self) -> Tuple[bool, str]:
        from core.monitor.sdr_setup import build_device_setup_report, get_device_spec

        spec = get_device_spec(self._source_id)
        if not spec:
            return False, self._setup_hint
        from core.monitor.device_discovery import enumerate_usb_for_spec

        usb = enumerate_usb_for_spec(spec)
        labels = [f"{d.friendly_name} ({d.serial or d.status})" for d in usb]
        report = build_device_setup_report(spec, usb_devices=labels, probe_python=False)
        if report.ready_for_capture:
            return True, report.usb.detail
        if usb:
            return True, f"{report.usb.detail} · {self._setup_hint}"
        return False, report.usb.detail

    def open(self) -> Tuple[bool, str]:
        from core.monitor.sdr_setup import build_device_setup_report, get_device_spec

        spec = get_device_spec(self._source_id)
        if not spec:
            return False, self._setup_hint
        from core.monitor.device_discovery import enumerate_usb_for_spec

        usb = enumerate_usb_for_spec(spec)
        labels = [f"{d.friendly_name} ({d.serial or d.status})" for d in usb]
        report = build_device_setup_report(spec, usb_devices=labels, probe_python=True)
        if not usb:
            return False, "Equipo no detectado por USB"
        if not report.ready_for_capture:
            return False, f"Instale driver/backend — {self._setup_hint}"
        self._open = True
        return False, f"Backend IQ pendiente para {self._display_name} (use Simulación mientras tanto)"

    def close(self) -> None:
        self._open = False

    def read_frame(self, params: SpectrumParams) -> SpectrumFrame:
        raise RuntimeError(f"Captura IQ no implementada aún para {self._display_name}")


class AirspySpectrumSource(_NativeSdrStub):
    def __init__(self) -> None:
        super().__init__(
            source_id="airspy",
            display_name="Airspy R2 / Mini",
            setup_hint="Use el asistente FUENTE (libairspy / airspy_info)",
        )


class AirspyHfSpectrumSource(_NativeSdrStub):
    def __init__(self) -> None:
        super().__init__(
            source_id="airspy_hf",
            display_name="Airspy HF+",
            setup_hint="Use el asistente FUENTE (libairspyhf / airspy_info)",
        )


def create_spectrum_source(source_id: str) -> SpectrumSource:
    from core.monitor.sdr_setup import map_source_id_to_device_id

    base = map_source_id_to_device_id(source_id)
    if base == "hackrf":
        return HackRFSpectrumSource()
    if base == "airspy":
        return AirspySpectrumSource()
    if base == "airspy_hf":
        return AirspyHfSpectrumSource()
    return MockSpectrumSource()


def detect_sources(*, probe_backend: bool = False) -> List[SourceDescriptor]:
    """Lista fuentes conocidas (USB rápido; backend opcional)."""
    return discover_sources(probe_backend=probe_backend)
