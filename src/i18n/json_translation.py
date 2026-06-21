import json
import os
from typing import Dict, Optional

class JsonTranslator:
    def __init__(self, lang_code: str = "es"):
        self.lang_code = lang_code
        self.translations: Dict[str, str] = {}
        self.load_language(lang_code)

    def load_language(self, lang_code: str):
        base_dir = os.path.dirname(__file__)
        path = os.path.join(base_dir, f"{lang_code}.json")
        # Fallback: si no existe, probar con solo el prefijo (es_ES -> es)
        if not os.path.exists(path):
            lang_prefix = lang_code.split('_')[0]
            path = os.path.join(base_dir, f"{lang_prefix}.json")
            if not os.path.exists(path):
                raise FileNotFoundError(f"No se encontró el archivo de idioma: {path}")
        with open(path, "r", encoding="utf-8") as f:
            self.translations = json.load(f)
        self.lang_code = lang_code

    def tr(self, key: str, **kwargs) -> str:
        text = self.translations.get(key, key)
        if kwargs:
            try:
                return text.format(**kwargs)
            except Exception:
                return text
        return text

# Instancia global para la app
translator = JsonTranslator("es")

def set_language(lang_code: str):
    global translator
    translator.load_language(lang_code)

def tr(key: str, **kwargs) -> str:
    return translator.tr(key, **kwargs)
