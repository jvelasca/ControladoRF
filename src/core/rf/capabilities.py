"""Capacidades por modelo de equipo."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GainStageSpec:
    name: str
    min_db: int
    max_db: int
    step_db: int


@dataclass(frozen=True)
class DeviceCapabilities:
    device_id: str
    display_name: str
    freq_min_hz: float
    freq_max_hz: float
    instant_bw_hz: float
    sample_rate_min_hz: float
    sample_rate_max_hz: float
    sweep_rbw_min_hz: float
    sweep_rbw_max_hz: float
    gain_stages: tuple[GainStageSpec, ...]
    supports_bias_tee: bool = True
    supports_sweep: bool = True
    supports_iq_stream: bool = True


HACKRF_CAPABILITIES = DeviceCapabilities(
    device_id="hackrf",
    display_name="HackRF One",
    freq_min_hz=1_000_000.0,
    freq_max_hz=6_000_000_000.0,
    instant_bw_hz=20_000_000.0,
    sample_rate_min_hz=2_000_000.0,
    sample_rate_max_hz=20_000_000.0,
    sweep_rbw_min_hz=100_000.0,
    sweep_rbw_max_hz=5_000_000.0,
    gain_stages=(
        GainStageSpec("lna", 0, 40, 8),
        GainStageSpec("vga", 0, 62, 2),
        GainStageSpec("rf_amp", 0, 11, 11),
    ),
    supports_bias_tee=True,
    supports_sweep=True,
    supports_iq_stream=True,
)

MOCK_CAPABILITIES = DeviceCapabilities(
    device_id="mock",
    display_name="Mock SDR",
    freq_min_hz=1_000_000.0,
    freq_max_hz=6_000_000_000.0,
    instant_bw_hz=20_000_000.0,
    sample_rate_min_hz=2_000_000.0,
    sample_rate_max_hz=20_000_000.0,
    sweep_rbw_min_hz=1_000.0,
    sweep_rbw_max_hz=5_000_000.0,
    gain_stages=(
        GainStageSpec("lna", 0, 40, 8),
        GainStageSpec("vga", 0, 62, 2),
    ),
    supports_bias_tee=False,
    supports_sweep=True,
    supports_iq_stream=True,
)

RF_EXPLORER_CAPABILITIES = DeviceCapabilities(
    device_id="rf_explorer",
    display_name="RF Explorer",
    freq_min_hz=15_000_000.0,
    freq_max_hz=2_700_000_000.0,
    instant_bw_hz=100_000.0,
    sample_rate_min_hz=0.0,
    sample_rate_max_hz=0.0,
    sweep_rbw_min_hz=2_600.0,
    sweep_rbw_max_hz=640_000.0,
    gain_stages=(),
    supports_bias_tee=False,
    supports_sweep=True,
    supports_iq_stream=False,
)

TINYSA_CAPABILITIES = DeviceCapabilities(
    device_id="tinysa",
    display_name="TinySA",
    freq_min_hz=100_000.0,
    freq_max_hz=960_000_000.0,
    instant_bw_hz=100_000.0,
    sample_rate_min_hz=0.0,
    sample_rate_max_hz=0.0,
    sweep_rbw_min_hz=2_000.0,
    sweep_rbw_max_hz=600_000.0,
    gain_stages=(),
    supports_bias_tee=False,
    supports_sweep=True,
    supports_iq_stream=False,
)

_CAPABILITIES = {
    "hackrf": HACKRF_CAPABILITIES,
    "mock": MOCK_CAPABILITIES,
    "rf_explorer": RF_EXPLORER_CAPABILITIES,
    "tinysa": TINYSA_CAPABILITIES,
}


def capabilities_for_device(device_id: str) -> DeviceCapabilities:
    from core.rf.source_ids import device_family

    base = device_family(device_id) if device_id else "mock"
    return _CAPABILITIES.get(base, MOCK_CAPABILITIES)
