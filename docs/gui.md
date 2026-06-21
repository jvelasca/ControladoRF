# Documentación de la interfaz gráfica y apariencia

Este documento recoge el estado actual de la UI tras las fases de profesionalización (workspaces, configuración, apariencia IDE e iconografía).

## Apariencia adaptativa al SO

- **No hay selector manual de temas.** La app detecta modo claro/oscuro del sistema operativo.
- Motor: `src/utils/theme_utils.py`
  - `is_dark_mode()` — registro Windows + `Qt.ColorScheme` + paleta
  - `apply_system_appearance()` — estilo **Fusion** + paleta VS + QSS global
  - `connect_system_appearance_changed()` — refresco al cambiar el tema del SO
- Estilos globales: `src/gui/app_chrome_styles.py` (menú, toolbar, status bar, diálogos, tablas)
- Paneles dock: `src/gui/panel_styles.py` (contenido de cada panel)

### Barra de estado

Integrada al cromo neutro (sin franja azul). Mismo tono que menús en claro/oscuro.

## Iconografía unificada

- Registro central: `src/gui/icon_utils.py` → `get_app_icon("nombre", tamaño)`
- Solo glyphs **Qt monocromáticos** (`QStyle.StandardPixmap`), adaptados a la paleta activa
- Claves: `settings`, `workspaces`, `panel1/2/3`, `new`, `import`, `export`, `duplicate`, `delete`, `activate`, `reset_panels`, etc.

## Workspaces

- Módulo: `src/workspace/` (controller, store, model, `workspace_io.py`)
- Diálogo: `src/gui/workspace_manager.py` (tabla, import/export, duplicar, columna Activo)
- Persistencia: `src/workspace/data/workspaces.json`
- Por workspace se guarda **idioma** y **layout** (geometría, docks, tablas del gestor). **No** se guarda tema visual.

## Configuración

- Diálogo: `src/gui/config_dialog.py` — pestañas **General** (idioma por workspace) y **Base de datos** (global)
- Pestaña BD: `src/gui/config_db_tab.py` — parámetros SQLite, estado y mantenimiento
- Menú: Herramientas → Configuración

## Layout de paneles (Ver)

Disposición por defecto (`src/gui/_layout_utils.py`):

```
┌─────────────────┬──────────┐
│  Panel 1        │          │
│  (Items CRUD)   │ Panel 2  │
├─────────────────┤ (dcha.)  │
│    Panel 3      │          │
│  (inf. izq.)    │          │
└─────────────────┴──────────┘
```

- **Panel 1** (`items_panel_widget.py`): tabla CRUD de items vía `app_services.items`
- Menú **Ver → Reiniciar paneles** (`view_reset_panels`): restaura disposición, visibilidad, tamaños proporcionales y persiste en el workspace activo.
- Función: `restaurar_paneles_por_defecto(main_window)`

## Ciclo de vida

- Arranque: `src/app_lifecycle.py` → SQLite (`app.db` + migraciones), idioma, apariencia, `MainWindow`
- Cierre: guarda workspace activo, `workspaces.json` y cierra la base de datos
- `MainWindow.refresh_appearance()` — reaplica SO + paneles + iconos

## Tests GUI relevantes

| Test | Qué verifica |
|------|----------------|
| `tests_gui/test_workspace_manager_i18n.py` | i18n del gestor |
| `tests_gui/test_config_dialog.py` | Configuración idioma |
| `tests_gui/test_config_db_tab.py` | Pestaña base de datos |
| `tests_gui/test_panel_theme.py` | Paneles vs modo SO |
| `tests_gui/test_items_panel.py` | Panel CRUD items |
| `tests_gui/test_reset_panels_layout.py` | Reiniciar paneles |
| `tests/test_icon_utils.py` | Registro de iconos |
| `tests/test_appearance_utils.py` | Apariencia SO |
| `tests/db/test_connection.py` | SQLite, migraciones, transacciones |

## Referencias por módulo

- `src/gui/README.md`
- `src/workspace/README.md`
- `src/utils/README.md`
- `docs/arquitectura_APP.md` — pestañas Inventario / Coordinación / Monitor
- **`docs/monitor.md`** — layout Monitor (espectro, waterfall, config, alarmas)
- `src/i18n/README.md`
- `src/db/README.md`
- `src/resources/icons/README.md`
