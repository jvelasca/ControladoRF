"""Tests de validación del layout persistido en .crf."""
from core.project_ui_state import validate_module_ui_state


def test_validate_keeps_known_keys():
    raw = {
        "splitter_main": [700, 300],
        "splitter_left": [400, 260],
        "panel_visibility": {"lista": True, "propiedades": True, "acciones": True},
        "unknown_key": "drop-me",
    }
    cleaned = validate_module_ui_state(raw)
    assert cleaned["splitter_main"] == [700, 300]
    assert "unknown_key" not in cleaned


def test_validate_fixes_all_hidden_panels():
    raw = {
        "panel_visibility": {"lista": False, "propiedades": False, "acciones": False},
    }
    cleaned = validate_module_ui_state(raw)
    assert all(cleaned["panel_visibility"].values())


def test_validate_keeps_monitor_markers():
    raw = {
        "panel_content": {
            "monitor": {
                "center_freq_hz": 100_000_000.0,
                "active_marker_id": 2,
                "markers": [
                    {
                        "enabled": True,
                        "mode": "normal",
                        "freq_hz": 101_000_000.0,
                        "ref_marker_id": 1,
                        "color": "#FFC850",
                        "show_line": True,
                        "show_freq": True,
                        "show_level": True,
                        "show_snr": False,
                    },
                    {"enabled": False, "mode": "normal", "freq_hz": 100_000_000.0},
                ],
                "extra_blob": {"drop": True},
            }
        }
    }
    cleaned = validate_module_ui_state(raw)
    monitor = cleaned["panel_content"]["monitor"]
    assert monitor["center_freq_hz"] == 100_000_000.0
    assert monitor["active_marker_id"] == 2
    assert len(monitor["markers"]) == 2
    assert monitor["markers"][0]["enabled"] is True
    assert "extra_blob" not in monitor


def test_validate_keeps_table_header_state():
    raw = {
        "panel_content": {
            "lista": {
                "table_header": "AAAA",
                "table_text_alignment": "center",
                "extra": "drop",
            },
        }
    }
    cleaned = validate_module_ui_state(raw)
    lista = cleaned["panel_content"]["lista"]
    assert lista["table_header"] == "AAAA"
    assert lista["table_text_alignment"] == "center"
    assert "extra" not in lista
