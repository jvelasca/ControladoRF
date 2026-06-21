# Módulo Monitor — Visión, arquitectura y roadmap

Documento maestro del módulo **Monitor** de CONTROLADORF: analizador de espectro SDR en tiempo real, supervisión de portadoras del show y sistema de alarmas con registro histórico.

**Estado actual:** v1.0.0 — estudio arquitectura RF (`docs/rf_engine/`). M1 Monitor en curso — UI analizador, toolbar LCD, asistente SDR multiplataforma (HackRF/Airspy/HF+). Ver [monitor_sdr_setup.md](monitor_sdr_setup.md).  
**Id interno:** `monitor` · **Pestaña principal:** Monitor

---

## 1. Objetivo del módulo

Desarrollar una aplicación **completa en tiempo real** de:

1. **Analizador de espectro y radio SDR** — recepción, FFT, visualización y demodulación.
2. **Supervisión de portadoras en aire** — cada canal RF del inventario del proyecto como objetivo de vigilancia.
3. **Detección de problemas** — umbrales y reglas configurables por canal o grupo.
4. **Gestión de alarmas** — niveles, estados, notificación al operador y **logs de alarmas** persistentes.
5. *(Futuro)* **Acciones automáticas** — respuestas configurables ante ciertos tipos de alarma.

La idea central: **importar las frecuencias (y metadatos) del inventario RF** del proyecto `.crf`, representarlas como **marcas en el espectro** y medir continuamente parámetros RF (nivel, ocupación, desviación, presencia/ausencia, etc.) para detectar incidencias antes o durante el show.

---

## 2. Posición en CONTROLADORF

```
┌─────────────────────────────────────────────────────────────┐
│  Inventario RF          Coordinación           Monitor       │
│  (qué hay en el show)   (planificación)        (qué pasa     │
│                                                 en aire)     │
└─────────────────────────────────────────────────────────────┘
         │                      │                      ▲
         └──────────────────────┴──────────────────────┘
                    mismo proyecto .crf
```

| Módulo | Aporta al Monitor |
|--------|-------------------|
| **Inventario RF** | `frequency_mhz`, `channel_name`, `device_name`, `band`, `zone`, `model`, bloqueo, color, metadatos |
| **Import Workbench** | `monitoring_info` en `.shw` (orden monitor, registry, autolog) — fase posterior |
| **Coordinación** | Asignaciones finales, exclusiones, estado activo/incluido — contexto para umbrales |

El Monitor **no sustituye** al inventario: **lee** canales activos del proyecto y opcionalmente permite filtrar por zona, banda o grupo.

---

## 3. Referencias de mercado (investigación)

Antes de implementar, el diseño se basa en el comportamiento de aplicaciones SDR de referencia. No se trata de copiar código, sino de **replicar flujos de operador** ya validados en producción y RF técnico.

### 3.1 SDR++ (referencia principal de UI)

| Aspecto | Comportamiento típico | Implicación CONTROLADORF |
|---------|----------------------|---------------------------|
| **Fuente IQ** | Plugin por hardware (RTL-SDR, Airspy, HackRF, etc.) | Capa `sdr/` desacoplada; interfaz común de dispositivo |
| **Espectro (FFT)** | Vista central, rango configurable, zoom/pan, peak hold | Panel central del módulo Monitor |
| **Waterfall / espectrograma** | Historial temporal debajo del espectro, colormap | Panel inferior del módulo Monitor |
| **VFO / marcadores** | Frecuencias seleccionadas, ancho de banda visual | Base para **marcas de inventario** |
| **Demodulador** | AM/FM/SSB, ancho de canal, squelch | Panel izquierdo — configuración SDR |
| **Sample rate / gain** | Controles en barra lateral o menú dispositivo | Panel izquierdo — configuración analizador |
| **Buffering** | Ring buffer IQ → FFT pipeline en hilo separado | Obligatorio para no bloquear GUI PyQt6 |

### 3.2 SDR# (SDRSharp) / ecosistema Airspy

