# Monitor — Resolución (FFT/RBW) y suavizado de traza (SUAV)

Documento de referencia para programadores que mantengan la cadena **toolbar → SpectrumParams → motor → traza**.

Relacionado: [monitor.md](monitor.md) · código en `src/core/monitor/` y `src/gui/monitor/`.

**Auditoría en curso (jun 2026):** [audit/README.md](audit/README.md) — P preamp, span SDR, coherencia analizador/SDR.

---

## 1. Problema que resolvimos

En analizadores clásicos **RBW** (resolución) y **VBW** (video / suavizado temporal) son magnitudes en Hz y suelen confundirse en la UI.

En CONTROLADORF Monitor:

| Concepto | Qué controla | Unidad interna | Etiqueta UI |
|----------|--------------|----------------|-------------|
| **Resolución** | Ancho de bin FFT o paso de barrido | Hz (`rbw_hz`, `fft_size`) | **FFT** (modo IQ) o **RBW** (modo barrido) |
| **Suavizado** | Media espacial entre bins adyacentes en la traza dibujada | bins (`trace_smooth_bins`) | **SUAV** |

El suavizado **no** modifica la captura IQ ni el bin width de `hackrf_sweep`; solo post-procesa la curva en `core/rf/analysis/pipeline.py`.

---

## 2. Modelo de datos (`SpectrumParams`)

```python
# Resolución
rbw_hz: float
rbw_auto: bool
fft_size: int

# Suavizado de traza (UI «SUAV»)
trace_smooth_auto: bool = True   # True = OFF (sin kernel extra)
trace_smooth_bins: int = 1       # Ancho del kernel cuando manual (≥ 1)
```

Métodos útiles:

- `effective_rbw_hz()` — bin width efectivo (Hz).
- `effective_trace_smooth_bins()` — ancho del kernel (1 = traza cruda).

Campos legacy **`vbw_hz` / `vbw_auto` eliminados**. Proyectos antiguos se migran al cargar (`spectrum_params_io.migrate_legacy_vbw_fields`).

---

## 3. Modos de captura

### 3.1 IQ / SDR (`capture_mode == "iq"`)

- **Resolución:** `RBW ≈ sample_rate_hz / fft_size`.
- Menú **FFT:** presets 256…8192 (`IQ_FFT_PRESETS`) vía `patch_fft_size`.
- **SUAV:** presets ×3, ×5, ×11… (`TRACE_SMOOTH_BIN_PRESETS`).

Perfil auxiliar: `iq_sdr_profile.py` (sample rate, filtro FI, ganancias). El suavizado no interviene en hardware.

### 3.2 Barrido (`capture_mode == "sweep"`)

- **Resolución:** RBW enviada a `hackrf_sweep` (`patch_rbw_hz`, límites `SWEEP_RBW_MIN/MAX_HZ`).
- **SUAV:** mismo modelo en bins; el kernel se aplica sobre los puntos ya interpolados del barrido.

`sync_analysis_chain()` mantiene coherencia RBW ↔ FFT ↔ SWT sin tocar `trace_smooth_*`.

---

## 4. Flujo GUI → motor

```
Toolbar LCD (monitor_bw_sweep_controls.py)
    │ patch_* vía MonitorController.apply_params
    ▼
SpectrumParams (copia inmutable por patch)
    │ prepare_params_for_capture() + refresh_capture_and_span_limits()
    ▼
RfSpectrumRunner (PLAY)
    │ RfSession.capture_once(legacy_params=params)
    ▼
DefaultAcquisitionPolicy → IQ stream | hackrf_sweep
    ▼
AnalysisPipeline.process()  — detector, SUAV, hold
    ▼
MonitorSpectrumWidget (espectro + waterfall)
```

Demod/audio/digital: `SpectrumEngine.start_demod_auxiliary()` comparte el tap IQ del motor (sin segundo `hackrf_transfer`).

Archivos clave:

