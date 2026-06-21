# Calibración Monitor — cadena RF profesional

## Objetivo

Cerrar de forma **trazable** la coherencia entre:

1. **Entrada RF** — FC, SPAN, ganancias, ATT
2. **Adquisición** — IQ continuo vs `hackrf_sweep` (frontera ~20 MHz HackRF)
3. **Análisis** — RBW, FFT, SWT, SUAV (AUTO/MANUAL por modo)
4. **Visualización** — rejilla, escala, bins de traza

Modelo de referencia: self-test de analizadores **Rohde & Schwarz** / **Keysight** — matriz de escenarios, informe PASS/FAIL, log persistente.

## Frontera IQ ↔ barrido (HackRF)

| SPAN | Modo esperado | Notas |
|------|---------------|-------|
| ≤ 20 MHz | `iq` | `sample_rate_hz ≈ span`; RBW = SR/FFT |
| > 20 MHz | `sweep` | RBW hardware ≥ 100 kHz; FFT = rejilla pantalla |
| 15–20 MHz (bajando desde barrido) | `sweep` (histéresis) | Evita flip-flop en FM ancha |

**Corrección clave:** se eliminó la histéresis que **mantenía IQ** cuando la política pedía barrido (20–21 MHz). Eso rompía el analizador al ampliar SPAN.

## Uso

### CLI (recomendado en CI y depuración)

```powershell
.\env\Scripts\python.exe scripts\run_monitor_calibration.py
.\env\Scripts\python.exe scripts\run_monitor_calibration.py --quick
.\env\Scripts\python.exe scripts\run_monitor_calibration.py --live --fc 93.2e6 --live-span 10e6
```

Salida:

- `logs/calibration/calibration_YYYYMMDD_HHMMSS.json`
- `logs/calibration/calibration_latest.md`
- `logs/calibration/calibration_run.log`

### GUI (modo DEBUG) — asistente guiado

1. Panel lateral → **DEBUG** (contraseña desarrollador `1493`)
2. Pestaña **Diagnóstico** → **Abrir asistente de calibración…** (ventana amplia redimensionable, no modal)
3. Por cada paso: **Aplicar configuración** → lea **análisis backend** → si falla, **comentario obligatorio** → **OK** / **Falla**
4. Informes: `logs/calibration/wizard_latest.json` + `wizard_latest.md` (checklist completo, etiquetas, incoherencias)

Pasos cubren: dispositivo, PLAY, IQ 10/20 MHz, transición 19→21 MHz, barrido 50 MHz, RBW/FFT manual, histéresis 18 MHz, escala AUTO/manual, LNA/VGA.

## Matriz de escenarios

- **SPAN:** 1, 2, 5, 10, 15, 18, 19, 19.5, 20, 20.5, 21, 25, 40, 80, 100 MHz
- **Transiciones:** 19→21, 21→19, 20→50, 50→10, 18→25, 25→18 MHz
- **Flags:** IQ/barrido × AUTO/MANUAL en RBW y FFT

Cada escenario valida:

- `capture_mode` vs política de adquisición
- ventana FI/FF vs SPAN
- FFT potencia de 2
- IQ: SR≈SPAN, RBW=SR/FFT, `rbw_auto==fft_auto`
- Barrido: RBW≥100 kHz, SWT>0
- plan hardware enriquecido coherente con parámetros GUI

## Módulos

```
src/core/monitor/calibration/
  chain_validator.py    # invariantes cadena
  capture_transition.py # perfiles al cambiar modo
  scenario_matrix.py    # escenarios
  harness.py            # ejecutor + informe
scripts/run_monitor_calibration.py
```

## Pruebas hardware (contigo)

Tras PASS offline, conviene validar en equipo real:

1. Señal CW o FM conocida (ej. 93.2 MHz)
2. SPAN 10 MHz (IQ) → comprobar pico y RBW derivado
3. SPAN 40 MHz (barrido) → traza estable, sin reset visual
4. Barrido 19→21 MHz con PLAY activo — sin “descomposición” de escala/traza
5. RBW manual en barrido → SWT congelado (no salta a 0)

Registra `logs/monitor_flow.log` durante la prueba y ejecuta:

```powershell
.\env\Scripts\python.exe scripts\monitor_diagnose_session.py
```

## Tests unitarios

```powershell
.\env\Scripts\python.exe -m pytest tests\core\test_monitor_calibration.py -v
```
