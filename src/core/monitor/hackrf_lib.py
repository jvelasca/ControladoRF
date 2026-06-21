"""libhackrf vía ctypes — RX continuo y ganancias en caliente (como SDR++)."""
from __future__ import annotations

import ctypes
import sys
import threading
from pathlib import Path
from typing import Callable, Optional

from core.monitor.hackrf_paths import ensure_hackrf_on_path, resolve_hackrf_bin_dir

HACKRF_SUCCESS = 0


class HackRfTransfer(ctypes.Structure):
    _fields_ = [
        ("device", ctypes.c_void_p),
        ("buffer", ctypes.POINTER(ctypes.c_uint8)),
        ("buffer_length", ctypes.c_int),
        ("valid_length", ctypes.c_int),
        ("rx_ctx", ctypes.c_void_p),
    ]


HackRfCallbackType = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.POINTER(HackRfTransfer))

_lib: Optional[ctypes.CDLL] = None
_lib_lock = threading.Lock()
_init_refs = 0


def resolve_hackrf_dll() -> Optional[Path]:
    ensure_hackrf_on_path()
    bin_dir = resolve_hackrf_bin_dir()
    if not bin_dir:
        return None
    if sys.platform == "win32":
        names = ("hackrf.dll", "libhackrf.dll")
    elif sys.platform == "darwin":
        names = ("libhackrf.dylib", "hackrf.dylib")
    else:
        names = ("libhackrf.so.0", "libhackrf.so", "hackrf.so")
    for name in names:
        candidate = bin_dir / name
        if candidate.is_file():
            return candidate
    return None


def load_hackrf_lib() -> Optional[ctypes.CDLL]:
    global _lib
    if _lib is not None:
        return _lib
    dll_path = resolve_hackrf_dll()
    if dll_path is None:
        return None
    try:
        if sys.platform == "win32":
            lib = ctypes.WinDLL(str(dll_path))
        else:
            lib = ctypes.CDLL(str(dll_path))
    except OSError:
        return None
    lib.hackrf_init.argtypes = []
    lib.hackrf_init.restype = ctypes.c_int
    lib.hackrf_exit.argtypes = []
    lib.hackrf_exit.restype = ctypes.c_int
    lib.hackrf_open.argtypes = [ctypes.POINTER(ctypes.c_void_p)]
    lib.hackrf_open.restype = ctypes.c_int
    lib.hackrf_close.argtypes = [ctypes.c_void_p]
    lib.hackrf_close.restype = ctypes.c_int
    lib.hackrf_set_freq.argtypes = [ctypes.c_void_p, ctypes.c_uint64]
    lib.hackrf_set_freq.restype = ctypes.c_int
    lib.hackrf_set_sample_rate.argtypes = [ctypes.c_void_p, ctypes.c_double]
    lib.hackrf_set_sample_rate.restype = ctypes.c_int
    lib.hackrf_set_baseband_filter_bandwidth.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    lib.hackrf_set_baseband_filter_bandwidth.restype = ctypes.c_int
    lib.hackrf_set_lna_gain.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    lib.hackrf_set_lna_gain.restype = ctypes.c_int
    lib.hackrf_set_vga_gain.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    lib.hackrf_set_vga_gain.restype = ctypes.c_int
    lib.hackrf_set_amp_enable.argtypes = [ctypes.c_void_p, ctypes.c_uint8]
    lib.hackrf_set_amp_enable.restype = ctypes.c_int
    if hasattr(lib, "hackrf_set_antenna_enable"):
        lib.hackrf_set_antenna_enable.argtypes = [ctypes.c_void_p, ctypes.c_uint8]
        lib.hackrf_set_antenna_enable.restype = ctypes.c_int
    lib.hackrf_start_rx.argtypes = [ctypes.c_void_p, HackRfCallbackType, ctypes.c_void_p]
    lib.hackrf_start_rx.restype = ctypes.c_int
    lib.hackrf_stop_rx.argtypes = [ctypes.c_void_p]
    lib.hackrf_stop_rx.restype = ctypes.c_int
    lib.hackrf_is_streaming.argtypes = [ctypes.c_void_p]
    lib.hackrf_is_streaming.restype = ctypes.c_int
    _lib = lib
    return lib


def libhackrf_available() -> bool:
    return load_hackrf_lib() is not None


def _check(code: int, action: str) -> None:
    if code != HACKRF_SUCCESS:
        raise RuntimeError(f"libhackrf {action} error {code}")


