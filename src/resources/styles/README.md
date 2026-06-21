# Estilos visuales (QSS)

La aplicación **no usa archivos `.qss` externos**. El aspecto IDE está en código Python.

## Apariencia tipo Visual Studio

1. **`utils/theme_utils.apply_system_appearance()`** — detecta modo claro/oscuro del SO, aplica estilo **Fusion** y paleta VS (evita barras beige del estilo nativo Windows en oscuro).
2. **`gui/app_chrome_styles.py`** — QSS global: `QMenuBar`, `QMenu`, `QToolBar`, `QStatusBar`, `QDockWidget`, diálogos, tablas, botones.
3. **`gui/panel_styles.py`** — colores del contenido de cada panel dock.

La barra de estado usa el mismo cromo neutro que menús y toolbars (sin franja azul).
