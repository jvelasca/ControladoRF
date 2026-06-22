"""Segmentos de asignación RF visibles en el espectro del Monitor."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from core.rf.channelization_service import ChannelizationService


@dataclass(frozen=True)
class AllocationSegment:
    standard_id: str
    service_type: str
    label: str
    freq_min_hz: float
    freq_max_hz: float
    center_freq_hz: float


def collect_allocation_segments(
    service: ChannelizationService,
    start_hz: float,
    stop_hz: float,
) -> List[AllocationSegment]:
    state = service.get_state()
    if not state.show_spectrum_allocations:
        return []

    segments: List[AllocationSegment] = []
    for std in service.active_standards():
        for ch in service.list_channels(std.id):
            half = ch.bandwidth_hz / 2.0
            f_min = ch.center_freq_hz - half
            f_max = ch.center_freq_hz + half
            if f_max < start_hz or f_min > stop_hz:
                continue
            segments.append(
                AllocationSegment(
                    standard_id=std.id,
                    service_type=std.service_type,
                    label=ch.channel_label,
                    freq_min_hz=f_min,
                    freq_max_hz=f_max,
                    center_freq_hz=ch.center_freq_hz,
                )
            )
    segments.sort(key=lambda seg: (seg.freq_min_hz, seg.center_freq_hz))
    return segments
