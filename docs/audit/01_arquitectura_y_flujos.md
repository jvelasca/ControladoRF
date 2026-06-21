# Fase 1 — Arquitectura y flujos de datos

## Estado actual (resumen)

```text
GUI (toolbar, overlays, dock, status strip)
    │ apply_params()
    ▼
MonitorController._apply_params_impl
    │ refresh_capture_and_span_limits (a veces omitido: gain_only_sdr)
    │ prepare_params_for_capture
    ▼
MonitorRfViewModel ──► RfSpectrumRunner.sync_from_params
    │                      └── RfSession (captura PLAY)
    └── RfSession (segunda instancia, preview/latente)

SpectrumEngine (PLAY)
    └── start_demod_auxiliary(RfDemodIqSource)  → tap del mismo HackRfIqCapture
    └── NO ejecuta bucle de espectro en PLAY normal
```

**Fuente de verdad de params en UI:** `get_params()` → `SpectrumEngine.params` (`monitor_controller.py`).

**Quién captura espectro en PLAY:** solo `RfSpectrumRunner` → `RfSession.capture_once()`.

---

## Hallazgos CRÍTICOS

### C1 — Dos copias de parámetros y dos `RfSession`

| Componente | Almacén | Sesión RF |
|------------|---------|-----------|
| `SpectrumEngine` | `_params` (lo que lee la GUI) | No captura en PLAY |
| `RfSpectrumRunner` | `_params` propia | `RfSession` activa en PLAY |
| `MonitorRfViewModel` | — | **Otra** `RfSession` |

**Riesgo:** La GUI muestra valores de `engine.params` mientras el runner puede estar un frame o un parche desfasado. Cualquier side-effect en `SpectrumEngine.set_params` que mute solo la copia del engine no llega al runner.

**Archivos:** `monitor_controller.py` (orden: view_model ~1782, engine.set_params ~1805), `runner.py`, `monitor_rf_view_model.py`.

### C2 — `SpectrumEngine.request_reconfigure` es camino muerto en PLAY con demod

En PLAY con audio:

1. `apply_params` siempre llama `_engine.set_params(...)`.
2. Con demod auxiliar, `_running=True` pero **no** hay `_run_loop` de espectro.
3. `_maybe_reconfigure()` solo corre dentro del bucle legacy de captura.

**Síntoma:** Logs `reconfigure_scheduled` / `triggers_reconfigure=True` sin garantía de aplicación HW. La reconfiguración real depende del runner en el **siguiente** `capture_once` → `restart_if_needed`.

**Archivos:** `spectrum_engine.py`, `monitor_controller.py`, `demod_iq_source.py`.

---

## Hallazgos ALTOS

### H1 — Logging engañoso

`triggers_reconfigure=True` si `_rf_runner.is_running`, pero el motor que programa reconfigure es `SpectrumEngine`, no el runner.

### H2 — `apply_operating_mode()` en cada `apply_params`

Resetea `audio_enabled` / `supervision_enabled` en cada movimiento de slider; luego `refresh_capture` parcialmente lo corrige. Aumenta acoplamiento y efectos colaterales.

**Archivo:** `monitor_controller.py` ~1717, `spectrum_params.py` `apply_operating_mode`.

### H3 — Coalescing de `apply_params`

Si llegan parches rápidos, `_pending_apply_params` descarta estados intermedios. Span + P en la misma ráfaga puede dejar solo el último estado.

**Archivo:** `monitor_controller.py` 1647–1667.

---

## Diagrama IQ compartido (espectro + demod)

```text
HackRfIqCapture._on_iq_chunk
    ├── _fft_buffer (snapshot, no consume)  ← RfSpectrumRunner / FFT
    └── _demod_buffer (ring, consume)     ← DemodStreamWorker
```

Tras `stop()` / restart: buffers vacíos; demod **no** siempre recibe `gap_detected` → posible audio basura o silencio hasta re-lock.

---

## Checklist fase 1 (revisión manual)

- [ ] Confirmar en código que `engine.start()` no se llama para espectro en PLAY (`monitor_controller.start`).
- [ ] Trazar una llamada `apply_params` desde toggle P hasta `restart_if_needed` (breakpoint o log).
- [ ] Verificar si `get_params()` y `runner.get_params()` divergen tras mover solo REF auto.
- [ ] Inventariar todos los sitios que llaman `refresh_capture_and_span_limits` (¿siempre necesario?).

**Siguiente fase:** [02_analizador_vs_sdr.md](02_analizador_vs_sdr.md)
