"""Entrada por canal — resolución Hz ↔ canal (modo global APP)."""
from __future__ import annotations

import re
from typing import Optional

from core.rf.channelization_service import ChannelizationService
from db.models.rf_standard import RfStandardChannel

_LABEL_RE = re.compile(r"^(?:CH|FM|CANAL)?\s*(\d+)\s*$", re.IGNORECASE)


def pick_standard_for_frequency(
    service: ChannelizationService, freq_hz: float
) -> Optional[str]:
    """Elige el estándar activo que contiene la frecuencia."""
    state = service.get_state()
    best_id: Optional[str] = None
    best_dist = float("inf")
    for std_id in state.active_standard_ids:
        std = service.get_standard(std_id)
        if std is None or not std.enabled:
            continue
        if std.freq_min_hz is not None and freq_hz < std.freq_min_hz - 1.0:
            continue
        if std.freq_max_hz is not None and freq_hz > std.freq_max_hz + 1.0:
            continue
        ch = service.find_nearest_channel(std_id, freq_hz)
        if ch is None:
            continue
        dist = abs(ch.center_freq_hz - freq_hz)
        if dist < best_dist:
            best_dist = dist
            best_id = std_id
    return best_id


def channel_label_for_frequency(
    service: ChannelizationService,
    freq_hz: float,
    *,
    standard_id: str | None = None,
) -> Optional[str]:
    """Etiqueta corta del canal (p. ej. FM39) o None si no hay estándar."""
    std_id = standard_id or pick_standard_for_frequency(service, freq_hz)
    if not std_id:
        return None
    ch = service.find_nearest_channel(std_id, freq_hz)
    if ch is None:
        return None
    if ch.channel_label:
        return ch.channel_label
    if ch.channel_number is not None:
        return str(ch.channel_number)
    return None


def format_channel_display(
    service: ChannelizationService,
    freq_hz: float,
    *,
    standard_id: str | None = None,
) -> str:
    label = channel_label_for_frequency(
        service, freq_hz, standard_id=standard_id
    )
    if label:
        return label
    return f"{freq_hz / 1_000_000:.6f}"


def format_channel_toolbar_title(
    service: ChannelizationService,
    freq_hz: float,
    *,
    standard_id: str | None = None,
) -> str:
    """Título del cuadro FC en modo canal — «Canal; FM39» (frecuencia solo en el spin)."""
    from i18n.json_translation import tr

    base = tr("monitor_lcd_channel")
    label = channel_label_for_frequency(
        service, freq_hz, standard_id=standard_id
    )
    if label:
        return f"{base}; {label}"
    return f"{base}; {freq_hz / 1_000_000:.6f}"


def format_channel_readout(
    service: ChannelizationService,
    freq_hz: float,
    *,
    standard_id: str | None = None,
    decimals: int = 6,
) -> str:
    """Lectura modo canal: MHz con etiqueta entre paréntesis — 87.600000 (FM39)."""
    mhz = f"{freq_hz / 1_000_000:.{decimals}f}"
    label = channel_label_for_frequency(
        service, freq_hz, standard_id=standard_id
    )
    if label:
        return f"{mhz} ({label})"
    return mhz


def _nearest_channel_index(
    channels: list[RfStandardChannel], freq_hz: float
) -> int:
    return min(
        range(len(channels)),
        key=lambda i: abs(channels[i].center_freq_hz - freq_hz),
    )


def snap_channel_frequency(
    service: ChannelizationService,
    freq_hz: float,
    *,
    standard_id: str | None = None,
) -> float:
    """Ajusta Hz al centro del canal más cercano del estándar activo."""
    std_id = standard_id or pick_standard_for_frequency(service, freq_hz)
    if not std_id:
        return float(freq_hz)
    channels = service.list_channels(std_id)
    if not channels:
        return float(freq_hz)
    best = min(channels, key=lambda ch: abs(ch.center_freq_hz - freq_hz))
    return float(best.center_freq_hz)


def step_channel_frequency(
    service: ChannelizationService,
    freq_hz: float,
    direction: int,
    *,
    standard_id: str | None = None,
) -> float:
    std_id = standard_id or pick_standard_for_frequency(service, freq_hz)
    if not std_id or direction == 0:
        return freq_hz
    channels = service.list_channels(std_id)
    if not channels:
        return freq_hz
    idx = _nearest_channel_index(channels, freq_hz)
    new_idx = max(0, min(len(channels) - 1, idx + int(direction)))
    return float(channels[new_idx].center_freq_hz)


def parse_channel_input(
    service: ChannelizationService,
    text: str,
    *,
    near_hz: float | None = None,
) -> Optional[float]:
    raw = (text or "").strip()
    if not raw:
        return None
    paren = raw.find("(")
    if paren > 0 and raw.endswith(")"):
        inner = raw[paren + 1 : -1].strip()
        if inner:
            resolved = parse_channel_input(
                service, inner, near_hz=near_hz
            )
            if resolved is not None:
                return resolved
        raw = raw[:paren].strip()
    state = service.get_state()
    upper = raw.upper()

    for std_id in state.active_standard_ids:
        ch = service.resolve_channel(std_id, label=raw)
        if ch is not None:
            return ch.center_freq_hz
        ch = service.resolve_channel(std_id, label=upper)
        if ch is not None:
            return ch.center_freq_hz

    match = _LABEL_RE.match(raw.replace(" ", ""))
    if match:
        number = int(match.group(1))
        for std_id in state.active_standard_ids:
            ch = service.resolve_channel(std_id, channel_number=number)
            if ch is not None:
                return ch.center_freq_hz

    try:
        mhz = float(raw.replace(",", "."))
    except ValueError:
        return None
    if mhz > 10_000:
        return mhz
    return mhz * 1_000_000.0 if near_hz is None or near_hz > 1_000_000 else mhz