| Aspecto | Comportamiento típico | Implicación CONTROLADORF |
|---------|----------------------|---------------------------|
| **Integración Airspy** | Airspy R2, Mini, HF+ vía API nativa | Priorizar soporte Airspy si el hardware objetivo lo exige |
| **Spectrum display** | Cursor con frecuencia + nivel en dBFS/dBm | Tooltip / barra de estado Monitor |
| **Recording** | IQ o audio demodulado | Fase posterior — evidencia para alarmas |
| **Plugins** | Extensibilidad | Inspiración para plugins de supervisión por canal |

### 3.3 Wireless Workbench (contexto show, no SDR)

Workbench no es un SDR, pero define **qué vigilar**: lista ordenada de canales, colores, registry de monitorización. CONTROLADORF ya importa inventario por canal; el Monitor añade la capa **medición en vivo**.

### 3.4 Patrón común a replicar (pipeline)

```
[Hardware SDR] → [Driver/API] → [IQ stream]
       → [Ring buffer]
       → [FFT / DSP] → espectro instantáneo
       → [Waterfall history] → espectrograma
       → [Demodulator branch] → audio (opcional)
       → [Supervisor] → comparar con marcas inventario → alarmas → logs
```

**Principio:** la GUI solo **consume** espectros ya calculados (señales Qt o buffers compartidos); el procesamiento IQ vive en **hilos/workers** fuera del hilo principal.

---

## 3.5 Modos de operación (Espectro · SDR · Supervisión)

Un **único motor IQ + FFT** sirve a tres perfiles de operación. Cambiar de modo **no reinicia** el hardware; solo activa ramas distintas y ajusta la UI.

```
                    ┌─────────────────────────────────┐
                    │     MonitorSession / Engine      │
                    │  capture → ring buffer → FFT     │
                    └───────────────┬─────────────────┘
                                    │
          ┌─────────────────────────┼─────────────────────────┐
          ▼                         ▼                         ▼
   Modo ESPECTRO              Modo SDR                 Modo SUPERVISIÓN
   (analizador puro)          (demod + audio)          (show — M2+)
          │                         │                         │
   Toolbar medición           Panel RADIO               Marcas inventario
   Sin audio                  FM/AM, squelch            Umbrales + alarmas
   Vista panorámica           Diagnóstico canal         Valor diferencial CRf
```

| Modo | Id interno | Uso principal | Audio | Estado |
|------|------------|---------------|-------|--------|
| **Espectro** | `spectrum` | Medición, waterfall, vista de muchas portadoras | No | **Implementado** (toolbar + FFT) |
| **SDR** | `sdr` | Escuchar/diagnosticar un canal (micro FM analógico) | Sí *(pendiente salida)* | **UI + params**; demod en curso |

La **supervisión del show** (marcas inventario, alarmas) queda **integrada en modo Analizador**, no como tercer botón.

**Selector toolbar:** un botón PLAY/STOP (cambia color) · **Analizador | SDR** · cuadro **FC/F** con menú contextual.

**Objetivo del show:** el operador usa **Espectro** (y luego **Supervisión**) casi todo el tiempo; pasa a **SDR** solo para investigar una incidencia.

**Código:** `MonitorOperatingMode` en `src/core/monitor/monitor_operating_mode.py` · campos en `SpectrumParams` · rama `DemodBranch` (stub) · panel `MonitorRadioPanel`.

**Nota digital vs analógico:** micros/IEM digitales se supervisan por **presencia y nivel en espectro**; la demodulación FM solo aplica a equipos analógicos.

### 3.6 Resolución (FFT/RBW), suavizado (SUAV) y barrido (SWT) *(M1 — implementado)*

Controles en **toolbar** (FFT o RBW · SUAV · SWT) y franja azul. Documentación técnica: **[monitor_bw_trace.md](monitor_bw_trace.md)**.

| Parámetro UI | Función | Campos `SpectrumParams` |
|--------------|---------|-------------------------|
| **FFT** (IQ) / **RBW** (barrido) | Resolución en frecuencia | `rbw_hz`, `rbw_auto`, `fft_size` |
| **SUAV** | Suavizado espacial de la traza (bins adyacentes) | `trace_smooth_auto`, `trace_smooth_bins` |
| **SWT** | Tiempo de barrido en modo `sweep` | `sweep_time_ms`, `sweep_auto` |
| **Traza** | Clear/Write, Max/Min Hold, Average + detector | `trace_mode`, `detector` |

