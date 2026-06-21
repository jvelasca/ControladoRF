# Edición del inventario RF

Guía de la edición CRUD, metadatos, foco contextual y atajos de teclado.

## Capas de datos

| Capa | Ubicación | Contenido |
|------|-----------|-----------|
| Documento | `.crf` → `modules.inventario_rf` | `equipos[]`, `list_metadata`, `group_metadata` |
| SQLite | `app.db` | `inventory_channels`, `inventory_scope_metadata` |

La fuente de verdad es el `.crf`. La BD se sincroniza al refrescar el inventario.

## Metadatos por elemento

Cada **canal**, **grupo** (según modo de agrupación) y la **lista completa** pueden tener:

| Campo | Tipo | Efecto |
|-------|------|--------|
| `notes` | texto | Notas libres |
| `color` | `#RRGGBB` | Tinte visual en tabla / cabecera de grupo |
| `locked` | bool | Impide edición, duplicado y borrado |

### Herencia de bloqueo

1. **Lista bloqueada** → todo el inventario queda protegido.
2. **Grupo bloqueado** → todos los canales que pertenecen a ese grupo (zona, red, tipo, etc.) quedan protegidos.
3. **Canal bloqueado** → solo ese canal.

## Foco contextual

Las acciones (panel Acciones, barra de herramientas, menú contextual) actúan sobre el **elemento con foco**:

| Foco | Cómo se selecciona | Acciones |
|------|-------------------|----------|
| **Lista** | Clic en zona de lista sin fila seleccionada | Nuevo, Editar metadatos de lista |
| **Grupo** | Clic en fila de sección agrupada | Editar metadatos, Duplicar/Eliminar todos los canales del grupo |
| **Canal** | Clic en fila de canal | CRUD del canal + metadatos |

Panel **Propiedades** muestra campos según el foco (metadatos siempre; campos RF/dispositivo solo en canal).

## Edición inline en tabla

- Celdas editables con **F2**, doble clic o tecleo directo (columnas de datos RF/dispositivo y **Notas** si está visible).
- Columnas **Bloq.** y **Color** son solo visualización (icono candado y muestra de color).
- Canales bloqueados: celdas no editables; botones Duplicar/Eliminar deshabilitados. Al intentar editar (F2, tecleo, foco en Propiedades) aparece un aviso en la barra de estado indicando que hay que desbloquear primero.
- Panel **Propiedades**: banner amarillo y campos atenuados cuando el elemento está bloqueado; la casilla **Bloqueado** sigue activa si el bloqueo es directo (para poder desbloquear).

## Columnas configurables

Abra el diálogo **Columnas visibles** desde:

- el botón **Columnas** de la barra de herramientas (módulo Inventario RF), o
- clic derecho en la **cabecera de la tabla** → «Configurar columnas…».

En el diálogo marque o desmarque cada columna (incl. Bloq., Color, Notas). Debe permanecer al menos una columna visible. En **Diseño**, use los tres botones de alineación (estilo Office: izquierda, centro, derecha) para tabular todas las celdas de datos; **Bloq.** y **Color** permanecen centradas. **Ajustar anchos** adapta el ancho de cada columna visible al contenido. **Restablecer columnas** recupera el layout por defecto (columnas ocultas y alineación a la izquierda).

También puede reordenar y redimensionar columnas directamente en la cabecera. La configuración se guarda con el proyecto.

Por defecto **Notas** está oculta; **Bloq.** y **Color** visibles como columnas estrechas.

## Barra de herramientas (gestión principal)

Toda la gestión CRUD del inventario se realiza desde la **barra de herramientas** y el panel **Propiedades** (Apply/Revert). El panel **Acciones** queda reservado para enlaces con Coordinación y Monitor.

Los botones Duplicar, Eliminar y Aplicar se **deshabilitan** automáticamente si el elemento está bloqueado (directamente o por herencia lista/grupo).

## Exportar lista

Desde la barra de herramientas del módulo **Inventario RF**, **Exportar lista** abre un diálogo para guardar solo la lista (no el proyecto completo):

| Formato | Contenido |
|---------|-----------|
| **CSV** | Tabla plana con cabeceras traducidas; separador `;` y UTF-8 con BOM (Excel). |
| **JSON** | Documento estructurado: metadatos de lista + array de canales con todas las propiedades. |
| **PDF** | Informe A4 apaisado: cabecera del proyecto, metadatos de lista, tabla resumen y **fichas detalladas por canal** al final (RF, dispositivo, coordinación, metadatos e identificación). |

Campos exportados por canal: datos RF, dispositivo, coordinación, metadatos (notas, color, bloqueo) e identificadores (`channel_key`, origen Workbench, etc.).

El menú **Archivo → Exportar** sigue exportando el proyecto `.crf` completo.

---

## Relación con el módulo Monitor

Los canales exportados (CSV/JSON/PDF) contienen los mismos campos que alimentarán las **marcas de frecuencia** en el analizador SDR del Monitor (`frequency_mhz`, nombres, banda, color, etc.). Ver **`docs/monitor.md`**.

## Panel Acciones

Muestra el contexto del foco actual y, en el futuro, acciones externas (coordinación, monitorización). **No** incluye CRUD de inventario.

| Atajo | Acción |
|-------|--------|
| `Ctrl+N` | Nuevo canal |
| `F2` | Editar (abre propiedades) |
| `Ctrl+D` | Duplicar |
| `Supr` | Eliminar |
| `Ctrl+S` | Aplicar cambios en propiedades |
| `Esc` | Revertir cambios en propiedades |

## Esquema BD (migración `005_inventory_metadata`)

```sql
-- Canales: columnas nuevas
notes TEXT, color TEXT, locked INTEGER

-- Metadatos de lista y grupos
CREATE TABLE inventory_scope_metadata (
    project_key TEXT,
    scope_type TEXT,      -- 'list' | 'group'
    group_mode TEXT,      -- vacío para lista; 'zone', 'device_type', ...
    group_key TEXT,       -- clave del grupo
    notes TEXT, color TEXT, locked INTEGER,
    UNIQUE(project_key, scope_type, group_mode, group_key)
);
```

## Código relevante

| Módulo | Rol |
|--------|-----|
| `core/inventory_editor.py` | CRUD canales + campos editables |
| `core/inventory_metadata.py` | Metadatos lista/grupo + bloqueo |
| `core/inventory_group_ops.py` | Duplicar/eliminar grupo |
| `core/inventory_selection.py` | Modelo de foco |
| `gui/inventory_edit_controller.py` | Orquestación GUI |
| `gui/inventory_channel_table.py` | Tabla + inline + grupos |
| `gui/inventory_properties_panel.py` | Formulario Apply/Revert |
| `db/migration.py` | Migración `005` |

## Referencias

- Persistencia: [inventario_bd.md](inventario_bd.md)
- Arquitectura app: [arquitectura_APP.md](arquitectura_APP.md)
