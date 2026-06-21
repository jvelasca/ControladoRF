# Motor RF — ControladoRF

ControladoRF usa un único motor de radio en `src/core/rf/`. Toda captura de espectro (analizador y SDR) pasa por **RfSession**; la GUI habla en términos de `SpectrumParams` y el puente `core/rf/bridge.py` traduce a intención de operador y planes de hardware.

## Documentación

| Documento | Contenido |
|-----------|-----------|
| [architecture.md](architecture.md) | Capas, módulos, flujo de un frame |
| [hackrf.md](hackrf.md) | Límites reales HackRF One (IQ vs barrido) |
| [policies.md](policies.md) | IQ/barrido, RBW, FFT, SWT, SUAV |
| [controls.md](controls.md) | Controles LCD/menús y modo manual |
| [gui_integration.md](gui_integration.md) | MonitorController, runner, demod |
| [development.md](development.md) | Guía para mantener y extender el motor |

Relacionado (cadena RBW/SUAV en UI): [../monitor_bw_trace.md](../monitor_bw_trace.md).

## Arranque rápido (desarrollador)

```text
GUI (PyQt6)
  MonitorController
    RfSpectrumRunner  ──► RfSession.capture_once()
    MonitorRfViewModel
    SpectrumEngine    ──► solo demod/audio/digital (IQ compartido)
         │
         ▼
  core/rf/
    bridge.py          SpectrumParams ↔ OperatorIntent
    acquisition/policy DefaultAcquisitionPolicy
    analysis/policy    DefaultAnalysisPolicy
    analysis/pipeline  SUAV, hold, detector
    devices/hackrf/    IQ stream + hackrf_sweep
```

## Tests

```bash
python -m pytest tests/core/rf/ tests/core/test_rf_display.py tests/core/test_monitor_bw_sweep.py tests/core/test_trace_vbw.py -q
```

Hardware HackRF opcional; la mayoría de tests usan mock o políticas puras.

## Fuera de alcance del motor RF

- Inventario, BD, supervisión de alarmas → `core/monitor/supervision/`
- Demodulación DSP → `core/monitor/demod_*` (alimentada por tap IQ del motor)
- Persistencia de proyectos → `spectrum_params_io.py`
