"""Enlace serie mínimo para analizadores USB (RF Explorer, TinySA)."""
from __future__ import annotations

import time
from typing import Protocol, runtime_checkable


class SerialUnavailableError(RuntimeError):
    """pyserial no instalado o puerto inaccesible."""


@runtime_checkable
class SerialTransport(Protocol):
    def write(self, data: bytes) -> int: ...

    def readline(self) -> bytes: ...

    def read(self, size: int = 1) -> bytes: ...

    def reset_input_buffer(self) -> None: ...

    def close(self) -> None: ...


class PySerialTransport:
    """Adaptador sobre pyserial.Serial."""

    def __init__(self, port: str, baud: int, *, timeout: float = 2.0) -> None:
        try:
            import serial  # type: ignore[import-untyped]
        except ImportError as exc:
            raise SerialUnavailableError(
                "Instale pyserial (pip install pyserial) para usar analizadores por puerto serie"
            ) from exc
        self._port = port
        self._ser = serial.Serial(
            port=port,
            baudrate=baud,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=timeout,
            write_timeout=timeout,
        )

    @property
    def port(self) -> str:
        return self._port

    def write(self, data: bytes) -> int:
        return int(self._ser.write(data))

    def readline(self) -> bytes:
        return bytes(self._ser.readline())

    def read(self, size: int = 1) -> bytes:
        return bytes(self._ser.read(size))

    def reset_input_buffer(self) -> None:
        self._ser.reset_input_buffer()

    def close(self) -> None:
        if self._ser.is_open:
            self._ser.close()


class SerialLink:
    """Fachada de lectura/escritura con timeouts acumulados."""

    def __init__(
        self,
        port: str,
        baud: int,
        *,
        transport: SerialTransport | None = None,
        default_timeout: float = 2.0,
    ) -> None:
        self._transport = transport or PySerialTransport(port, baud, timeout=default_timeout)
        self.port = port
        self.baud = baud

    def open(self) -> None:
        return

    def close(self) -> None:
        self._transport.close()

    def write_line(self, text: str) -> None:
        payload = text if text.endswith("\n") else f"{text}\n"
        self._transport.write(payload.encode("ascii", errors="ignore"))

    def write_bytes(self, data: bytes) -> None:
        self._transport.write(data)

    def reset_input(self) -> None:
        self._transport.reset_input_buffer()

    def read_line(self, *, timeout_sec: float = 2.0) -> str:
        deadline = time.monotonic() + max(0.05, timeout_sec)
        while time.monotonic() < deadline:
            line = self._transport.readline()
            if line:
                return line.decode("ascii", errors="ignore").strip()
            time.sleep(0.01)
        return ""

    def read_lines_until(
        self,
        *,
        timeout_sec: float,
        stop_when,
        max_lines: int = 4096,
    ) -> list[str]:
        lines: list[str] = []
        deadline = time.monotonic() + max(0.05, timeout_sec)
        while time.monotonic() < deadline and len(lines) < max_lines:
            line = self.read_line(timeout_sec=min(0.25, deadline - time.monotonic()))
            if not line:
                continue
            lines.append(line)
            if stop_when(line, lines):
                break
        return lines
