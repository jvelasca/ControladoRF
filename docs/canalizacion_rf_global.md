# Canalización RF global — diseño CONTROLADORF

Documento maestro (Fase 1+) acordado con requisitos:

1. **Uso mundial** — catálogo de estándares y países/regiones más habituales.
2. **Modo canal en toda la APP** — no solo Monitor SDR.
3. **Restricciones visuales + avisos** — sombreado en espectro y alertas en gestor de frecuencias.

---

## Visión

CONTROLADORF debe poder operar en dos planos simultáneos:

| Plano | Qué es | Ejemplo |
|-------|--------|---------|
| **Físico (Hz)** | Lo que mide el SDR | 482.000 MHz |
| **Lógico (canal)** | Lo que entiende el operador | TDT ES canal 22 |

El catálogo global vive en **BD**; el inventario del proyecto (`inventory_channels`) **referencia** canales del catálogo cuando aplica.

---

## Estándares mundiales (prioridad v1)

Solo normas/países **más usados** en RF profesional e broadcast. Extensible por migraciones/JSON seed.

### Broadcast / TV

| ID | Nombre | Región | Notas |
|----|--------|--------|-------|
| `DVB-T_EU` | DVB-T/T2 Europa | EU | Canales 5–69 (histórico), UHF/VHF |
| `DVB-T_ES` | DVB-T España | ES | Subconjunto MITECO |
| `DVB-T_UK` | Freeview UK | GB | |
| `DVB-T_DE` | DVB-T Alemania | DE | |
| `ATSC_US` | ATSC 1.0/3.0 | US/CA/MX | Canales 2–51 |
| `ISDB-T_JP` | ISDB-T | JP/LATAM | |
| `DTMB_CN` | DTMB | CN | |

### FM radio

| ID | Nombre | Región | Canalización |
|----|--------|--------|--------------|
| `FM_EU_100K` | FM Europa 100 kHz | ITU Region 1 | 87.5–108 MHz, 100 kHz |
| `FM_US_200K` | FM USA 200 kHz | US | 88.1–107.9 MHz, 200 kHz |
| `FM_JP` | FM Japón | JP | 76–95 MHz |

### PMR / servicios

| ID | Nombre | Región |
|----|--------|--------|
| `PMR446_EU` | PMR446 | EU |
| `FRS_GMRS_US` | FRS/GMRS | US |
| `DAB_EU` | DAB/DAB+ | EU (bloques 5A–13F) |

### Microfonía inalámbrica (referencia)

| ID | Nombre | Notas |
|----|--------|-------|
| `UHF_TV_WS_EU` | Bandas UHF TV vacías | Para coordinación vs TDT |
| `LICENSED_UHF_EU` | Bandas licenciadas genéricas EU | Por país en `rf_standard_regions` |

> v1 implementa **seed JSON** + 3–4 estándares completos (FM_EU, FM_US, DVB-T_ES, DVB-T_EU). El resto se añade sin cambiar esquema.

---

## Modelo de datos (SQLite)

Migración `006_rf_channelization` (prevista):

```sql
-- Estándar (norma + banda)
CREATE TABLE rf_standards (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    region_code TEXT NOT NULL DEFAULT '',
    service_type TEXT NOT NULL,  -- fm | dvb-t | atsc | dab | pmr | custom
    freq_min_hz REAL,
    freq_max_hz REAL,
    channel_spacing_hz REAL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    enabled INTEGER NOT NULL DEFAULT 1
);

-- Canal dentro de un estándar
CREATE TABLE rf_standard_channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    standard_id TEXT NOT NULL REFERENCES rf_standards(id),
    channel_number INTEGER,
    channel_label TEXT NOT NULL DEFAULT '',
    center_freq_hz REAL NOT NULL,
    bandwidth_hz REAL NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE(standard_id, channel_label)
);

-- País / región → estándares activos por defecto
CREATE TABLE rf_standard_regions (
    region_code TEXT NOT NULL,   -- ISO 3166-1 alpha-2 o macro (EU, LATAM)
    standard_id TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (region_code, standard_id)
);

-- Restricciones (solapamientos, guard bands)
CREATE TABLE rf_channel_restrictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    standard_id TEXT NOT NULL,
    label TEXT NOT NULL,
    freq_min_hz REAL NOT NULL,
    freq_max_hz REAL NOT NULL,
    severity TEXT NOT NULL DEFAULT 'warning',  -- info | warning | block
    color_hex TEXT NOT NULL DEFAULT '#c04040',
    message_key TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

-- Preferencias globales APP (una fila lógica)
-- Alternativa: ampliar app_metadata
CREATE TABLE rf_app_channelization (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

Claves en `rf_app_channelization`:

| key | valores |
|-----|---------|
| `input_mode` | `frequency` \| `channel` |
| `active_region` | `ES`, `US`, `EU`, … |
| `active_standards_json` | `["DVB-T_ES","FM_EU_100K"]` |
| `show_spectrum_allocations` | `0` \| `1` |
| `show_restrictions` | `0` \| `1` |

Vínculo inventario → catálogo (migración `007`):

```sql
ALTER TABLE inventory_channels ADD COLUMN rf_standard_id TEXT;
ALTER TABLE inventory_channels ADD COLUMN rf_standard_channel_id INTEGER;
```

---

## Modo canal en toda la APP

Estado global (`ApplicationServices` / `WorkspaceStore`):

```python
@dataclass
class ChannelizationState:
    input_mode: str  # "frequency" | "channel"
    active_region: str
    active_standard_ids: tuple[str, ...]
    show_allocations: bool
    show_restrictions: bool