class HackRfLibSession:
    """Sesión RX libhackrf — un dispositivo, callback IQ continuo."""

    def __init__(self) -> None:
        self._device = ctypes.c_void_p()
        self._dev_ptr: Optional[ctypes.c_void_p] = None
        self._callback: Optional[HackRfCallbackType] = None
        self._open = False
        self._streaming = False

    @property
    def is_open(self) -> bool:
        return self._open and self._dev_ptr is not None

    @property
    def is_streaming(self) -> bool:
        return self._streaming

    def open(self) -> None:
        lib = load_hackrf_lib()
        if lib is None:
            raise RuntimeError("libhackrf no disponible")
        global _init_refs
        with _lib_lock:
            if _init_refs == 0:
                _check(lib.hackrf_init(), "init")
            _init_refs += 1
        self._device = ctypes.c_void_p()
        _check(lib.hackrf_open(ctypes.byref(self._device)), "open")
        self._dev_ptr = self._device
        self._open = True

    def close(self) -> None:
        global _init_refs
        lib = load_hackrf_lib()
        if lib is None:
            return
        self.stop_rx()
        if self._dev_ptr is not None:
            try:
                lib.hackrf_close(self._dev_ptr)
            except OSError:
                pass
        self._dev_ptr = None
        self._open = False
        with _lib_lock:
            if _init_refs > 0:
                _init_refs -= 1
                if _init_refs == 0:
                    try:
                        lib.hackrf_exit()
                    except OSError:
                        pass

    def configure(
        self,
        *,
        center_freq_hz: float,
        sample_rate_hz: float,
        lna_gain: int,
        vga_gain: int,
        rf_amp_enable: bool,
        rf_bias_tee_enable: bool,
        baseband_filter_bw_hz: int,
    ) -> None:
        if not self.is_open or self._dev_ptr is None:
            raise RuntimeError("HackRF no abierto")
        lib = load_hackrf_lib()
        assert lib is not None
        dev = self._dev_ptr
        _check(lib.hackrf_set_freq(dev, ctypes.c_uint64(int(center_freq_hz))), "set_freq")
        _check(lib.hackrf_set_sample_rate(dev, ctypes.c_double(float(sample_rate_hz))), "set_sample_rate")
        _check(
            lib.hackrf_set_baseband_filter_bandwidth(dev, ctypes.c_uint32(int(baseband_filter_bw_hz))),
            "set_baseband_filter",
        )
        _check(lib.hackrf_set_lna_gain(dev, ctypes.c_uint32(int(lna_gain))), "set_lna_gain")
        _check(lib.hackrf_set_vga_gain(dev, ctypes.c_uint32(int(vga_gain))), "set_vga_gain")
        _check(lib.hackrf_set_amp_enable(dev, ctypes.c_uint8(1 if rf_amp_enable else 0)), "set_amp_enable")
        if hasattr(lib, "hackrf_set_antenna_enable"):
            _check(
                lib.hackrf_set_antenna_enable(dev, ctypes.c_uint8(1 if rf_bias_tee_enable else 0)),
                "set_antenna_enable",
            )

    def apply_gains(
        self,
        *,
        lna_gain: int,
        vga_gain: int,
        rf_amp_enable: bool,
        rf_bias_tee_enable: bool,
    ) -> None:
        if not self.is_open or self._dev_ptr is None:
            raise RuntimeError("HackRF no abierto")
        lib = load_hackrf_lib()
        assert lib is not None
        dev = self._dev_ptr
        _check(lib.hackrf_set_lna_gain(dev, ctypes.c_uint32(int(lna_gain))), "set_lna_gain")
        _check(lib.hackrf_set_vga_gain(dev, ctypes.c_uint32(int(vga_gain))), "set_vga_gain")
        _check(lib.hackrf_set_amp_enable(dev, ctypes.c_uint8(1 if rf_amp_enable else 0)), "set_amp_enable")
        if hasattr(lib, "hackrf_set_antenna_enable"):
            _check(
                lib.hackrf_set_antenna_enable(dev, ctypes.c_uint8(1 if rf_bias_tee_enable else 0)),
                "set_antenna_enable",
            )

    def apply_center_freq(self, center_freq_hz: float) -> None:
        if not self.is_open or self._dev_ptr is None:
            raise RuntimeError("HackRF no abierto")
        lib = load_hackrf_lib()
        assert lib is not None
        _check(
            lib.hackrf_set_freq(self._dev_ptr, ctypes.c_uint64(int(center_freq_hz))),
            "set_freq",
        )

    def start_rx(self, on_chunk: Callable[[bytes], None]) -> None:
        if not self.is_open or self._dev_ptr is None:
            raise RuntimeError("HackRF no abierto")
        lib = load_hackrf_lib()
        assert lib is not None

        @HackRfCallbackType
        def _callback(transfer_ptr: ctypes.POINTER(HackRfTransfer)) -> int:
            transfer = transfer_ptr.contents
            length = int(transfer.valid_length)
            if length > 0 and transfer.buffer:
                chunk = ctypes.string_at(transfer.buffer, length)
                on_chunk(chunk)
            return 0

        self._callback = _callback
        _check(lib.hackrf_start_rx(self._dev_ptr, self._callback, None), "start_rx")
        self._streaming = True

    def stop_rx(self) -> None:
        if not self.is_open or self._dev_ptr is None or not self._streaming:
            self._streaming = False
            return
        lib = load_hackrf_lib()
        if lib is None:
            self._streaming = False
            return
        try:
            lib.hackrf_stop_rx(self._dev_ptr)
        except OSError:
            pass
        self._streaming = False
