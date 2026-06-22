"""Identificadores de fuente RF — parsing y familias de equipo."""
from __future__ import annotations

from dataclasses import dataclass

ANALYZER_ONLY_DEVICES = frozenset({"rf_explorer", "tinysa"})


@dataclass(frozen=True)
class ParsedSourceId:
    """Fuente normalizada: familia, puerto serie opcional e índice USB."""

    raw: str
    device_id: str
    serial_port: str = ""
    instance_index: int = 0


def parse_source_id(source_id: str) -> ParsedSourceId:
    raw = (source_id or "mock").strip()
    if not raw or raw == "mock":
        return ParsedSourceId(raw="mock", device_id="mock")

    if "@" in raw:
        base, port = raw.split("@", 1)
        return ParsedSourceId(raw=raw, device_id=base.strip(), serial_port=port.strip())

    if raw.startswith("airspy_hf"):
        idx = _trailing_index(raw, prefix="airspy_hf")
        return ParsedSourceId(raw=raw, device_id="airspy_hf", instance_index=idx)

    if raw.startswith("airspy"):
        idx = _trailing_index(raw, prefix="airspy")
        return ParsedSourceId(raw=raw, device_id="airspy", instance_index=idx)

    if raw.startswith("hackrf"):
        idx = _trailing_index(raw, prefix="hackrf")
        return ParsedSourceId(raw=raw, device_id="hackrf", instance_index=idx)

    if raw.startswith("rf_explorer"):
        idx = _trailing_index(raw, prefix="rf_explorer")
        return ParsedSourceId(raw=raw, device_id="rf_explorer", instance_index=idx)

    if raw.startswith("tinysa"):
        idx = _trailing_index(raw, prefix="tinysa")
        return ParsedSourceId(raw=raw, device_id="tinysa", instance_index=idx)

    if "_" in raw:
        base, suffix = raw.rsplit("_", 1)
        if suffix.isdigit():
            return ParsedSourceId(raw=raw, device_id=base, instance_index=int(suffix))

    return ParsedSourceId(raw=raw, device_id=raw.split("_")[0])


def _trailing_index(raw: str, *, prefix: str) -> int:
    if raw == prefix:
        return 0
    rest = raw[len(prefix) :]
    if rest.startswith("_") and rest[1:].isdigit():
        return int(rest[1:])
    return 0


def device_family(source_id: str) -> str:
    return parse_source_id(source_id).device_id


def is_analyzer_only_source(source_id: str) -> bool:
    return device_family(source_id) in ANALYZER_ONLY_DEVICES


def format_serial_source_id(device_id: str, port: str, *, index: int = 0) -> str:
    base = f"{device_id}@{port}"
    if index > 0:
        return f"{device_id}_{index}@{port}"
    return base