**Importante:** SUAV en AUTO = **OFF** (no copia RBW). El suavizado es independiente de la resolución.

Persistencia: `rbw_*`, `trace_smooth_*`, `sweep_*`, `trace_mode`, `detector` en `spectrum_params_io.py`. Proyectos con `vbw_*` se migran al cargar.

---

### 3.7 Lectura FC / F, SPAN y marcador principal *(M1 — implementado)*

Comportamiento alineado con analizadores profesionales (R&S, SDR++):

| Concepto | Comportamiento |
|----------|----------------|
| **FC** | Frecuencia central de la ventana. Mover FC recentra el span; el marcador sigue el centro. |
| **F** | Frecuencia analizada independiente. Mover F **no** cambia FC/SPAN salvo **auto-pan** (opcional). |
| **SPAN** | Mismo valor en toolbar, slider superior y franja azul inferior (`display_span_hz` en `monitor_freq_span_logic.py`). |
| **Marcador** | Línea vertical fina (1 px) siempre visible en la frecuencia activa (FC o F). Etiqueta encima: `F: … · nivel · S/R`. |
| **Visibilidad** | Clic en la etiqueta → diálogo para mostrar/ocultar línea, frecuencia, nivel, S/R y auto-pan. |
| **Persistencia** | Claves `marker_show_*` y `marker_auto_pan` en `SpectrumParams` / `spectrum_params_io.py`. |

**Código:** `active_marker_freq_hz`, `ensure_marker_visible` · `marker_analysis.py` (interpolación + S/R) · `monitor_spectrum_widget.py` (pintado) · `monitor_marker_config_dialog.py`.

**Arranque HackRF:** el motor espera el primer trazo válido (`SpectrumEngine._warmup_capture`) y aumenta el retardo post-`hackrf_transfer start` para evitar PLAY vacío al conectar USB.

### 3.8 Transición Analizador ↔ SDR y SPAN amplio *(M1 — implementado)*

HackRF (y la mayoría de SDR) tienen **dos anchos distintos**:

| Concepto | Analizador (`spectrum`) | SDR (`sdr`) |
|----------|-------------------------|-------------|
| **BW máximo** | Lapso en FC (hasta GHz vía barrido) | ~20 MHz IQ instantáneo |
| **Captura** | `sweep` si SPAN > 20 MHz | siempre `iq` |
| **Audio / demod** | No | Sí (panel RADIO) |

**Patrón profesional** (SDR++, R&S, Workbench “Tune vs Scan”): al cambiar modo **no se pierde la FC**; el lapso analizador se **guarda** y en SDR solo se **limita** la vista al BW del hardware.

```
Analizador  FC=500 MHz  SPAN=80 MHz  capture=sweep
      │  toolbar [Analizador | SDR]
      ▼
SDR         FC=500 MHz  SPAN=20 MHz  capture=iq
            analyzer_span_hz=80M guardado en sesión
      │  toolbar [Analizador | SDR]
      ▼
Analizador  FC=500 MHz  SPAN=80 MHz  capture=sweep  (restaurado)
```

**Campos `SpectrumParams`:**

| Campo | Rol |
|-------|-----|
| `manual_span_hz` | SPAN activo en UI |
| `last_span_hz` | Memoria del botón SPAN «Último» (independiente del cambio de modo) |
| `analyzer_span_hz` | Lapso guardado al entrar en SDR (0 = sin backup) |
| `analyzer_span_mode` | Modo SPAN guardado (`manual`, `full`, …) |

**Flujo (`transition_operating_mode` en `monitor_mode_profile.py`):**

1. **Analizador → SDR:** guardar lapso/modo en `analyzer_span_*` → FC igual → SPAN activo:
   - si lapso **> 20 MHz** → acotar a 20 MHz (mensaje de aviso);
   - si lapso **≤ 20 MHz** → **mantener** (no forzar siempre al máximo).
