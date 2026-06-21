# Importación Shure Wireless Workbench (.shw)

Documento de análisis y plan de implementación — Fase 2.

Fichero de referencia en el repo: `auxiliares/ejempo impor workbench.shw`

---

## Objetivo

Importar un **show de Workbench** (no solo CSV de inventario) y convertirlo en un **proyecto CONTROLADORF** (`.crf`) con:

1. Metadatos del show (nombre, cliente, contacto)
2. Inventario RF completo (dispositivos + canales + frecuencias)
3. *(fases posteriores)* coordinación, exclusiones, band plans
4. *(fases posteriores)* datos útiles para el módulo **Monitor** (orden de canales, registry)

Perspectiva futura: el inventario importado alimentará el **Monitor** (vigilancia en tiempo real vía SDR / analizadores de espectro sobre las frecuencias del show).

---

## Formato `.shw`

| Propiedad | Valor (ejemplo) |
|-----------|-----------------|
| Formato real | **XML UTF-8** (extensión `.shw`) |
| Raíz | `<show appl_version="7.8.1.56" …>` |
| Show analizado | **Concierto Madrid** — GAIN Audio — Workbench 7.8.1.56 |

### Secciones principales del XML

| Sección | Versión | Contenido | Fase CONTROLADORF |
|---------|---------|-----------|-------------------|
| `show_properties` | 1.0 | Nombre, cliente, contacto, venue, notas | **2a** ✅ metadatos |
| `inventory` | 2.1 | Dispositivos RF + canales + frecuencias | **2a** ✅ inventario |
| `coordination_info` | — | Gestión canales, scan, exclusiones, band planning | **2c** |
| `coordinated_data_root` | 0.3 | Resultado coordinación (asignaciones finales) | **2c** |
| `CFLs` | 1.0 | Custom frequency lists | **2c** |
| `plot_info` | — | Gráficos / plot | omitir |
| `band_plan_group_list` | 1.0 | Planes de banda | **2c** |
| `monitoring_info` | 2.2 | Orden monitor, registry, autolog | **4** (Monitor) |

---

## Inventario del ejemplo (`Concierto Madrid`)

| Métrica | Valor |
|---------|-------|
| Dispositivos | 14 |
| Canales RF | 24 |
| Series | ULXD (3), UHFR (2), PSM1000 (2), EW 500 G3 (2), EM 3732-II (1), SR 2050 (4) |
| Bandas | K51, J5, L8, J8, B, L, Aw, Bw |
| Rango frecuencias | 472,825 – 696,675 MHz |

### Unidades de frecuencia

Workbench guarda `<frequency>` como **entero en kHz**:

```
658175  →  658,175 MHz
472825  →  472,825 MHz
```

Función: `frequency_khz_to_mhz(value) = value / 1000`

### Estructura de un `<device>`

Campos relevantes para CONTROLADORF (Fase 2a):

- `id` (+ atributo `dcid`) — identificadores Workbench
- `series`, `model`, `manufacturer`, `band`, `zone`
- `device_name` — etiqueta en Workbench
- `<channel number="N">` — uno o varios por dispositivo
  - `channel_name`, `frequency`, `color`, `audio_gain`, `audio_mute`

Campos ignorados por ahora (hex blobs, Dante, scan capabilities, etc.).

---

## Modelo CONTROLADORF (intermedio)

Implementado en `src/importers/workbench_models.py`:

```
WorkbenchShow
├── info (name, customer, contact)
├── devices[]
│   └── channels[] (number, name, frequency_mhz, …)
└── to_inventory_dicts() → project.modules.inventario_rf.equipos[]
```

Cada **fila de inventario** = un **canal RF** (no un solo transmisor físico), coherente con Workbench y con futura vigilancia por frecuencia en Monitor.

---

## Parser (Fase 2a — implementado)

