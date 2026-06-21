"""Tests exportación de traza Monitor."""
from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import pytest

from core.monitor.monitor_export import (
    MonitorExportError,
    TraceExportFormat,
    export_spectrum_trace_csv,
    export_spectrum_trace_soundbase_csv,
    export_spectrum_trace_workbench_csv,
    rf_tool_scan_filename,
)
from core.monitor.spectrum_params import SpectrumFrame, SpectrumParams


def _sample_frame(*, points: int = 801) -> SpectrumFrame:
    freqs = np.linspace(470_000_000.0, 490_000_000.0, points)
    power = np.linspace(-110.0, -70.0, points)
    return SpectrumFrame(
        freqs_hz=freqs,
        power_db=power,
        center_freq_hz=480_000_000.0,
        span_hz=20_000_000.0,
    )


def test_workbench_csv_no_header_pairs_mhz_dbm(tmp_path: Path):
    frame = _sample_frame(points=5)
    path = tmp_path / "scan.csv"
    export_spectrum_trace_workbench_csv(frame, SpectrumParams(), path)
    text = path.read_text(encoding="utf-8")
    assert not text.startswith("\ufeff")
    lines = [line for line in text.strip().splitlines() if line.strip()]
    assert all(";" not in line for line in lines)
    first = lines[0].split(",")
    assert len(first) == 2
    assert float(first[0]) == pytest.approx(470.0125, abs=0.05)
    assert float(first[1]) == pytest.approx(-110.0, abs=0.5)


def test_soundbase_csv_has_header(tmp_path: Path):
    frame = _sample_frame(points=5)
    path = tmp_path / "scan_sb.csv"
    export_spectrum_trace_soundbase_csv(frame, SpectrumParams(), path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    assert rows[0] == ["Frequency_MHz", "Level_dBm"]
    assert float(rows[1][0]) == pytest.approx(470.0125, abs=0.05)
    assert float(rows[1][1]) == pytest.approx(-110.0, abs=0.5)


def test_controladorf_csv_keeps_metadata(tmp_path: Path):
    frame = _sample_frame(points=3)
    path = tmp_path / "trace.csv"
    export_spectrum_trace_csv(frame, SpectrumParams(), path, export_format=TraceExportFormat.CONTROLADORF)
    text = path.read_text(encoding="utf-8-sig")
    assert "CONTROLADORF Monitor export" in text
    assert "freq_hz" in text
    assert "power_dbm" in text


def test_rf_tool_scan_filename():
    frame = _sample_frame(points=10)
    name = rf_tool_scan_filename(frame)
    assert name.startswith("Scan_")
    assert name.endswith(".csv")


def test_export_empty_trace_raises(tmp_path: Path):
    frame = SpectrumFrame(freqs_hz=[], power_db=[], center_freq_hz=0.0, span_hz=0.0)
    with pytest.raises(MonitorExportError):
        export_spectrum_trace_workbench_csv(frame, SpectrumParams(), tmp_path / "x.csv")
