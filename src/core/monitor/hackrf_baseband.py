"""Filtro paso-banda HackRF (MAX2837) — misma lógica que libhackrf."""
from __future__ import annotations

# Valores válidos (Hz), orden ascendente — hackrf.c max2837_ft[]
HACKRF_BASEBAND_FILTER_HZ = (
    1_750_000,
    2_500_000,
    3_500_000,
    5_000_000,
    5_500_000,
    6_000_000,
    7_000_000,
    8_000_000,
    9_000_000,
    10_000_000,
    12_000_000,
    14_000_000,
    15_000_000,
    20_000_000,
    24_000_000,
    28_000_000,
)


def compute_hackrf_baseband_filter_bw(bandwidth_hz: float) -> int:
    """Elige el ancho de filtro válido (port de hackrf_compute_baseband_filter_bw)."""
    target = max(1, int(bandwidth_hz))
    table = HACKRF_BASEBAND_FILTER_HZ
    idx = 0
    while idx < len(table):
        if table[idx] >= target:
            break
        idx += 1
    if idx >= len(table):
        return table[-1]
    if idx > 0 and table[idx] > target:
        return table[idx - 1]
    return table[idx]


def default_baseband_filter_for_sample_rate(sample_rate_hz: float) -> int:
    """Auto filtro FI: ≤ 75 % del sample rate (como SDR++ / hackrf_set_sample_rate)."""
    rate = max(1.0, float(sample_rate_hz))
    return compute_hackrf_baseband_filter_bw(0.75 * rate)


def snap_hackrf_baseband_filter_bw(bandwidth_hz: float) -> int:
    return compute_hackrf_baseband_filter_bw(bandwidth_hz)


def baseband_filter_choices_for_sample_rate(sample_rate_hz: float) -> tuple[int, ...]:
    """Valores válidos del MAX2837 que no superan el sample rate (menú manual SDR++)."""
    rate = max(1.0, float(sample_rate_hz))
    return tuple(v for v in HACKRF_BASEBAND_FILTER_HZ if v <= rate + 1.0)


def format_baseband_filter_mhz(bw_hz: float) -> str:
    mhz = float(bw_hz) / 1_000_000.0
    if abs(mhz - round(mhz)) < 0.05:
        return f"{mhz:.0f}"
    return f"{mhz:.2f}"