```

### Puntos de integración

| Módulo | Comportamiento en modo **canal** |
|--------|----------------------------------|
| Barra frecuencia (Monitor) | Combo canal + etiqueta; Hz solo lectura o secundario |
| Gestor de frecuencias | Columnas canal / estándar; botón «Estándares» |
| Inventario | Asignación a canal DVB-T / FM europeo |
| Marcadores | Tooltip «Canal 22 (482 MHz)» |
| Supervisión / alarmas | Mensajes en canal, no solo Hz |
| Export / informes | Canal + estándar + Hz |

Servicio central: `core/rf/channelization_service.py`

- `resolve_channel(standard_id, label) → freq_hz`
- `resolve_frequency(standard_id, freq_hz) → nearest channel`
- `list_standards(region) → …`
- `check_restrictions(freq_hz, standards) → list[RestrictionHit]`

---

## Capa gráfica espectro

### Franja de asignaciones (modo CANAL)

Debajo del eje X, **sin afectar al waterfall**:

```
[── Ch21 ──][── Ch22 ──][── Ch23 ──]
     ↑ clic → sintoniza canal
```

- Color por `service_type` (TDT azul, FM verde, PMR ámbar).
- Opacidad baja; no escucha el espectro.

### Capa restricciones (opcional ON)

Sombreado semitransparente (p. ej. rojo `#c0404088`) donde:

- Un marcador/inventario en UHF solapa canal TDT subyacente.
- Guard band de estándar activo.

**Aviso en gestor:** fila amarilla/roja + tooltip «Posible conflicto: canal TDT 22 bajo esta frecuencia».

---

## Menú Herramientas → Gestión de canalizaciones

Diálogo maestro:

1. **Región activa** (combo países principales + EU/US/LATAM/APAC).
2. **Estándares habilitados** (checkbox por fila del catálogo).
3. **Tabla canal ↔ MHz ↔ BW** (filtro por estándar).
4. **Modo entrada global** (Hz / Canal).
5. **Opciones gráficas** (asignaciones / restricciones).

Desde **Gestor de frecuencias**: icono 📋 abre la misma tabla filtrada por banda del span actual.

---

## Roadmap

| Fase | Entregable | Estado |
|------|------------|--------|
| **0** | Panel demod: BW/OBW dinámico, ACP mini-VU, RDS colapsable | En curso |
| **1a** | Migración BD + seed FM_EU, FM_US, DVB-T_ES, DVB-T_EU | Pendiente |
| **1b** | Menú Herramientas (consulta + activar estándares) | Pendiente |
| **2** | `ChannelizationState` global + barra frecuencia modo canal | Pendiente |
| **3** | Franja espectro asignaciones | Pendiente |
| **4** | Restricciones visual + gestor frecuencias | Pendiente |
| **5** | Inventario ↔ catálogo + informes | Pendiente |

---

## Referencias de producto (benchmark)

| Producto | Qué copiar |
|----------|------------|
| Shure Wireless Workbench | Planos TV/UHF, coordinación vs DTV |
| RF Venue | Regiones y bandas licenciadas |
| Sennheiser WSM | Modo canal en coordinación |
| SDR++ / SDR# | Entrada MHz simple (no canal) — nosotros añadimos capa encima |

---

## Decisiones cerradas

- Catálogo **mundial** (estándares principales, no todos los países).
- Modo canal **global** en toda la APP.
- Restricciones **visuales y lógicas** desde el inicio del diseño.

Próximo paso de implementación: **Fase 1a** (migración + seed + repositorio `RfStandardRepository`).
