# CONTROLADORF — Arquitectura de la aplicación

Aplicación de escritorio para análisis, diseño y explotación de entornos de **radiofrecuencia** en sistemas inalámbricos de audio profesional (filosofía similar a Shure Wireless Workbench o SoundBase).

Basada en la plantilla PyQt6 genérica del repositorio.

**Visión Monitor / Supervisión:** ver [monitor_supervision_premisas.md](monitor_supervision_premisas.md) —
superar aplicaciones profesionales con hardware SDR de coste medio-bajo, matriz de umbrales
transparente y referencia nominal «en el aire».

---

## Módulos funcionales

| Módulo | Id interno | Estado |
|--------|------------|--------|
| Inventario RF | `inventario_rf` | ✅ CRUD, metadatos, export CSV/JSON/PDF, import Workbench |
| Coordinación | `coordinacion` | Placeholder |
| Monitor | `monitor` | 📋 v1.0 RF architecture — `docs/rf_engine/` + UI analizador activa |

Cada módulo tiene **3 paneles acoplables** redimensionables:

| Posición | Id panel | Inventario RF |
|----------|----------|---------------|
| Superior izquierda | `lista` | Lista de equipos |
| Lateral derecha | `propiedades` | Propiedades |
| Inferior izquierda | `acciones` | Acciones |

---

## Decisión arquitectónica: Workspace vs Proyecto

**Decisión (2026-06-12):** mantener **ambos conceptos separados**, como en aplicaciones profesionales de escritorio.

| Concepto | Fichero | Contenido | Analogía |
|----------|---------|-----------|----------|
| **Workspace** | `src/workspace/data/workspaces.json` | Idioma, proyectos recientes, geometría global de ventana, prefs de usuario | Preferencias de usuario / perfil local |
| **Proyecto** | `*.crf` (elegido por el usuario) | Datos RF del show + layout GUI por módulo | Documento de trabajo portable |

**Por qué no unificar todo en el proyecto:**
- Cada usuario ejecuta la app en su PC con sus preferencias (idioma, rutas, ventana).
- Los proyectos deben poder **compartirse** entre técnicos sin arrastrar prefs personales.
- El menú **Archivo** opera sobre proyectos; **Herramientas → Workspaces** sigue gestionando perfiles locales.

**Por qué no eliminar workspaces:**
- La plantilla ya tiene un patrón robusto de prefs por workspace.
- Separar prefs locales de datos de dominio reduce acoplamiento y facilita tests.

### Tres nombres distintos (no mezclar)

| Concepto | Dónde vive | Qué es | Ejemplo |
|----------|------------|--------|---------|
| **Nombre del show** | Campo editable en menú + `metadata.name` | Título del evento/producción | `Final Madrid 2026` |
| **Documento `.crf`** | Disco (Archivo → Guardar/Abrir) | Fichero portable (JSON UTF-8) | `backup_v3.crf` |
| **Indicador en toolbar** | `ProjectTitleWidget` (solo lectura) | `● Final Madrid 2026` al final de la barra de herramientas | Patrón IDE |

**Reglas (desarrollo v1):**
- Al **arrancar**, no se crea proyecto automático: estado «Sin proyecto» hasta Nuevo / Abrir / Importar.
- El **nombre del show** se edita con **Archivo → Renombrar show…** (diálogo estándar).
- El indicador de la toolbar es **solo lectura** (sin campos editables).
- La **ruta completa** del `.crf` aparece en la **barra de estado** (izquierda).
- El **título de ventana** es fijo: **CONTROLADORF** (el show no va en la barra de título del SO).

---

## GUI — estructura implementada (Fase 1)

```
┌─ Menú ────────────────────────────────────────────────┐
├─ Toolbar ───────────────────────────────────────────────┤
│ [ Inventario RF | Coordinación | Monitor ]  ← pestañas │
│ ┌───────────────┬──────────┐                           │
│ │ Lista         │          │  ← paneles DENTRO de tab  │
│ ├───────────────┤ Propied. │                           │
│ │ Acciones      │          │                           │
│ └───────────────┴──────────┘                           │
├─ Status bar ────────────────────────────────────────────┤
```

