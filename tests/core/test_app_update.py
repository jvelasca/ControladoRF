"""Comprobación de actualizaciones GitHub Releases."""
from core.app_update import UpdateCheckResult, is_newer_version


def test_is_newer_version_semver():
    assert is_newer_version("1.0.2", "1.1.0")
    assert not is_newer_version("1.1.0", "1.1.0")
    assert not is_newer_version("1.1.0", "1.0.2")


def test_update_check_result_statuses():
    assert UpdateCheckResult(status="current", latest_published="1.0.2").status == "current"
    assert UpdateCheckResult(status="available").status == "available"
