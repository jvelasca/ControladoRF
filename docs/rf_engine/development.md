# Guía de desarrollo — motor RF



Documento para quien modifique captura, análisis o integración GUI sin romper el contrato de `SpectrumParams`.



## Principios



1. **Un solo bucle de espectro** — `RfSpectrumRunner` + `RfSession.capture_once()`. No añadir segundos `hackrf_transfer` para la traza.

2. **SpectrumParams es el contrato** — persistencia `.crf`, LCD, menús y tests hablan este modelo. El motor interno usa `OperatorIntent`.

3. **Políticas puras** — decisión IQ/barrido y valores AUTO viven en `acquisition/policy.py`, `analysis/policy.py` y `display.py`, no en la GUI.

4. **Análisis en el motor** — SUAV, hold y detector se aplican en `AnalysisPipeline` antes de llegar al widget.



## Flujo de un cambio de parámetro



```text

Usuario (menú / LCD)

  → patch_* en monitor_bw_sweep_logic.py (inmutable: devuelve copia)

  → MonitorController.apply_params()

  → prepare_params_for_capture(params)     # bridge: AUTO + capture_mode

  → refresh_capture_and_span_limits()      # si cambió SPAN o fuente

  → MonitorRfViewModel.apply_params()

  → RfSpectrumRunner.sync_from_params()    # si PLAY activo

```



En PLAY, cada frame:



```text

RfSpectrumRunner._loop()

  → RfSession.capture_once(legacy_params=params)

       → DefaultAcquisitionPolicy.plan()

       → HackRfDevice.capture_iq_spectrum() | capture_sweep()

       → AnalysisPipeline.process()

       → apply_display_scale()

  → legacy_frame_from_display() → MonitorSpectrumWidget

```



## Dónde tocar según el cambio



| Objetivo | Archivos |

|----------|----------|

| Nuevo preset RBW/FFT/SUAV | `monitor_bw_profile.py`, `monitor_bw_menus.py`, `monitor_bw_sweep_logic.py` |

| Regla IQ ↔ barrido | `acquisition/policy.py`, `bridge.sync_params_capture_mode_from_v2()` |

| RBW AUTO / histéresis FM | `display.py` (`pick_stable_sweep_rbw`, `optimize_analyzer_auto_for_span`) |

| RBW manual < 100 kHz | `monitor_bw_sweep_logic._maybe_switch_iq_for_fine_rbw()` |

| FFT desacoplado en barrido | `SpectrumParams.fft_auto`, `display_trace_bins()`, `patch_fft_size()` |

| Periodo entre barridos (SWT) | `runner.effective_sweep_time_ms()`, `analysis/policy.py` |

| Suavizado espacial | `analysis/pipeline.py` |

| Waterfall MIN/MAX | `MonitorRfViewModel` hold state + `pipeline.py` trace modes |

| Demod sin duplicar USB | `demod_iq_source.py`, `SpectrumEngine.start_demod_auxiliary()` |



## Campos `SpectrumParams` (RF)



| Campo | Rol |

|-------|-----|

| `capture_mode` | `iq` \| `sweep` — etiqueta derivada; refrescar con `refresh_capture_and_span_limits` |

| `rbw_auto`, `rbw_hz` | Resolución hardware en barrido (`hackrf_sweep -w`) |

| `fft_auto`, `fft_size` | Rejilla de pantalla en barrido; tamaño FFT en IQ |

| `sweep_auto`, `sweep_time_ms` | Pacing mínimo entre frames de barrido |

| `trace_smooth_auto`, `trace_smooth_bins` | SUAV (convolución en frecuencia) |

| `trace_mode` | clear_write, max_hold, min_hold, average |



`fft_auto` y `rbw_auto` son **independientes** en barrido: RBW controla bins hardware; FFT controla interpolación/display (~801 en AUTO).



## Tests recomendados



```bash

python -m pytest tests/core/rf/ tests/core/test_rf_display.py tests/core/test_monitor_bw_sweep.py tests/core/test_trace_vbw.py -q

```



Añadir tests de política en `tests/core/rf/` (sin hardware) y de parches UI en `tests/core/test_monitor_bw_sweep.py`.



## Extensiones previstas



Ver [gui_integration.md](gui_integration.md) — telemetría en barra de estado, barrido segmentado, consolidar demod bajo `RfSession`.



## Anti-patrones



- Reintroducir un segundo motor de captura o flag de activación alternativo.

- Acoplar `fft_size` a `rbw_hz` en barrido (rompe menús FFT manuales).

- Aplicar SUAV solo en GUI (debe estar en `AnalysisPipeline` para coherencia waterfall/traza).

- Llamar `hackrf_sweep` desde la GUI directamente.


