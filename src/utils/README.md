# Módulo utils

Este módulo contiene utilidades generales reutilizables en toda la aplicación.

## Logger centralizado

- `init_logging()`, `get_logger()`, `log_info()`, `log_error()`, etc.

## Apariencia adaptativa al SO

- `theme_utils.py`: detección claro/oscuro del SO + `apply_system_appearance()` (Fusion + paleta VS).
- `gui/app_chrome_styles.py`: QSS global tipo Visual Studio (menú, toolbar, status bar, controles).

## Buenas prácticas

- Añade tests unitarios en `tests/`.
- Documenta cada utilidad con ejemplos de uso.
