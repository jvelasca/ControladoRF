"""Tests catálogo y setup SDR."""
from core.monitor.sdr_catalog import SDR_DEVICE_CATALOG, get_default_device_id, get_device_spec
from core.monitor.sdr_setup import build_all_setup_reports, map_source_id_to_device_id


def test_catalog_includes_hackrf_airspy():
    ids = {spec.device_id for spec in SDR_DEVICE_CATALOG}
    assert ids == {"hackrf", "airspy", "airspy_hf"}


def test_default_device_is_hackrf():
    assert get_default_device_id() == "hackrf"


def test_map_source_ids():
    assert map_source_id_to_device_id("hackrf_0") == "hackrf"
    assert map_source_id_to_device_id("airspy_hf") == "airspy_hf"


def test_build_setup_reports_structure():
    reports = build_all_setup_reports(probe_python=False)
    assert len(reports) == 3
    hackrf = next(r for r in reports if r.device_id == "hackrf")
    assert hackrf.is_default


def test_get_device_spec_hf():
    assert get_device_spec("airspy_hf_0").device_id == "airspy_hf"
