"""Tests reparto de splitters del workspace Monitor."""
from __future__ import annotations

from gui.module_workspace import (
    MONITOR_DEFAULT_HORIZONTAL,
    _splitter_sizes_from_ratio,
)


def test_splitter_sizes_from_ratio_uses_reference():
    sizes = _splitter_sizes_from_ratio(
        1000,
        reference=[700, 300],
        fallback=list(MONITOR_DEFAULT_HORIZONTAL),
        min_second=174,
    )
    assert sizes[0] + sizes[1] == 1000
    assert sizes[1] >= 174
    assert abs(sizes[1] - 300) <= 2


def test_splitter_sizes_from_ratio_respects_window_resize():
    sizes = _splitter_sizes_from_ratio(
        1400,
        reference=[820, 300],
        fallback=list(MONITOR_DEFAULT_HORIZONTAL),
        min_second=174,
    )
    assert sizes[0] + sizes[1] == 1400
    assert sizes[1] > 300
