# Arquitectura del motor RF

## Capas

```text
┌─────────────────────────────────────────────────────────────┐
│  GUI — MonitorController, LCD RBW/FFT/SWT/SUAV, waterfall   │
│         SpectrumParams (modelo único de proyecto)             │
└───────────────────────────┬─────────────────────────────────┘
                            │ bridge.py
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  OperatorIntent + políticas                                   │
│    DefaultAcquisitionPolicy  → IQ o hackrf_sweep              │
│    DefaultAnalysisPolicy     → RBW/FFT/SWT/SUAV efectivos     │
└───────────────────────────┬─────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  RfSession.capture_once()                                     │
│    configure(HackRfDevice)                                    │
│    capture_iq_spectrum() | capture_sweep()                    │
│    AnalysisPipeline.process()                                 │
│    apply_display_scale()                                      │
└───────────────────────────┬─────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  HackRF — HackRfIqStream | hackrf_sweep CLI                   │
└─────────────────────────────────────────────────────────────┘
```

## Módulos principales (`src/core/rf/`)

| Módulo | Responsabilidad |
|--------|-----------------|
| `types.py` | `OperatorIntent`, `AcquisitionPlan`, `SweepPlan`, `AnalysisConfig` |
| `bridge.py` | `prepare_params_for_capture`, `operator_intent_from_params`, enriquecimiento de planes |
| `display.py` | Rejilla 801 pts, RBW AUTO barrido, presets |
| `session.py` | Orquestación: políticas + dispositivo + pipeline |
| `runner.py` | `RfSpectrumRunner` — hilo PLAY/STOP |
| `acquisition/policy.py` | SPAN ≤ 20 MHz → IQ; SPAN mayor → barrido |
| `analysis/policy.py` | Resolución y SWT AUTO |
| `analysis/pipeline.py` | SUAV, max/min hold, average |
| `devices/hackrf/` | IQ continuo y barrido |
| `demod_iq_source.py` | Tap IQ para audio sin segundo `hackrf_transfer` |

## Hilos en PLAY

1. **RfSpectrumRunner** — bucle `capture_once()` → emite frames a la GUI.
2. **SpectrumEngine (auxiliar)** — solo si demod o análisis digital activos; lee el mismo `HackRfIqCapture` vía `RfDemodIqSource`.

No hay segundo motor de espectro ni flag de activación.

## Parámetros de proyecto

`SpectrumParams` sigue siendo el contrato de persistencia (`.crf`). Campos RF relevantes:

- `capture_mode` — `iq` | `sweep` (derivado de política al aplicar)
- `rbw_auto`, `rbw_hz` — resolución hardware en barrido
- `fft_auto`, `fft_size` — rejilla de pantalla en barrido; FFT en IQ
- `trace_smooth_auto`, `trace_smooth_bins` — SUAV
- `sweep_auto`, `sweep_time_ms` — periodo mínimo entre barridos

## Telemetría

`RfSession.telemetry()` + `RfSpectrumRunner.fps()` — modo, RBW, bins, ms de captura y FPS en la franja de estado del espectro.
