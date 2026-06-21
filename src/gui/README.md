# Módulo gui

Interfaz PyQt6 profesional con paneles acoplables (`QDockWidget`), i18n JSON y persistencia de layout por workspace. **No hay selector de temas**: la apariencia sigue el modo claro u oscuro del sistema operativo.

## Estructura actual

| Archivo | Responsabilidad |
|---------|-----------------|
| `main_window.py` | Ventana principal, layout dock, persistencia, `refresh_appearance()` |
| `dock_panel_base.py` | Clase base de paneles con estilo adaptativo |
| `dock_panel1/2/3.py` | Tres paneles acoplables |
| `app_chrome_styles.py` | QSS global tipo Visual Studio (menú, toolbar, status bar) |
| `panel_styles.py` | Paletas de contenido de paneles dock |
| `_layout_utils.py` | Disposición por defecto de docks |
| `menu_bar.py`, `tool_bar.py`, `status_bar.py` | Barras de la ventana |
| `config_dialog.py` | Idioma por workspace + pestaña base de datos (global) |
| `config_db_tab.py` | Parámetros SQLite y mantenimiento |
| `items_panel_widget.py` | CRUD de items (Panel 1) |
| `item_edit_dialog.py` | Diálogo crear/editar item |
| `workspace_manager.py` | Gestión visual de workspaces |
| `about_dialog.py` | Ventana Acerca de |
| `icon_utils.py` | Registro único de iconos monocromáticos Qt (`get_app_icon`) |

## Paneles acoplables

Colores adaptados automáticamente al modo del SO (`is_dark_mode()`):

- **Claro**: `#FFFFFF`, `#F3F3F3`, `#ECECEC`
- **Oscuro**: `#1E1E1E`, `#252526`, `#2D2D30`

Al cambiar el tema de Windows/macOS se llama `MainWindow.refresh_appearance()`.

## Persistencia de layout

Solo `MainWindow` está registrado como componente **workspace aware** del layout.

Guardado al cerrar; restauración en el primer `show()`.

## i18n

Todos los textos visibles usan `tr("clave")`. Cada diálogo implementa `recargar_textos()`.

## Tests

Tests gráficos en `tests_gui/`.