2. **SDR → Analizador:** restaurar `analyzer_span_hz` y `analyzer_span_mode` → `refresh_capture_and_span_limits` elige `sweep` o `iq` según lapso.

**Convención adoptada:** la **A** (preservar SPAN estrecho en SDR). No se amplía automáticamente a 20 MHz al entrar en SDR si el analizador ya mostraba menos (p. ej. 10 MHz → 10 MHz).

**Reglas:** no recortar `last_span_hz` al entrar en SDR; la supervisión del show sigue en modo Analizador (barrido); SDR es diagnóstico puntual de un canal.

**Tests:** `tests/core/test_monitor_mode_transition.py`.

---

## 4. Layout GUI propuesto (módulo Monitor)

Misma filosofía que Inventario RF: **pestaña Monitor** con paneles internos (`QSplitter`), no docks globales.

```
┌─ Menú / Toolbar (contextual Monitor) ─────────────────────────────┐
│ [ Monitor ]                                                        │
├───────────────────────────────────────────────────────────────────┤
│ ┌─ Panel izq. ────┬─ Panel central (espectro FFT) ─────────────┐ │
│ │ Dispositivo     │  ▁▂▃▅▇ Espectro en tiempo real              │ │
│ │ (conexión SDR)  │  |    |    | marcas inventario              │ │
│ │                 │  ─────────────────────────────────────────  │ │
│ │ DEBUG ▾         ├─ Panel inferior (espectrograma) ──────────┤ │
│ │ • Radio         │  ░░▒▒▓▓██ waterfall / historial temporal   │ │
│ │ • Recorder      │                                              │ │
│ │ • Display       │                                              │ │
│ └─────────────────┴──────────────────────────────────────────────┘ │
├─ Status bar: frecuencia bajo cursor · nivel · estado SDR · alarmas │
└───────────────────────────────────────────────────────────────────┘
```

### Mapeo de paneles (`monitor`) — implementado

| Id interno | Menú **Ver** / título | Posición | Contenido |
|------------|----------------------|----------|-----------|
| `lista` | Espectro | Central + superior | FFT interactivo, toolbar, overlays |
| `acciones` | Espectrograma | Inferior | Waterfall |
| `propiedades` | Dispositivo | Lateral | **DISPOSITIVO** (selector + estado) → **RADIO** → … → **DEBUG** (sub-acordeón: drivers, diagnóstico). Captura con ▶ PLAY en toolbar. |

El menú **Ver** usa los mismos títulos e iconos que las cabeceras de panel; cambia automáticamente al activar la pestaña Monitor.

---

## 5. Fases de desarrollo (enfoque incremental)

Ir **por partes**, validando cada capa antes de la supervisión avanzada.

### Fase M0 — Investigación y spike técnico *(actual)*

| Entregable | Descripción |
|------------|-------------|
| Este documento | Visión, referencias, layout, roadmap |
| Spike SDR | Prototipo mínimo: abrir dispositivo, FFT, pintar en QWidget (sin integración proyecto) |
| Decisión hardware | RTL-SDR vs Airspy vs ambos vía capa abstracta |
| Dependencias | Evaluar: `pyrtlsdr`, bindings Airspy, o bridge a SDR++ / SoapySDR |

### Fase M1 — Analizador SDR completo (núcleo visual)

**Objetivo:** experiencia comparable a SDR++ / SDR# en lo esencial.

- Modos de operación: **Espectro** (analizador puro) · **SDR** (demod) · **Supervisión** (flag M2+)
- Conexión y configuración de dispositivo SDR
- Espectro FFT en tiempo real (panel central)
- Espectrograma (panel inferior)
- Controles: centro/frecuencia, span, RBW/VBW, gain, sample rate
- Demodulador básico (al menos FM/AM) — panel izquierdo
- Hilos de captura + FFT desacoplados de PyQt6
- Persistencia de prefs SDR en workspace (no en `.crf`)

**Criterio de éxito:** operador puede escuchar y ver el espectro local sin proyecto abierto.

### Fase M2 — Integración con inventario

- Importar / sincronizar canales del proyecto `.crf`
- **Marcas en espectro:** línea o banda por `frequency_mhz`, etiqueta `channel_name`, color desde inventario
- Filtros: solo activos, por zona, por banda
- Panel: lista de canales supervisados con estado «no medido / OK / aviso»

