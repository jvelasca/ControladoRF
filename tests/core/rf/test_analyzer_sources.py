"""Tests fuentes analizador sweep-only (RF Explorer, TinySA)."""
from __future__ import annotations

from collections import deque

import numpy as np
import pytest

from core.monitor.spectrum_params import SpectrumParams
from core.rf.acquisition.policy import DefaultAcquisitionPolicy
from core.rf.capabilities import capabilities_for_device
from core.rf.devices.common.serial_link import SerialLink
from core.rf.devices.tinysa.protocol import scanraw_spectrum
from core.rf.registry import create_device
from core.rf.source_ids import format_serial_source_id, is_analyzer_only_source, parse_source_id
from core.rf.source_profile import apply_analyzer_source_restrictions
from core.rf.types import FrequencyWindow, OperatingMode, OperatorIntent


def test_parse_source_id_serial_port():
    parsed = parse_source_id("tinysa@COM7")
    assert parsed.device_id == "tinysa"
    assert parsed.serial_port == "COM7"
    assert parsed.raw == "tinysa@COM7"


def test_parse_source_id_hackrf_index():
    parsed = parse_source_id("hackrf_1")
    assert parsed.device_id == "hackrf"
    assert parsed.instance_index == 1


def test_is_analyzer_only():
    assert is_analyzer_only_source("rf_explorer@COM3")
    assert is_analyzer_only_source("tinysa")
    assert not is_analyzer_only_source("hackrf")
    assert not is_analyzer_only_source("mock")


def test_capabilities_analyzer_no_iq():
    caps = capabilities_for_device("rf_explorer")
    assert caps.supports_sweep is True
    assert caps.supports_iq_stream is False


def test_acquisition_analyzer_always_sweep():
    policy = DefaultAcquisitionPolicy()
    intent = OperatorIntent(
        window=FrequencyWindow.from_center_span(100e6, 5e6),
        operating_mode=OperatingMode.SPECTRUM,
        source_id="tinysa",
    )
    plan = policy.plan(intent, device_id="tinysa")
    assert plan.mode.value == "sweep"
    assert plan.reason == "analyzer_only_sweep"
    assert plan.sweep is not None


def test_apply_analyzer_source_restrictions():
    params = SpectrumParams()
    params.source_id = "rf_explorer@COM5"
    params.operating_mode = "sdr"
    params.audio_enabled = True
    notices = apply_analyzer_source_restrictions(params)
    assert params.operating_mode == "spectrum"
    assert params.capture_mode == "sweep"
    assert params.audio_enabled is False
    assert "monitor_source_forced_analyzer_mode" in notices


def test_prepare_iq_for_play_clears_freq_window():
    from core.monitor.iq_sdr_profile import prepare_iq_for_play

    params = SpectrumParams()
    params.source_id = "hackrf"
    params.operating_mode = "sdr"
    params.capture_mode = "iq"
    params.marker_start_hz = 90_000_000.0
    params.marker_stop_hz = 110_000_000.0
    params.manual_span_hz = 10_000_000.0
    prepare_iq_for_play(params)
    assert not params.has_freq_window()


def test_prefer_playable_source_skips_analyzers():
    from core.monitor.device_discovery import SourceDescriptor, prefer_playable_source_id

    items = [
        SourceDescriptor("mock", "Mock", True, "", device_family="mock"),
        SourceDescriptor("tinysa@COM1", "TinySA", True, "", device_family="tinysa"),
        SourceDescriptor("hackrf", "HackRF", True, "", device_family="hackrf"),
    ]
    assert prefer_playable_source_id(descriptors=items) == "hackrf"


def test_create_device_tinysa_port():
    dev = create_device("tinysa@COM9")
    assert dev.device_id == "tinysa"
    assert dev._port == "COM9"  # noqa: SLF001


def test_format_serial_source_id():
    assert format_serial_source_id("tinysa", "COM1") == "tinysa@COM1"
    assert format_serial_source_id("tinysa", "COM1", index=1) == "tinysa_1@COM1"


class _FakeTransport:
    def __init__(self, lines: list[str]) -> None:
        self._lines = deque(line.encode("ascii") + b"\n" for line in lines)
        self.written: list[bytes] = []

    def write(self, data: bytes) -> int:
        self.written.append(data)
        return len(data)

    def readline(self) -> bytes:
        if self._lines:
            return self._lines.popleft()
        return b""

    def read(self, size: int = 1) -> bytes:
        return b""

    def reset_input_buffer(self) -> None:
        return

    def close(self) -> None:
        return


def test_tinysa_scanraw_parse():
    lines = [
        "350000000,-80.5",
        "350100000,-75.2",
        "350200000,-70.0",
        "ch>",
    ]
    link = SerialLink("COM_TEST", 115200, transport=_FakeTransport(lines))
    freqs, power = scanraw_spectrum(
        link,
        start_hz=350e6,
        stop_hz=350.2e6,
        num_points=101,
        timeout_sec=1.0,
    )
    assert freqs.size == 3
    assert power.size == 3
    assert freqs[0] == pytest.approx(350e6)
    assert power[1] == pytest.approx(-75.2)
