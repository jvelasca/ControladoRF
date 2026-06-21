"""Tests carga de ayuda por idioma."""
from __future__ import annotations

from i18n.json_translation import set_language

from gui.help_content import (
    current_help_language,
    help_markdown_path,
    load_help_markdown,
)


def test_help_paths_by_language():
    set_language("es")
    assert current_help_language() == "es"
    assert help_markdown_path("manual").name == "ayuda.md"
    assert help_markdown_path("supervision").name == "monitor_supervision_ayuda.md"

    set_language("en")
    assert current_help_language() == "en"
    assert help_markdown_path("manual").name == "help.md"
    assert help_markdown_path("supervision").name == "monitor_supervision_help.md"
    set_language("es")


def test_load_help_markdown_english():
    set_language("en")
    text = load_help_markdown("manual")
    assert "User manual" in text
    assert "Getting started" in text
    set_language("es")


def test_unknown_language_falls_back_to_spanish():
    path = help_markdown_path("manual", lang="fr")
    assert path.name == "ayuda.md"
    assert path.is_file()


def test_load_supervision_help_spanish():
    set_language("es")
    text = load_help_markdown("supervision")
    assert "Registro REC y log CSV" in text
    assert "Barra de estado de la aplicación" in text
    assert "Panel Alarmas" in text
    set_language("es")


def test_load_supervision_help_english():
    set_language("en")
    text = load_help_markdown("supervision")
    assert "REC logging and CSV" in text
    assert "Application status bar" in text
    assert "Alarms panel" in text
    set_language("es")
