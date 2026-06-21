# Políticas de adquisición y análisis

## Modo IQ vs barrido

| Condición | Modo | Motivo |
|-----------|------|--------|
| SDR | Siempre IQ | Demodulación y waterfall fluidos |
| Analizador, SPAN ≤ 20 MHz | IQ | RBW fino (`SR / FFT`), ~50 fps |
| Analizador, SPAN > 20 MHz | Barrido | `hackrf_sweep` cubre el lapso |
| RBW manual < 100 kHz y SPAN ≤ 20 MHz | IQ automático | Barrido no admite RBW < 100 kHz |

Implementación: `DefaultAcquisitionPolicy` + `sync_params_capture_mode_from_v2()` en `bridge.py`.

## Controles en barrido (desacoplados)

| Control | Campo | Efecto |
|---------|-------|--------|
| **RBW** | `rbw_hz`, `rbw_auto` | Ancho de bin `hackrf_sweep -w` (mín. 100 kHz) |
| **FFT** | `fft_size`, `fft_auto` | Puntos de rejilla en pantalla (256–8192 manual) |
| **SWT** | `sweep_time_ms`, `sweep_auto` | Periodo mínimo entre barridos (no acelera el hardware) |
| **SUAV** | `trace_smooth_*` | Convolución espacial en `AnalysisPipeline` |

En IQ/SDR:

| Control | Efecto |
|---------|--------|
| **FFT** | Tamaño FFT → `bin_hz = SR / FFT` |
| **SUAV** | Igual que barrido |

## AUTO (~801 puntos)

- Rejilla objetivo: `ANALYZER_AUTO_POINTS = 801` (`core/rf/display.py`).
- RBW barrido AUTO: `SPAN / 801`, snap a preset 100 kHz–5 MHz con histéresis al cambiar SPAN.
- FFT barrido AUTO: 801 puntos de display (`fft_auto=True`).
- SWT AUTO: estimación `bins × 1,2 ms + 80 ms`, acotada 50 ms–30 s.

## Menús: manual en un clic

Al elegir un preset numérico (FFT, RBW, SUAV ×N, SWT ms):

1. Se activa modo manual del control.
2. Se aplica el valor elegido.

En AUTO, el preset que coincide con el valor efectivo aparece marcado en el menú.

## Archivos de referencia

- Parches UI: `core/monitor/monitor_bw_sweep_logic.py`
- Perfil LCD: `core/monitor/monitor_bw_profile.py`
- Menús: `gui/monitor/monitor_bw_menus.py`
- Políticas motor: `core/rf/acquisition/policy.py`, `core/rf/analysis/policy.py`