| Archivo | Rol |
|---------|-----|
| `monitor_bw_profile.py` | Etiquetas UI, presets, `format_*_status` |
| `monitor_bw_sweep_logic.py` | `patch_rbw_*`, `patch_fft_size`, `patch_trace_smooth_*` |
| `core/rf/bridge.py` | `SpectrumParams` ↔ `OperatorIntent`, `prepare_params_for_capture` |
| `core/rf/display.py` | Política AUTO analizador (~801 pts, RBW estable) |
| `core/rf/acquisition/policy.py` | IQ ↔ barrido |
| `core/rf/analysis/pipeline.py` | SUAV y modos de traza (max/min hold) |
| `monitor_bw_menus.py` | Menús FFT/RBW y SUAV: **Automático · Manual · presets** en lista plana con ✓ |
| `monitor_spectrum_status_strip.py` | Franja azul inferior |
| `monitor_flow_log.py` | Log de cambios (`trace_smooth_*` en DISPLAY_PARAM_KEYS) |

Documentación motor RF: [rf_engine/README.md](rf_engine/README.md).

---

## 5. Parches de suavizado

| Función | Efecto |
|---------|--------|
| `patch_trace_smooth_auto()` | SUAV **OFF** (`trace_smooth_auto=True`) |
| `patch_trace_smooth_manual()` | Activa manual; si venía de OFF, elige preset ×5 (o el primero válido) |
| `patch_trace_smooth_bins(n)` | Fija ancho en bins (menú presets) |

Aliases legacy (tests / imports antiguos): `patch_vbw_auto`, `patch_vbw_manual`, `patch_smooth_bins`.

`patch_vbw_hz(hz)` convierte Hz legacy → bins y delega en `patch_trace_smooth_bins` (solo compatibilidad).

---

## 6. Algoritmo de suavizado

Implementación en `core/rf/analysis/pipeline.py` → `apply_trace_smooth()`:

1. Si `trace_smooth_auto` → devolver traza sin cambios.
2. Convertir dB → potencia lineal.
3. Convolución uniforme de ancho `effective_trace_smooth_bins()`.
4. Volver a dB.

Es **espacial** (eje frecuencia), no temporal. Correcto tanto en IQ continuo como en barrido discontinuo.

---

## 7. Persistencia y migración

Claves en `PERSIST_KEYS` (`spectrum_params_io.py`):

- `trace_smooth_auto`
- `trace_smooth_bins`

Al cargar JSON/proyecto con `vbw_auto` / `vbw_hz`:

| Legacy | Resultado |
|--------|-----------|
| `vbw_auto=True` | OFF |
| `vbw_auto=False`, `vbw_hz` ≪ RBW | `bins ≈ round(RBW / vbw_hz)` |
| `vbw_hz` ≥ 0.98 × RBW | OFF |

La migración corre **después** de `sync_analysis_chain()` para que `effective_rbw_hz()` sea correcto.

---

## 8. i18n

Claves principales (es/en):

- `monitor_lcd_fft`, `monitor_lcd_rbw` — títulos resolución
- `monitor_lcd_smooth`, `monitor_lcd_smooth_off` — SUAV
- `monitor_tip_fft`, `monitor_tip_rbw`, `monitor_tip_smooth` — tooltips

Claves `monitor_lcd_vbw_*` conservadas por compatibilidad de traducción; la UI visible usa SUAV/FFT.

---

## 9. Motor AUTO (`core/rf/display.py` + políticas)

Referencia tipo Keysight/R&S (modo analizador, RBW/FFT/SWT en AUTO):

