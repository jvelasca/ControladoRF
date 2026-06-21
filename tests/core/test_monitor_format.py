"""Tests de formateo LCD del Monitor."""
from core.monitor.monitor_format import (
    format_attenuation_db,
    format_bw_hz,
    format_db_per_div,
    format_freq_short,
    format_ref_level,
    parse_locale_float,
)
from core.monitor.spectrum_params import SpectrumParams


def test_format_ref_level():
    assert format_ref_level(0.0) == "0.0 dBm"


def test_format_attenuation():
    assert format_attenuation_db(10.0) == "10 dB"


def test_format_bw_khz():
    assert format_bw_hz(9_765.625) == "9.8 kHz"


def test_format_freq_mhz():
    assert "MHz" in format_freq_short(100_000_000)


def test_db_per_div():
    assert format_db_per_div(100, 10) == "10 dB/div"


def test_effective_rbw_auto():
    params = SpectrumParams(sample_rate_hz=20_000_000, fft_size=2048, rbw_auto=True)
    assert abs(params.effective_rbw_hz() - 20_000_000 / 2048) < 0.01


def test_parse_locale_float_dot_and_comma():
    assert parse_locale_float("90.9") == 90.9
    assert parse_locale_float("90,9") == 90.9
    assert parse_locale_float("  100,25 MHz ") == 100.25
    assert parse_locale_float("1.234,5") == 1234.5
    assert parse_locale_float("1,234.5") == 1234.5
