"""Banco de marcadores M1–M10 (medición sobre la traza)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

import numpy as np

from core.monitor.spectrum_params import SpectrumParams

MARKER_COUNT = 10
MARKER_MODES = ("normal", "delta", "fixed", "peak")

DEFAULT_MARKER_COLORS = (
    "#FFC850",
    "#50C8FF",
    "#50FF88",
    "#FF5088",
    "#C850FF",
    "#FF8850",
    "#88FF50",
    "#5088FF",
    "#FF50C8",
    "#C8FF50",
)


@dataclass
class MarkerDefinition:
    """Un marcador numerado (M1…M10)."""

    enabled: bool = False
    mode: str = "normal"
    freq_hz: float = 100_000_000.0
    ref_marker_id: int = 1
    color: str = "#FFC850"
    show_line: bool = True
    show_freq: bool = True
    show_level: bool = True
    show_snr: bool = False

    def copy(self) -> MarkerDefinition:
        return MarkerDefinition(
            enabled=self.enabled,
            mode=self.mode,
            freq_hz=float(self.freq_hz),
            ref_marker_id=int(self.ref_marker_id),
            color=str(self.color),
            show_line=self.show_line,
            show_freq=self.show_freq,
            show_level=self.show_level,
            show_snr=self.show_snr,
        )


def default_marker_bank(center_hz: float = 100_000_000.0) -> list[MarkerDefinition]:
    bank: list[MarkerDefinition] = []
    for index in range(MARKER_COUNT):
        bank.append(
            MarkerDefinition(
                enabled=False,
                freq_hz=float(center_hz),
                color=DEFAULT_MARKER_COLORS[index],
            )
        )
    return bank


def normalize_marker_mode(mode: str) -> str:
    value = str(mode or "normal").lower().strip()
    return value if value in MARKER_MODES else "normal"


def normalize_marker_color(color: str, *, index: int = 0) -> str:
    text = str(color or "").strip()
    if text.startswith("#") and len(text) in (4, 7):
        return text
    return DEFAULT_MARKER_COLORS[max(0, min(MARKER_COUNT - 1, index))]


def marker_definition_to_dict(marker: MarkerDefinition) -> dict[str, Any]:
    return {
        "enabled": bool(marker.enabled),
        "mode": normalize_marker_mode(marker.mode),
        "freq_hz": float(marker.freq_hz),
        "ref_marker_id": int(marker.ref_marker_id),
        "color": str(marker.color),
        "show_line": bool(marker.show_line),
        "show_freq": bool(marker.show_freq),
        "show_level": bool(marker.show_level),
        "show_snr": bool(marker.show_snr),
    }


def marker_definition_from_dict(data: dict[str, Any] | None, *, index: int, center_hz: float) -> MarkerDefinition:
    if not isinstance(data, dict):
        return MarkerDefinition(
            enabled=False,
            freq_hz=float(center_hz),
            color=DEFAULT_MARKER_COLORS[index],
        )
    return MarkerDefinition(
        enabled=bool(data.get("enabled", False)),
        mode=normalize_marker_mode(str(data.get("mode", "normal"))),
        freq_hz=float(data.get("freq_hz", center_hz)),
        ref_marker_id=max(1, min(MARKER_COUNT, int(data.get("ref_marker_id", 1)))),
        color=normalize_marker_color(str(data.get("color", DEFAULT_MARKER_COLORS[index])), index=index),
        show_line=bool(data.get("show_line", True)),
        show_freq=bool(data.get("show_freq", True)),
        show_level=bool(data.get("show_level", True)),
        show_snr=bool(data.get("show_snr", False)),
    )


def markers_to_dict(bank: Iterable[MarkerDefinition]) -> list[dict[str, Any]]:
    return [marker_definition_to_dict(marker) for marker in bank]


def markers_from_dict(data: list[Any] | None, *, center_hz: float) -> list[MarkerDefinition]:
    bank: list[MarkerDefinition] = []
    items = data if isinstance(data, list) else []
    for index in range(MARKER_COUNT):
        item = items[index] if index < len(items) else None
        if isinstance(item, dict):
            bank.append(marker_definition_from_dict(item, index=index, center_hz=center_hz))
        else:
            bank.append(
                MarkerDefinition(
                    enabled=index == 0,
                    freq_hz=float(center_hz),
                    color=DEFAULT_MARKER_COLORS[index],
                )
            )
    return bank


def get_marker(params: SpectrumParams, marker_id: int) -> MarkerDefinition | None:
    index = int(marker_id) - 1
    if index < 0 or index >= len(params.markers):
        return None
    return params.markers[index]


def find_peak_near(
    freqs: np.ndarray,
    power: np.ndarray,
    center_hz: float,
    *,
    half_window_hz: float = 500_000.0,
) -> float:
    if freqs is None or power is None or len(freqs) < 3:
        return float(center_hz)
    freqs_arr = np.asarray(freqs, dtype=float)
    power_arr = np.asarray(power, dtype=float)
    lo = float(center_hz) - half_window_hz
    hi = float(center_hz) + half_window_hz
    mask = (freqs_arr >= lo) & (freqs_arr <= hi)
    if not np.any(mask):
        return float(center_hz)
    local_freqs = freqs_arr[mask]
    local_power = power_arr[mask]
    return float(local_freqs[int(np.argmax(local_power))])


def resolve_marker_frequency_hz(
    params: SpectrumParams,
    marker_id: int,
    *,
    freqs: np.ndarray | None = None,
    power: np.ndarray | None = None,
    allow_peak_search: bool = True,
    _stack: set[int] | None = None,
) -> float | None:
    """Frecuencia absoluta del marcador, o None si está apagado o la referencia delta es inválida."""
    marker = get_marker(params, marker_id)
    if marker is None or not marker.enabled:
        return None

    mode = normalize_marker_mode(marker.mode)
    if mode == "delta":
        stack = set(_stack or ())
        if marker_id in stack:
            return None
        stack.add(marker_id)
        ref_id = int(marker.ref_marker_id)
        if ref_id == marker_id or ref_id < 1 or ref_id > MARKER_COUNT:
            return None
        ref_freq = resolve_marker_frequency_hz(
            params,
            ref_id,
            freqs=freqs,
            power=power,
            allow_peak_search=allow_peak_search,
            _stack=stack,
        )
        if ref_freq is None:
            return None
        return float(ref_freq) + float(marker.freq_hz)

    if mode == "peak" and allow_peak_search and freqs is not None and power is not None:
        return find_peak_near(freqs, power, marker.freq_hz)

    return float(marker.freq_hz)


def resolve_marker_level_db(
    params: SpectrumParams,
    marker_id: int,
    *,
    freqs: np.ndarray | None,
    power: np.ndarray | None,
) -> float | None:
    if freqs is None or power is None:
        return None
    freq = resolve_marker_frequency_hz(params, marker_id, freqs=freqs, power=power)
    if freq is None:
        return None
    from core.monitor.marker_analysis import interpolate_power_db

    return interpolate_power_db(freqs, power, freq)


def resolve_marker_delta(
    params: SpectrumParams,
    marker_id: int,
    *,
    freqs: np.ndarray | None,
    power: np.ndarray | None,
) -> tuple[float | None, float | None]:
    """ΔF (Hz) y Δ nivel (dB) respecto al marcador de referencia."""
    marker = get_marker(params, marker_id)
    if marker is None or normalize_marker_mode(marker.mode) != "delta":
        return None, None
    ref_id = int(marker.ref_marker_id)
    ref_freq = resolve_marker_frequency_hz(params, ref_id, freqs=freqs, power=power)
    marker_freq = resolve_marker_frequency_hz(params, marker_id, freqs=freqs, power=power)
    if ref_freq is None or marker_freq is None:
        return None, None
    delta_f = marker_freq - ref_freq
    ref_level = resolve_marker_level_db(params, ref_id, freqs=freqs, power=power)
    marker_level = resolve_marker_level_db(params, marker_id, freqs=freqs, power=power)
    delta_level = None
    if ref_level is not None and marker_level is not None:
        delta_level = marker_level - ref_level
    return delta_f, delta_level


def iter_drawable_markers(
    params: SpectrumParams,
    *,
    freqs: np.ndarray | None = None,
    power: np.ndarray | None = None,
    allow_peak_search: bool = True,
) -> list[tuple[int, MarkerDefinition, float]]:
    rows: list[tuple[int, MarkerDefinition, float]] = []
    for marker_id in range(1, MARKER_COUNT + 1):
        marker = get_marker(params, marker_id)
        if marker is None or not marker.enabled:
            continue
        freq = resolve_marker_frequency_hz(
            params,
            marker_id,
            freqs=freqs,
            power=power,
            allow_peak_search=allow_peak_search,
        )
        if freq is None:
            continue
        rows.append((marker_id, marker, freq))
    return rows


def sync_selected_freq_from_active_marker(params: SpectrumParams) -> None:
    marker = get_marker(params, params.active_marker_id)
    if marker is None or not marker.enabled:
        return
    if normalize_marker_mode(marker.mode) in ("normal", "fixed", "peak"):
        params.selected_freq_hz = float(marker.freq_hz)
    elif normalize_marker_mode(marker.mode) == "delta":
        ref_freq = resolve_marker_frequency_hz(params, marker.ref_marker_id)
        if ref_freq is not None:
            params.selected_freq_hz = float(ref_freq) + float(marker.freq_hz)


def ensure_default_marker_on_f_readout(params: SpectrumParams) -> None:
    """FC→F sin marcador activo válido: enciende M1 en FC y lo selecciona."""
    active_id = int(params.active_marker_id)
    if resolve_marker_frequency_hz(params, active_id, allow_peak_search=False) is not None:
        return
    marker = get_marker(params, 1)
    if marker is None:
        return
    params.active_marker_id = 1
    marker.enabled = True
    center = float(params.center_freq_hz)
    if abs(float(marker.freq_hz)) < 1.0 or normalize_marker_mode(marker.mode) == "delta":
        marker.mode = "normal"
        marker.freq_hz = center
    params.selected_freq_hz = float(marker.freq_hz)


def patch_active_marker_frequency(params: SpectrumParams, freq_hz: float) -> None:
    from core.monitor.monitor_freq_span_logic import clamp_center_hz

    clamped = clamp_center_hz(params, freq_hz)
    marker = get_marker(params, params.active_marker_id)
    if marker is None:
        params.selected_freq_hz = clamped
        return
    mode = normalize_marker_mode(marker.mode)
    if mode in ("normal", "fixed", "peak"):
        marker.freq_hz = clamped
    elif mode == "delta":
        ref_freq = resolve_marker_frequency_hz(params, marker.ref_marker_id)
        if ref_freq is not None:
            marker.freq_hz = clamped - ref_freq
    params.selected_freq_hz = clamped


def migrate_legacy_marker_bank(params: SpectrumParams, data: dict[str, Any] | None = None) -> None:
    """Proyectos antiguos: F/FC → banco M1–M10."""
    center = float(params.center_freq_hz)
    if not params.markers or len(params.markers) != MARKER_COUNT:
        params.markers = default_marker_bank(center)
    m1 = params.markers[0]
    m1.freq_hz = float(params.selected_freq_hz) if params.freq_readout == "f" else center
    if data:
        m1.show_line = bool(data.get("marker_show_line", m1.show_line))
        m1.show_freq = bool(data.get("marker_show_freq", m1.show_freq))
        m1.show_level = bool(data.get("marker_show_level", m1.show_level))
        m1.show_snr = bool(data.get("marker_show_snr", m1.show_snr))
    params.active_marker_id = max(1, min(MARKER_COUNT, int(getattr(params, "active_marker_id", 1) or 1)))


def markers_equal(
    left: list[MarkerDefinition],
    right: list[MarkerDefinition],
    *,
    freq_tol_hz: float = 0.5,
) -> bool:
    if len(left) != len(right):
        return False
    for a, b in zip(left, right):
        if (
            a.enabled != b.enabled
            or normalize_marker_mode(a.mode) != normalize_marker_mode(b.mode)
            or abs(float(a.freq_hz) - float(b.freq_hz)) > freq_tol_hz
            or int(a.ref_marker_id) != int(b.ref_marker_id)
            or str(a.color) != str(b.color)
            or a.show_line != b.show_line
            or a.show_freq != b.show_freq
            or a.show_level != b.show_level
            or a.show_snr != b.show_snr
        ):
            return False
    return True


def default_delta_ref_marker_id(params: SpectrumParams, marker_id: int) -> int | None:
    """Referencia delta por defecto (estilo analizador): activo → M1 → otro habilitado."""
    active = int(params.active_marker_id)
    if active != marker_id:
        ref = get_marker(params, active)
        if ref is not None and ref.enabled:
            return active
    if marker_id != 1:
        ref = get_marker(params, 1)
        if ref is not None and ref.enabled:
            return 1
    for other in range(1, MARKER_COUNT + 1):
        if other == marker_id:
            continue
        ref = get_marker(params, other)
        if ref is not None and ref.enabled:
            return other
    return None


def prepare_marker_for_delta_mode(
    params: SpectrumParams,
    marker_id: int,
    ref_marker_id: int,
) -> None:
    """Convierte un marcador a delta conservando posición absoluta como offset respecto a ref."""
    marker = get_marker(params, marker_id)
    if marker is None:
        return
    abs_freq = resolve_marker_frequency_hz(params, marker_id, allow_peak_search=False)
    if abs_freq is None:
        abs_freq = float(marker.freq_hz)
    ref_freq = resolve_marker_frequency_hz(params, ref_marker_id, allow_peak_search=False)
    if ref_freq is None:
        ref_marker = get_marker(params, ref_marker_id)
        ref_freq = float(ref_marker.freq_hz) if ref_marker is not None else float(params.center_freq_hz)
    marker.mode = "delta"
    marker.ref_marker_id = int(ref_marker_id)
    marker.freq_hz = float(abs_freq) - float(ref_freq)
    marker.enabled = True


def marker_bank_params_equal(left: SpectrumParams, right: SpectrumParams) -> bool:
    if int(left.active_marker_id) != int(right.active_marker_id):
        return False
    if bool(left.marker_auto_pan) != bool(right.marker_auto_pan):
        return False
    return markers_equal(left.markers, right.markers)