| Regla | Valor / comportamiento |
|-------|------------------------|
| Puntos en pantalla | `ANALYZER_AUTO_POINTS` ≈ 801 (rejilla fija en barrido AUTO) |
| RBW barrido | `Span / 801`, snap a presets si cercano; mín. 100 kHz (`hackrf_sweep`) |
| Estabilidad RBW | Histéresis ~12 % al variar SPAN (evita saltos 19↔21 MHz FM) |
| IQ ↔ barrido | SPAN ≤ 20 MHz → IQ; SPAN > 20 MHz → barrido |
| RBW fino en barrido | Si RBW manual < 100 kHz y SPAN ≤ 20 MHz → cambio automático a IQ |
| RBW manual en barrido amplio | SPAN > 20 MHz: `rbw_auto = false` usa `rbw_hz` del operador (clamp + snap preset) |
| FFT en barrido | Desacoplado de RBW: `fft_auto` controla rejilla; `rbw_auto` controla hardware |
| SUAV AUTO | OFF (1 bin); el usuario puede activar SUAV manual |

El override manual (menús RBW/FFT/SWT/SUAV) no se modifica al cambiar SPAN salvo políticas de captura (IQ/barrido).

---

## 11. Traza fina IQ (botón F en RBW)

Solo visible en **modo IQ** (SPAN ≤ ~20 MHz). Toggle **F ON / F OFF** en la fila RBW de la toolbar (mismo patrón visual que **Pre ON/OFF** en LNA).

| F ON | F OFF |
|------|-------|
| `iq_trace_sharp = true` | valor por defecto |
| Detector **peak** | detector habitual |
| Remuestreo columna **peak** | linear |
| FFT AUTO → 2048 si SR ≥ 10 MHz | FFT AUTO estándar |
| SUAV manual 3 bins | SUAV según perfil |

Parches: `patch_iq_trace_sharp()` en `monitor_bw_sweep_logic.py`. Menú contextual en `monitor_bw_menus.populate_sharp_trace_menu` (acceso secundario).

---

## 12. Toolbar — layout uniforme

Constantes en `monitor_lcd_styles.py`:

- `MONITOR_TOOLBAR_GROUP_HEIGHT = 56` — marcos FC/SPAN, RF, BW, modo.
- `MONITOR_TOOLBAR_CONTROL_HEIGHT = 46` — controles numéricos y botones Analizador/SDR.

Archivos: `monitor_toolbar.py`, `monitor_lcd_styles.py`.

---

## 13. Menú SPAN (…)

`gui/monitor/monitor_span_menu.py` — compartido por toolbar, overlay y franja azul:

- Modos: manual, completo, cero, último (`patch_span_mode`).
- Acción «Editar lapso» → `edit_span_dialog`.
- Avisos modo analizador vía `span_mode_requires_analyzer_mode` / `span_requires_analyzer_mode`.

---

## 10. Tests

| Test | Qué verifica |
|------|----------------|
| `tests/core/test_rf_display.py` | Estabilidad FM, rejilla 801 pts |
| `tests/core/test_monitor_bw_profile.py` | Etiquetas FFT vs SUAV OFF |
| `tests/core/test_monitor_bw_sweep.py` | Parches, persistencia, migración legacy |
| `tests/core/test_trace_vbw.py` | Kernel espacial (`AnalysisPipeline`) |
| `tests/core/test_sweep_manual_rbw_wide.py` | RBW manual en barrido > 20 MHz |
| `tests/core/test_iq_trace_sharp.py` | Traza fina F ON |
| `tests/gui/test_monitor_toolbar_qt.py` | Toolbar, AMPT AUTO, altura marcos |
| `tests/gui/test_monitor_span_menu_qt.py` | Menú SPAN (…) |
| `tests/gui/test_monitor_rbw_sharp_qt.py` | Botón F junto a RBW |
| `tests/gui/test_monitor_vbw_qt.py` | Widget `MonitorVbwControl` |

---

## 10. Overlays FC/F y SPAN (sesión relacionada)

Sliders inline sobre el espectro (`monitor_spectrum_overlays.py`):

- **FC** — frecuencia central; pan con mano; fondo azul.
- **F** — frecuencia analizada; mueve la raya; fondo ámbar.
- **SPAN** — colores según modo (manual/full/…); texto en una línea (`FC  93.200 MHz`, `SPAN  20.000 MHz`).

No alteran RBW/SUAV; comparten `SpectrumParams` vía el mismo controller.