**Criterio de éxito:** abrir un `.crf` y ver todas las portadoras del show marcadas en el espectro.

### Fase M3 — Supervisión, umbrales y gestor de alarmas

**Premisas de producto y ventaja competitiva:** [monitor_supervision_premisas.md](monitor_supervision_premisas.md)  
**Arquitectura técnica v2:** [monitor_supervision.md](monitor_supervision.md)

- Parámetros configurables por canal o plantilla:
  - Nivel mínimo/máximo (dBm o relativo)
  - Desviación de frecuencia (± kHz)
  - Ausencia de portadora
  - Ocupación de banda / ancho efectivo
  - Persistencia temporal (debounce, hold time)
- **Niveles de alarma:** informativo, aviso, crítico
- **Gestor de alarmas:** cola activa, acknowledge, silenciar, escalado
- Notificación en status bar + panel derecho

**Criterio de éxito:** simular o detectar caída de nivel en una frecuencia de inventario y generar alarma visible.

### Fase M4 — Logs de alarmas y automatización

- **Log de alarmas** persistente (SQLite + export CSV/JSON)
- Campos: timestamp, canal, frecuencia, tipo, nivel, valor medido, umbral, operador ack
- Histórico consultable desde GUI
- Reglas de acción automática *(futuro)*: notificación, snapshot espectro, comando externo
- Integración con `monitoring_info` Workbench si aplica

Ver también: `docs/logging.md` (sección logs de alarmas vs log de aplicación).

---

## 6. Modelo conceptual de supervisión

### 6.1 Marca de canal (desde inventario)

```json
{
  "channel_key": "workbench:…",
  "frequency_mhz": 658.175,
  "label": "Vocal 1",
  "color": "#FFAA00",
  "band": "K51",
  "supervision": {
    "enabled": true,
    "level_min_dbm": -80,
    "level_max_dbm": -20,
    "freq_tolerance_khz": 12.5,
    "carrier_loss_hold_ms": 500
  }
}
```

Persistencia prevista: `project.modules.monitor.supervision` o tabla SQLite vinculada a `channel_key`.

### 6.2 Alarma

```json
{
  "id": "uuid",
  "channel_key": "…",
  "raised_at": "2026-06-12T20:15:00Z",
  "cleared_at": null,
  "severity": "warning",
  "rule": "level_below_min",
  "measured_dbm": -95.2,
  "threshold_dbm": -80,
  "message": "Nivel bajo en Vocal 1 (658,175 MHz)",
  "ack_by": null
}
```

### 6.3 Gestor de alarmas (componente lógico)

```
MeasurementEngine ──► RuleEvaluator ──► AlarmManager ──► AlarmLogRepository
                              │                │
                              │                └──► GUI (panel alarmas)
                              └──► Marcas inventario (estado por canal)
```

- **MeasurementEngine:** extrae nivel/desviación en ventana alrededor de cada marca
- **RuleEvaluator:** aplica umbrales con histéresis y debounce
- **AlarmManager:** estados `raised` / `acknowledged` / `cleared`, sin duplicar alarmas activas
- **AlarmLogRepository:** append-only para auditoría post-show

---

## 7. Capas de código previstas

| Capa | Ruta propuesta | Responsabilidad |
|------|----------------|-----------------|
| Modelo | `src/core/monitor/` | Canales supervisados, reglas, alarmas |
| Modos | `src/core/monitor/monitor_operating_mode.py` | Espectro / SDR / Supervisión |
| SDR / DSP | `src/core/monitor/` | Dispositivo, IQ, FFT, demod (`demod_branch.py`) |
| Servicios | `src/core/services/monitor_service.py` | Orquestación, sync inventario |
| GUI espectro | `src/gui/monitor/spectrum_widget.py` | Pintado OpenGL/Qt |
| GUI waterfall | `src/gui/monitor/waterfall_widget.py` | Espectrograma |
| GUI config | `src/gui/monitor/config_panel.py` | Panel izquierdo |
| GUI alarmas | `src/gui/monitor/alarm_panel.py` | Panel derecho |
| BD | `src/db/` migraciones | `monitor_alarms`, `monitor_measurements` *(fase M4)* |