| Archivo | Rol |
|---------|-----|
| `src/importers/workbench_parser.py` | `parse_workbench_show()`, `apply_workbench_inventory_to_project()` |
| `scripts/analyze_workbench_shw.py` | Análisis rápido desde terminal |
| `tests/importers/test_workbench_parser.py` | Tests contra el fichero de `auxiliares/` |

```python
from importers.workbench_parser import parse_workbench_show, apply_workbench_inventory_to_project

show = parse_workbench_show("auxiliares/ejempo impor workbench.shw")
project = Project.create_new()
apply_workbench_inventory_to_project(project, show)
# project.name == "Concierto Madrid"
# len(project.modules["inventario_rf"]["equipos"]) == 24
```

---

## Flujo de importación (UI — Fase 2b ✅)

```
Archivo → Importar desde Workbench…  (*.shw)
    │   (también: toolbar «Importar» en Inventario RF)
    │
    ├─ ¿Proyecto sin guardar con cambios? → confirmar
    │
    ├─ parse_workbench_show()
    │
    ├─ WorkbenchImportDialog:
    │     • Crear proyecto nuevo desde el show
    │     • Reemplazar inventario del proyecto actual
    │
    ├─ apply_workbench_inventory_to_project()
    │
    ├─ Pestaña Inventario RF + InventoryListPanel (tabla de canales)
    │
    └─ Usuario guarda .crf + (fase 3) persistir en SQLite

Herramientas → Estructura del proyecto…
    └─ ProjectStructureDialog (árbol: metadatos, módulos, dispositivos/canales, UI)
```

| Archivo | Rol |
|---------|-----|
| `src/gui/workbench_import_dialog.py` | Diálogo de modo de importación |
| `src/gui/inventory_list_panel.py` | Tabla de canales RF en panel Lista |
| `src/gui/project_structure_dialog.py` | Explorador en árbol |
| `src/core/project_structure.py` | `build_project_structure_tree()` |
| `src/gui/main_window.py` | Orquestación Archivo / Herramientas |

---

## Roadmap por fases

| Fase | Entregable |
|------|------------|
| **2a** ✅ | Parser `.shw`, modelos, tests, documentación |
| **2b** ✅ | Archivo → Importar Workbench, tabla inventario, explorador estructura |
| **2c** ✅ | Import coordinación + columnas configurables persistentes en tabla |
| **3** ✅ | CRUD inventario, SQLite sync, export lista |
| **4 Monitor M1** | Analizador SDR (espectro + waterfall) — ver `docs/monitor.md` |
| **5 Monitor M2+** | Marcas inventario, supervisión, alarmas, logs |

---

## Relación Monitor (perspectiva)

Documento maestro: **`docs/monitor.md`**.

El módulo **Monitor** necesitará, por canal importado:

- `frequency_mhz` — objetivo de vigilancia y marca en espectro
- `channel_name` / `device_name` — etiqueta en UI y alarmas
- `model` / `band` / `zone` — contexto RF y filtros
- `color` — color de marca en espectro
- `coordination_include` / `coordination_active` — filtro de canales a supervisar *(fase M2+)*
- *(fase M3)* tolerancia de nivel, desviación de frecuencia, anchura de banda, reglas de alarma
- *(fase M4)* histórico en log de alarmas SQLite

Por eso el inventario se modela **por canal**, no solo por caja física.

### Sección `monitoring_info` (Workbench)

Al importar `.shw`, la sección `monitoring_info` (v2.2) quedará reservada para:

- Orden de presentación en panel de supervisión
- Registry dispositivo ↔ canal
- Inspiración para autolog de alarmas

La importación de `monitoring_info` al `.crf` es **fase posterior**; el Monitor puede arrancar con el inventario RF ya disponible.

---

## Comandos útiles

```powershell
$env:PYTHONPATH="src"
.\env\Scripts\python.exe scripts\analyze_workbench_shw.py
.\env\Scripts\python.exe -m pytest tests/importers -q
```

---

## Referencias

- `docs/arquitectura_APP.md` — arquitectura global
- Shure Wireless Workbench — export/show file (XML `.shw`)