**Decisión layout (2026-06-12):** los paneles van **dentro de cada pestaña** con `QSplitter`, no como `QDockWidget` globales de la ventana. Así menú/toolbar/status quedan fijos y cada módulo tiene su layout independiente.

| Componente | Ruta |
|------------|------|
| Pestañas + orquestación | `src/gui/module_tab_manager.py` |
| 3 paneles por pestaña | `src/gui/module_workspace.py` |
| Marco con título + controles | `src/gui/module_panel_frame.py`, `src/gui/panel_header_bar.py` |

**Cabecera de panel (2026-06-12):** cada panel tiene título a la izquierda y botones a la derecha (estilo Cursor/VS Code):
- **Maximizar** — ocupa todo el espacio del módulo; guarda el layout anterior para restaurar
- **Cerrar** — oculta el panel (equivalente a desmarcarlo en Ver → Paneles)
- El menú **Ver** y los botones de cabecera están sincronizados

### Menú Archivo (implementado)
- **Nuevo** — crea proyecto en memoria (sin fichero hasta Guardar como)
- **Abrir** — submenú con recientes + «Abrir archivo…» (sin aviso si no hay proyecto abierto)
- **Guardar** / **Guardar como…**
- **Exportar** — copia del JSON del proyecto
- **Salir** — confirma si hay cambios sin guardar

### Indicador de documento (patrón IDE)

| Zona | Contenido |
|------|-----------|
| **Toolbar** (derecha, `ProjectTitleWidget`) | Solo lectura: `● Nombre del show` o «Sin proyecto» |
| **Título de ventana** | `CONTROLADORF` (fijo) |
| **Barra de estado** (izquierda) | Ruta completa del `.crf` o vacío si no hay proyecto |
| **Renombrar show** | Archivo → Renombrar show… |

### Barra de herramientas por módulo
| Módulo | Botones |
|--------|---------|
| Inventario RF | Nuevo, Editar, Duplicar, Eliminar, Aplicar, Revertir, Columnas, Importar, Exportar lista |
| Coordinación | (vacía) |
| Monitor | (vacía — previsto: SDR, alarmas, sync inventario) |

### Menú Ver
- Visibilidad de Lista / Propiedades / Acciones (del módulo activo)
- Reiniciar paneles (restaura tamaños y visibilidad; sale del modo maximizado)

---

## Extensión del fichero de proyecto

**Única extensión admitida:** `.crf` (Controlado**RF**), contenido JSON UTF-8.

- Filtro del diálogo: `Proyecto CONTROLADORF (*.crf)`
- Nombre sugerido al guardar: `{nombre_del_show}.crf` (editable en el diálogo)

---

## Formato de proyecto `.crf` (esqueleto v1.0)

Fichero portable del show. Se irá ampliando en fases sucesivas.

```json
{
  "format_version": "1.0",
  "metadata": {
    "name": "Nuevo proyecto",
    "created_at": "2026-06-12T12:00:00+00:00",
    "modified_at": "2026-06-12T12:00:00+00:00",
    "app_version": "0.1.0"
  },
  "modules": {
    "inventario_rf": { "equipos": [] },
    "coordinacion": {},
    "monitor": {}
  },
  "ui": {
    "active_module": "inventario_rf",
    "modules": {
      "inventario_rf": {
        "splitter_main": [720, 280],
        "splitter_left": [420, 260],
        "panel_visibility": { "lista": true, "propiedades": true, "acciones": true },
        "maximized_panel": null,
        "pre_maximize": {}
      },
      "coordinacion": {},
      "monitor": {}
    }
  }
}
```

**Persistencia de layout por pestaña:**
- `splitter_main` — proporciones horizontal (columna izquierda | propiedades)
- `splitter_left` — proporciones vertical (lista | acciones)
- `panel_visibility` — visibilidad de cada panel
- `maximized_panel` — id del panel maximizado o `null`
- `pre_maximize` — layout guardado antes de maximizar (para restaurar al pulsar de nuevo □)

