# Módulo i18n

"""
README del módulo i18n
----------------------
Propósito: Gestionar la internacionalización (i18n) de la aplicación mediante archivos JSON.

Premisas:
- Todos los textos de UI deben estar en archivos de idioma, nunca hardcodeados en el código.
- Usar exclusivamente `tr("clave")` de `json_translation.py` (no `self.tr()` de Qt).
- Soporte para recarga dinámica de idioma y pruebas automáticas.
"""

Este módulo gestiona la internacionalización (i18n) de la aplicación.

## Archivos principales
- `json_translation.py`: Carga traducciones JSON y expone `tr(key, **kwargs)` y `set_language(lang_code)`.
- `translation_utils.py`: API de alto nivel con `apply_language(lang_code)` y `SUPPORTED_LANGUAGES`.
- `es.json`, `en.json`: Archivos de traducción (uno por idioma, clave → texto).
- `qm/`: Archivos `.ts` legacy de Qt Linguist (opcionales; la app usa JSON como fuente principal).

## Ejemplo de uso
```python
from i18n.json_translation import tr, set_language
from i18n.translation_utils import apply_language

set_language("es")
print(tr("file"))

apply_language("en")
print(tr("file"))  # "File"
```

## Recarga dinámica en la UI
Cada ventana o widget con textos traducibles debe implementar `recargar_textos()`:

```python
from i18n.json_translation import tr

def recargar_textos(self) -> None:
    self.setWindowTitle(tr("config_title"))
    self._close_btn.setText(tr("close"))
```

Tras cambiar el idioma, llamar a `recargar_textos()` en la ventana principal y sus componentes.

## Añadir un nuevo idioma
1. Crear `src/i18n/<codigo>.json` copiando la estructura de `es.json`.
2. Añadir el código a `SUPPORTED_LANGUAGES` en `translation_utils.py`.
3. Registrar el idioma en `ConfigDialog.AVAILABLE_LANGUAGES` si debe aparecer en la UI.

## Buenas prácticas
- Usa claves descriptivas en minúsculas con guiones bajos (`ws_manager_title`).
- Para textos con variables, usa placeholders: `"Idioma activo: {lang}"` y `tr("language_active", lang="Español")`.
- Añade tests en `tests/` o `tests_gui/` que verifiquen recarga de idioma.
- No mezclar `self.tr()` de Qt con el sistema JSON.

## Checklist para contribuciones
- [ ] ¿El texto está en `es.json` / `en.json` y no en el código?
- [ ] ¿Se usa `tr()` en lugar de cadenas literales o `self.tr()`?
- [ ] ¿El componente implementa `recargar_textos()`?
- [ ] ¿Hay test que verifique el cambio de idioma?