La GUI **no** debe llamar APIs SDR directamente: solo suscribirse a un `MonitorSession` o `SpectrumProvider` en core.

---

## 8. Dependencias técnicas (a decidir en M0)

| Opción | Pros | Contras |
|--------|------|---------|
| **SoapySDR** | Multi-dispositivo unificado | Instalación nativa compleja en Windows |
| **pyrtlsdr** | Simple, barato | Solo RTL-SDR |
| **libairspy** / Python bindings | Rendimiento Airspy | Dependencia específica |
| **Proceso externo SDR++** | UI probada | Integración difícil, no embebido |

**Recomendación provisional:** capa abstracta `SdrDevice` + primer backend según hardware disponible en desarrollo; evaluar SoapySDR a medio plazo.

**Visualización:** `QOpenGLWidget` o `pyqtgraph` para espectro/waterfall a 30+ FPS.

---

## 9. Persistencia

| Dato | Dónde |
|------|-------|
| Prefs SDR (dispositivo, gain, colormap) | Workspace / `workspaces.json` |
| Umbrales por canal del show | Proyecto `.crf` → `modules.monitor` |
| Log histórico de alarmas | SQLite `app.db` (tablas dedicadas) + export |
| Snapshots espectro *(futuro)* | Ficheros en carpeta del proyecto o adjuntos |

---

## 10. Relación con Workbench `monitoring_info`

En `.shw` (sección `monitoring_info` v2.2): orden de monitor, registry, autolog.

| Campo Workbench | Uso previsto en CONTROLADORF |
|-----------------|------------------------------|
| Orden de canales | Orden en panel supervisión |
| Registry | Mapeo dispositivo físico ↔ canal lógico |
| Autolog | Inspiración para log automático de alarmas (M4) |

Importación en fase posterior; el Monitor puede arrancar solo con inventario RF.

---

## 11. Roadmap resumido

| Fase | Nombre | Entregable clave |
|------|--------|------------------|
| **M0** | Diseño | Documentación + spike SDR |
| **M1** | Analizador | Espectro + waterfall + config SDR |
| **M2** | Inventario | Marcas de frecuencia en espectro |
| **M3** | Supervisión | Umbrales + gestor alarmas |
| **M4** | Logs y auto | Histórico alarmas + acciones |

**Orden estricto acordado:** primero analizador tipo SDR++ **completo y usable**; después capa de supervisión de portadoras (valor diferencial de CONTROLADORF).

---

## 12. Decisiones abiertas (para ir definiendo contigo)

1. **Hardware SDR objetivo** en primera versión (RTL-SDR, Airspy Mini/R2, otro).
2. **Unidades de medida** en UI: dBFS vs dBm calibrado (¿calibración por dispositivo?).
3. **Renombrado de paneles** Monitor vs reutilizar lista/propiedades/acciones.
4. **Demodulador en v1** — modo SDR con panel RADIO; salida de audio en siguiente iteración.
5. **Modos de operación** — Espectro (default) · SDR · Supervisión (overlay M2).
6. **Frecuencia de actualización** GUI vs FFT size (latencia aceptable en show en vivo).
7. **Coordinación con módulo Coordinación** — ¿solo canales `coordination_active`?

---

## 13. Comandos y referencias del repo

```powershell
cd "...\ControladoRF V1\ControladoRF V1"
$env:PYTHONPATH="src"
.\env\Scripts\python.exe src\main.py
# Pestaña Monitor → placeholder hasta M1
```

| Documento | Relación |
|-----------|----------|
| `docs/arquitectura_APP.md` | Módulos, pestañas, `.crf` |
| `docs/import_workbench.md` | Inventario por canal, `monitoring_info` |
| `docs/inventario_edicion.md` | Campos exportables → marcas Monitor |
| `docs/logging.md` | Log app vs log alarmas |
| `docs/gui.md` | Apariencia, paneles, temas |

---

*Última actualización: 2026-06-12 — documento vivo; se ampliará en cada iteración contigo.*
