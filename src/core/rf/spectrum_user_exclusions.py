"""Zonas de exclusión definidas por el usuario en el espectro."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import List

from core.rf.channelization_allocations import AllocationSegment

PREFS_KEY = "user_spectrum_exclusions_json"
DEFAULT_EXCLUSION_COLOR = "#c0404088"


@dataclass(frozen=True)
class SpectrumUserExclusion:
    id: str
    label: str
    standard_id: str
    freq_min_hz: float
    freq_max_hz: float
    color_hex: str = DEFAULT_EXCLUSION_COLOR


def exclusion_from_segment(
    segment: AllocationSegment, *, color_hex: str = DEFAULT_EXCLUSION_COLOR
) -> SpectrumUserExclusion:
    return SpectrumUserExclusion(
        id=f"{segment.standard_id}:{segment.label}",
        label=segment.label,
        standard_id=segment.standard_id,
        freq_min_hz=segment.freq_min_hz,
        freq_max_hz=segment.freq_max_hz,
        color_hex=color_hex,
    )


def parse_exclusions_json(raw: str) -> List[SpectrumUserExclusion]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    result: List[SpectrumUserExclusion] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            result.append(
                SpectrumUserExclusion(
                    id=str(item.get("id") or ""),
                    label=str(item.get("label") or ""),
                    standard_id=str(item.get("standard_id") or ""),
                    freq_min_hz=float(item.get("freq_min_hz") or 0.0),
                    freq_max_hz=float(item.get("freq_max_hz") or 0.0),
                    color_hex=str(item.get("color_hex") or DEFAULT_EXCLUSION_COLOR),
                )
            )
        except (TypeError, ValueError):
            continue
    return [ex for ex in result if ex.id and ex.freq_max_hz > ex.freq_min_hz]


def exclusions_to_json(items: List[SpectrumUserExclusion]) -> str:
    payload = [asdict(item) for item in items]
    return json.dumps(payload, ensure_ascii=False)
