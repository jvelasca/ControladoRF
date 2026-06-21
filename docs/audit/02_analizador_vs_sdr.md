# Fase 2 — Analizador vs SDR: misma UI, distinto significado

El usuario espera que **LNA 32 · VGA 40 · P ON · SPAN 2 MHz** se vea igual en ambos modos. Hoy **no es garantizable** por diseño.

## Tabla de divergencias (mismo “valor” en pantalla)

| Parámetro | Analizador (spectrum) | SDR |
|-----------|----------------------|-----|
| `operating_mode` | `spectrum` | `sdr` |
| `capture_mode` | `iq` si span ≤ 20 MHz, si no `sweep` | Siempre `iq` |
| `audio_enabled` | Off | On (si demod FM/AM) |
| `supervision_enabled` | On | Off |
| SPAN máximo UI | Hasta lapso completo (~6 GHz) | 20 MHz (BW instantáneo) |
| SPAN mínimo | 100 kHz (sweep) / 2 MHz (IQ) | 2 MHz |
| RBW efectivo | sweep bin o SR/FFT | SR / FFT |
| Escala dBm IQ | `+ HACKRF_IQ_ANTENNA_OFFSET_DB` (+32) | Igual |
| Escala sweep | Sin offset +32 | N/A en SDR |
| `rf_attenuation_db` | Auto `40 - LNA` en sweep | No recalculado en IQ |
| Ventana FI/FF | Activa en barrido | Limpiada (`clear_freq_window`) |
| Snap SR | Rejilla 0,5 MHz | Igual |
| Política IQ/barrido | `DefaultAcquisitionPolicy` | Siempre IQ |

**Archivos:** `monitor_mode_profile.py`, `acquisition/policy.py`, `spectrum_fft.py`, `hackrf_sweep_source.py`, `monitor_controller.py` 1707–1708.

---

## Hallazgos

### M1 — Offset +32 dB solo en IQ

Cambiar de analizador IQ a SDR con mismas ganancias puede mantener la **forma** de la traza pero el **REF AUTO** y la telemetría dBm no son comparables con barrido sin convertir.

### M2 — Histéresis IQ ↔ barrido documentada pero no implementada

`SPAN_SWEEP_HYSTERESIS_HZ` en `monitor_mode_profile.py` **no se usa** en `sync_params_capture_mode_from_v2`. Cerca de 20 MHz el modo puede conmutar al mínimo cambio de span.

**Test a revisar:** `test_sweep_hysteresis_avoids_iq_sweep_flip_flop` (puede no coincidir con política actual).

### M3 — `display_span_hz()` vs `sample_rate_hz`

En IQ, la UI a menudo muestra `manual_span_hz`, pero la traza usa `sample_rate_hz` tras snap. Si no se ejecutó `apply_span_mode`, pueden divergir.

---

## Escenarios de “incoherencia” reproducibles

1. **Analizador 80 MHz sweep** vs **SDR imposible** — mismo slider de span, distinto techo.
2. **Analizador 500 kHz RBW** (sweep fino o IQ forzado) vs **SDR mínimo 2 MHz**.
3. **Mismas ganancias** — traza IQ compensada en dBm; audio demod **sin** compensar → P ON sube audio pero la traza resta ganancia en FFT.

---

## Checklist fase 2

- [ ] Documentar en UI que “SPAN” en SDR = sample rate (no lapso de barrido).
- [ ] Decidir: ¿unificar offset +32 entre IQ y sweep para comparación visual?
- [ ] Decidir: ¿histéresis real o eliminar constante y tests obsoletos?
- [ ] Matriz de prueba manual: FC 98 MHz, span 2.5M, LNA 32, VGA 40, P off/on — capturas analizador IQ y SDR.

**Siguiente fase:** [03_hardware_iq_ganancias.md](03_hardware_iq_ganancias.md)
