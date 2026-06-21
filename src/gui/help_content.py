"""Rutas y carga de documentación de ayuda estándar (es / en)."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from app_paths import docs_dir
from i18n.json_translation import tr

HelpTopic = Literal["manual", "supervision"]
HelpLanguage = Literal["es", "en"]

_DOCS_DIR = docs_dir()
_DEFAULT_LANG: HelpLanguage = "es"

HELP_FILES: dict[HelpTopic, dict[HelpLanguage, str]] = {
    "manual": {
        "es": "ayuda.md",
        "en": "help.md",
    },
    "supervision": {
        "es": "monitor_supervision_ayuda.md",
        "en": "monitor_supervision_help.md",
    },
}


def current_help_language() -> HelpLanguage:
    """Idioma activo de la app (prefijo de ``translator.lang_code``)."""
    from i18n.json_translation import translator

    code = str(getattr(translator, "lang_code", _DEFAULT_LANG) or _DEFAULT_LANG)
    prefix = code.split("_")[0].lower()
    if prefix in HELP_FILES["manual"]:
        return prefix  # type: ignore[return-value]
    return _DEFAULT_LANG


def help_markdown_path(topic: HelpTopic, *, lang: str | None = None) -> Path:
    language = _normalize_lang(lang) if lang else current_help_language()
    filenames = HELP_FILES[topic]
    primary = _DOCS_DIR / filenames[language]
    if primary.is_file():
        return primary
    fallback = _DOCS_DIR / filenames[_DEFAULT_LANG]
    return fallback


def load_help_markdown(topic: HelpTopic, *, lang: str | None = None) -> str:
    path = help_markdown_path(topic, lang=lang)
    if not path.is_file():
        return tr("help_file_missing").format(path=str(path))
    return path.read_text(encoding="utf-8")


def _normalize_lang(lang: str | None) -> HelpLanguage:
    prefix = str(lang or _DEFAULT_LANG).split("_")[0].lower()
    if prefix in HELP_FILES["manual"]:
        return prefix  # type: ignore[return-value]
    return _DEFAULT_LANG
