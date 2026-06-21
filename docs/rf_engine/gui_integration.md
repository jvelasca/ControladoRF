# Integración GUI

## MonitorController

- **PLAY**: `RfSpectrumRunner.start()` → espectro/waterfall.
- **Demod/digital**: si aplica, `SpectrumEngine.start_demod_auxiliary(RfDemodIqSource)` sobre el mismo IQ USB.
- **apply_params**: siempre `prepare_params_for_capture()` + `MonitorRfViewModel.apply_params()`.
- **Frames**: el análisis (SUAV, hold) ya viene aplicado en `RfSession`; la GUI solo ajusta escala REF automática.

## MonitorRfViewModel

Fachada sin PyQt: sincroniza `SpectrumParams` → `RfSession.set_intent()` y `RfSpectrumRunner.sync_from_params()`.

## SpectrumEngine (rol actual)

No captura espectro. Conserva:

- Almacén de `SpectrumParams` compartido con la GUI.
- `DemodStreamWorker` / `DigitalAnalysisWorker`.
- `read_iq_snapshot` para supervisión dwell.

## Señales de transporte

- `engine_running_changed` — conectado al runner (y demod aux cuando corre).
- `_capture_is_running()` — consulta `_rf_runner.is_running`.

## Supervisión

`engine_running` en reglas de supervisión debe usar captura activa (`_rf_runner`), no solo demod aux.

## Telemetría en vivo

`RfSpectrumRunner.telemetry()` devuelve modo (`iq_stream` / `sweep`), RBW efectivo, bins, duración de captura (ms) y FPS. En cada frame, `MonitorController` llama a `MonitorSpectrumStatusStrip.set_runtime_telemetry()`. Visibilidad: menú `…` de la franja → grupo **Motor RF** (`status_show_capture`, `status_show_fps`).

## Próximas mejoras (producto)

- Mover demod por completo bajo `RfSession` (eliminar `SpectrumEngine`).
- Barrido segmentado en proceso (sin relanzar CLI cada frame) si libhackrf lo expone estable en Windows.
