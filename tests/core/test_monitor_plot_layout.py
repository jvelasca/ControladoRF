"""Tests alineación espectro / waterfall y bloques IQ demod."""
from __future__ import annotations

from PyQt6.QtCore import QRect

from core.monitor.demod_dsp import iq_samples_for_demod
from core.monitor.iq_constants import IQ_DEMOD_CHUNK_SAMPLES, IQ_DEMOD_MAX_SAMPLES
from core.monitor.spectrum_params import SpectrumParams
from gui.monitor.monitor_plot_layout import (
    DOCK_COLLAPSED_WIDTH,
    FREQ_PLOT_LEFT_MARGIN,
    WATERFALL_SLIDER_PANEL_WIDTH,
    freq_plot_rect,
    unified_freq_plot_right_gutter,
)


def test_unified_gutter_matches_slider_panel_when_dock_collapsed() -> None:
    gutter = unified_freq_plot_right_gutter(dock_width=DOCK_COLLAPSED_WIDTH)
    assert gutter == WATERFALL_SLIDER_PANEL_WIDTH
    assert DOCK_COLLAPSED_WIDTH == WATERFALL_SLIDER_PANEL_WIDTH


def test_spectrum_and_waterfall_share_freq_plot_rect() -> None:
    widget = QRect(0, 0, 900, 240)
    gutter = unified_freq_plot_right_gutter(dock_width=120)
    spec = freq_plot_rect(widget, right_gutter=gutter, top=42, bottom=42)
    wf = freq_plot_rect(widget, right_gutter=gutter, top=2, bottom=2)
    assert spec.left() == wf.left() == FREQ_PLOT_LEFT_MARGIN
    assert spec.right() == wf.right()
    assert spec.width() == widget.width() - FREQ_PLOT_LEFT_MARGIN - gutter


def test_iq_samples_for_demod_scales_with_sample_rate() -> None:
    params = SpectrumParams(
        center_freq_hz=100e6,
        vfo_freq_hz=100.025e6,
        sample_rate_hz=2_000_000.0,
        fft_size=2048,
        operating_mode="sdr",
        audio_enabled=True,
    )
    n = iq_samples_for_demod(params, fft_size=2048)
    assert n >= 2048
    assert n == IQ_DEMOD_CHUNK_SAMPLES * 4
    params.sample_rate_hz = 20_000_000.0
    assert iq_samples_for_demod(params, fft_size=2048) == IQ_DEMOD_MAX_SAMPLES