**Bug resuelto (pestañas):** `panel_visibility` se guarda con `not panel.isHidden()` (no `isVisible()`), porque al ocultar la pestaña Qt reporta los hijos como no visibles aunque el usuario no los haya cerrado.

### Código relacionado
| Componente | Ruta |
|------------|------|
| Modelo | `src/core/project_model.py` |
| I/O JSON | `src/core/project_io.py` |
| Gestor | `src/core/project_manager.py` |
| Pestañas + paneles | `src/gui/module_tab_manager.py`, `src/gui/module_workspace.py` |
| Ventana principal | `src/gui/main_window.py` |

---

## Inventario RF — roadmap

| Fase | Contenido |
|------|-----------|
| **2a** ✅ | Parser `.shw` Workbench, modelos, tests — ver `docs/import_workbench.md` |
| **2b** ✅ | Archivo → Importar Workbench, tabla equipos, Herramientas → Estructura del proyecto |
| **2c** ✅ | Import coordinación + tabla inventario con columnas persistentes |
| **3** ✅ | CRUD, metadatos, bloqueo, export lista CSV/JSON/PDF — ver `docs/inventario_edicion.md` |
| **4 Coordinación** | Planificación RF, exclusiones, asignaciones (placeholder) |
| **5 Monitor** | Analizador SDR + supervisión portadoras + alarmas — ver `docs/monitor.md` |

Importación prevista como **show completo** (metadatos + inventario + coordinación progresiva), no solo CSV de inventario.

---

## Módulo Monitor — resumen

> **v1.0.0:** estudio y documentación de la cadena RF en [`docs/rf_engine/00_README.md`](rf_engine/00_README.md) — refactorización planificada antes de más parches AUTO.

Aplicación **embebida en la pestaña Monitor** para:

- **Analizador de espectro SDR** en tiempo real (referencia: SDR++, SDR#, Airspy Suite): FFT central + espectrograma inferior.
- **Panel de configuración** izquierdo: dispositivo SDR, FFT, demodulador, alarmas, importación de frecuencias del inventario.
- **Supervisión de portadoras** del show: marcas en espectro, umbrales configurables, gestor de alarmas y **logs de alarmas** persistentes.

**Enfoque de desarrollo:** primero analizador SDR completo (Fase M1); después integración inventario (M2); después supervisión y alarmas (M3–M4).

Documento completo: **[docs/monitor.md](monitor.md)**.

---

## Historial de fases

| Fase | Fecha | Contenido |
|------|-------|-----------|
| **0** | 2026-06-12 | Auditoría plantilla vs CONTROLADORF |
| **1** | 2026-06-12 | Shell GUI 3×3, menú Archivo, proyecto JSON esqueleto, decisión workspace/proyecto |
| **1b** | 2026-06-12 | Fix arranque + tests; extensión `.crf`; fix paneles al cambiar pestaña |
| **1d** | 2026-06-12 | Fix guardar/abrir: flush 3 módulos, no dirty al abrir |
| **1f** | 2026-06-12 | Indicador documento solo lectura; renombrar vía menú |
| **2a** | 2026-06-12 | Análisis + parser Workbench `.shw`; nombre por defecto «Proyecto» |
| **2b** | 2026-06-12 | Import Workbench (menú + toolbar), tabla inventario, árbol estructura |
| **2c** | 2026-06-12 | Import coordinación Workbench; columnas tabla persistentes |
| **3** | 2026-06 | CRUD inventario, metadatos, bloqueo, export, UI profesional |
| **M0** | 2026-06 | Diseño módulo Monitor — `docs/monitor.md` |
| 4 | — | Módulo Coordinación |
| 5 | — | Monitor M1–M4 (SDR, supervisión, alarmas) |

---

## Referencias

- Plantilla general: `docs/arquitectura_gral.md`, `docs/gui.md`
- Workspaces: `src/workspace/README.md`
- Import Workbench: `docs/import_workbench.md`
- Inventario RF: `docs/inventario_edicion.md`, `docs/inventario_bd.md`
- **Monitor (SDR / supervisión):** `docs/monitor.md`
- Capa core/BD: `docs/core.md`, `docs/db.md`
