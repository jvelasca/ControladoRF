"""Grabación Monitor — baseband IQ (cf32) y audio demodulado (WAV)."""
from __future__ import annotations

import threading
import wave
from datetime import datetime
from pathlib import Path

import numpy as np

from core.monitor.demod_dsp import AUDIO_RATE_HZ
from core.monitor.spectrum_params import SpectrumParams

EXPORT_RECORD_BASEBAND = "monitor_record_baseband"
EXPORT_RECORD_AUDIO = "monitor_record_audio"


def default_recorder_directory(mode: str) -> Path:
    from core.monitor.monitor_export_paths import export_directory

    key = EXPORT_RECORD_BASEBAND if mode == "baseband" else EXPORT_RECORD_AUDIO
    return export_directory(key)


def build_recording_filename(params: SpectrumParams, mode: str, *, when: datetime | None = None) -> str:
    """Nombre de fichero sugerido para la grabación actual."""
    stamp = (when or datetime.now()).strftime("%Y%m%d_%H%M%S")
    vfo_mhz = float(params.vfo_freq_hz) / 1e6
    if mode == "audio":
        demod = (params.demod_mode or "wfm").lower()
        return f"audio_{vfo_mhz:.3f}MHz_{demod}_{stamp}.wav"
    rate_mhz = float(params.sample_rate_hz) / 1e6
    return f"bb_{vfo_mhz:.3f}MHz_{rate_mhz:.2f}Msps_{stamp}.cf32"


def resolve_recording_path(params: SpectrumParams, mode: str) -> Path:
    directory = (params.recorder_directory or "").strip()
    folder = Path(directory).expanduser() if directory else default_recorder_directory(mode)
    name = (params.recorder_filename or "").strip() or build_recording_filename(params, mode)
    return folder / Path(name).name


class MonitorRecorder:
    """Escritor de fichero thread-safe activado desde el hilo demod."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._mode = ""
        self._path: Path | None = None
        self._wav: wave.Wave_write | None = None
        self._bin_file = None
        self._active = False

    @property
    def is_active(self) -> bool:
        with self._lock:
            return self._active

    @property
    def mode(self) -> str:
        with self._lock:
            return self._mode

    @property
    def path(self) -> Path | None:
        with self._lock:
            return self._path

    def start(self, path: Path, mode: str) -> tuple[bool, str]:
        mode = str(mode or "baseband").lower()
        if mode not in ("baseband", "audio"):
            return False, "invalid_mode"
        target = Path(path).expanduser()
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return False, str(exc)
        with self._lock:
            if self._active:
                return False, "already_recording"
            try:
                if mode == "audio":
                    wav = wave.open(str(target), "wb")
                    wav.setnchannels(1)
                    wav.setsampwidth(2)
                    wav.setframerate(int(AUDIO_RATE_HZ))
                    self._wav = wav
                    self._bin_file = None
                else:
                    handle = open(target, "wb")
                    self._bin_file = handle
                    self._wav = None
            except OSError as exc:
                self._wav = None
                self._bin_file = None
                return False, str(exc)
            self._mode = mode
            self._path = target
            self._active = True
        return True, ""

    def stop(self) -> Path | None:
        with self._lock:
            path = self._path
            if self._wav is not None:
                try:
                    self._wav.close()
                except Exception:
                    pass
            if self._bin_file is not None:
                try:
                    self._bin_file.close()
                except Exception:
                    pass
            self._wav = None
            self._bin_file = None
            self._active = False
            self._mode = ""
            self._path = None
            return path

    def write_iq(self, samples) -> None:
        arr = np.asarray(samples, dtype=np.complex64).reshape(-1)
        if arr.size == 0:
            return
        payload = np.asarray(arr, dtype=np.complex64).reshape(-1).view(np.float32).tobytes()
        with self._lock:
            if not self._active or self._mode != "baseband" or self._bin_file is None:
                return
            self._bin_file.write(payload)

    def write_pcm(self, pcm: np.ndarray) -> None:
        arr = np.asarray(pcm, dtype=np.float32).reshape(-1)
        if arr.size == 0:
            return
        clipped = np.clip(arr, -1.0, 1.0)
        int16 = (clipped * 32767.0).astype(np.int16)
        payload = int16.tobytes()
        with self._lock:
            if not self._active or self._mode != "audio" or self._wav is None:
                return
            self._wav.writeframes(payload)
