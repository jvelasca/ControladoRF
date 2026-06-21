"""
Utilidades de internacionalización para cambio de idioma en caliente.
"""
from typing import List

from i18n.json_translation import set_language

SUPPORTED_LANGUAGES: List[str] = ["es", "en"]


def apply_language(lang_code: str) -> None:
    """Aplica el idioma indicado recargando las traducciones JSON."""
    set_language(lang_code)
