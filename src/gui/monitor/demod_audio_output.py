"""Salida de audio demodulado vía QAudioSink (PyQt6)."""
from __future__ import annotations

import threading
from typing import Optional

import numpy as np
from PyQt6.QtCore import QObject, QThread

from core.monitor.demod_dsp import AUDIO_RATE_HZ

try:
    from PyQt6.QtMultimedia import QAudioFormat, QAudioSink, QMediaDevices
except ImportError:  # pragma: no cover
    QAudioFormat = None  # type: ignore
    QAudioSink = None  # type: ignore
    QMediaDevices = None  # type: ignore

_PCM_BUFFER_SEC = 1.0


class _AudioPumpThread(QThread):
    def __init__(self, output: "DemodAudioOutput") -> None:
        super().__init__()
        self._output = output

    def run(self) -> None:
        while not self.isInterruptionRequested():
            self._output._pump_once()
            self.msleep(2)


class DemodAudioOutput(QObject):
    """Cola PCM thread-safe → QAudioSink (hilo de pump dedicado)."""

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._sink: Optional[QAudioSink] = None
        self._io = None
        self._pending = bytearray()
        self._lock = threading.Lock()
        self._volume = 0.8
        self._last_error = ""
        self._use_int16 = False
        self._bytes_per_sample = 4
        self._channel_count = 1
        self._pump_thread: Optional[_AudioPumpThread] = None

    @property
    def is_active(self) -> bool:
        return self._sink is not None

    @property
    def last_error(self) -> str:
        return self._last_error

    def set_volume(self, volume: float) -> None:
        self._volume = max(0.0, min(1.0, float(volume)))

    def start(self, *, stereo: bool = False) -> bool:
        if QAudioSink is None or QMediaDevices is None:
            self._last_error = "QtMultimedia no disponible"
            return False
        channels = 2 if stereo else 1
        if self._sink is not None and self._channel_count == channels:
            return True
        if self._sink is not None:
            self.stop()
        device = QMediaDevices.defaultAudioOutput()
        if device.isNull():
            self._last_error = "Sin dispositivo de audio de salida"
            return False
        fmt = QAudioFormat()
        fmt.setSampleRate(int(AUDIO_RATE_HZ))
        fmt.setChannelCount(channels)
        fmt.setSampleFormat(QAudioFormat.SampleFormat.Float)
        if not device.isFormatSupported(fmt):
            fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)
        self._use_int16 = fmt.sampleFormat() == QAudioFormat.SampleFormat.Int16
        self._channel_count = channels
        self._bytes_per_sample = max(1, fmt.bytesPerSample()) * channels
        self._sink = QAudioSink(device, fmt)
        self._sink.setVolume(1.0)
        try:
            buf = int(AUDIO_RATE_HZ * self._bytes_per_sample * 0.2)
            self._sink.setBufferSize(buf)
        except AttributeError:
            pass
        self._io = self._sink.start()
        self._last_error = ""
        self._pump_thread = _AudioPumpThread(self)
        self._pump_thread.start()
        return True

    def stop(self) -> None:
        if self._pump_thread is not None:
            self._pump_thread.requestInterruption()
            self._pump_thread.wait(1500)
            self._pump_thread = None
        with self._lock:
            self._pending.clear()
        if self._sink is not None:
            self._sink.stop()
        self._sink = None
        self._io = None

    def push_pcm(
        self,
        pcm: np.ndarray,
        *,
        squelch_open: bool,
        volume: float | None = None,
        stereo: bool = False,
    ) -> None:
        if pcm.size == 0:
            return
        if stereo and self._channel_count != 2:
            self.start(stereo=True)
        elif not stereo and self._channel_count != 1:
            self.start(stereo=False)
        vol = self._volume if volume is None else max(0.0, min(1.0, float(volume)))
        samples = np.asarray(pcm, dtype=np.float32).reshape(-1)
        if not squelch_open or vol <= 0.0:
            samples = np.zeros_like(samples)
        else:
            samples = np.clip(samples * vol, -1.0, 1.0)
        if self._use_int16:
            data = (samples * 32767.0).astype(np.int16).tobytes()
        else:
            data = samples.tobytes()
        max_bytes = int(AUDIO_RATE_HZ * self._bytes_per_sample * _PCM_BUFFER_SEC)
        with self._lock:
            self._pending.extend(data)
            if len(self._pending) > max_bytes:
                del self._pending[: len(self._pending) - max_bytes]

    def _pump_once(self) -> None:
        sink = self._sink
        io = self._io
        if sink is None or io is None:
            return
        for _ in range(12):
            free = int(sink.bytesFree())
            if free <= 0:
                break
            with self._lock:
                if not self._pending:
                    break
                nbytes = min(free, len(self._pending))
                chunk = bytes(self._pending[:nbytes])
                del self._pending[:nbytes]
            if io is not self._io:
                return
            io.write(chunk)
