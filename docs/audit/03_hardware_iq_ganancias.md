# Fase 3 — Hardware IQ, preamp P y pérdida de datos

## Síntoma: pulsar P → deja de recibir datos

### Causa A — Backend `hackrf_transfer` (no libhackrf)

En `hackrf_iq_capture.restart_if_needed`, si **no** es backend `lib` con stream activo:

- Cualquier cambio de LNA/VGA/**P** → `stop()` + `sleep(0.25)` + `start()` proceso hijo.
- Buffers FFT y demod **vacíos**.
- Hueco típico **250–500 ms+**; runner puede lanzar `Reiniciando captura IQ…` si no hay muestras a tiempo.

**Verificar:** ¿Windows usa libhackrf o transfer? `hackrf_iq_capture._backend`, scripts de instalación.

### Causa B — Camino `gain_only_sdr` incompleto

Parche reciente: si solo cambian ganancias en SDR, se **omite** `refresh_capture` y `prepare_params_for_capture` completo (`preserve_iq_span=True`).

- HW debería actualizarse en el **siguiente frame** vía `restart_if_needed`.
- Si `is_sdr_rf_gain_only_patch` falla (p. ej. REF auto cambió en el mismo tick), se ejecuta pipeline completo → posible re-snap de span **y** restart.

**Archivo:** `monitor_flow_log.py` `is_sdr_rf_gain_only_patch`, `monitor_controller.py`.

### Causa C — `HackRfDevice.configure` para FC/SR, no para P

Preamp **no** dispara teardown en `configure()` (correcto para lib). Pero **cambio de FC** sí para stream antes de poder usar `apply_center_freq` en vivo → reinicio duro.

**Archivo:** `devices/hackrf/device.py` 97–107.

### Causa D — Espectro vs demod desincronizados tras restart

- FFT resta `nominal_gain_db` tras P ON → traza estable en dBm.
- Demod usa IQ crudo → salto de nivel; squelch puede cerrar.
- Usuario percibe “sin audio” aunque lleguen frames de espectro.

**Archivos:** `spectrum_fft.py`, `demod_dsp.py`, `demod_branch.py`.

### Causa E — `SpectrumEngine` reporta reconfigure sin ejecutarla

Ver fase 1 C2 — no resetea demod al cambiar P si el log dice `Sin cambios`.

---

## Tabla backends

| Evento | libhackrf | hackrf_transfer |
|--------|-----------|-----------------|
| Solo P/LNA/VGA | `apply_gains()` en vivo | Reinicio proceso |
| FC / SR | Puede reiniciar RX si stream ya parado por `configure` | Reinicio |
| Barrido | `capture_sweep` para IQ stream | — |

---

## Checklist fase 3

- [ ] Log en PLAY: toggle P → ¿`stream_restart` o `apply_gains`?
- [ ] Medir FPS en franja de estado antes/después de P.
- [ ] Si transfer: priorizar libhackrf o aplicar gains sin `stop()` completo.
- [ ] Tras restart: ¿`DemodStreamWorker` debería `reset()` explícito?
- [ ] Unificar compensación de ganancia espectro ↔ demod (o documentar diferencia).

**Siguiente fase:** [04_span_y_sample_rate.md](04_span_y_sample_rate.md)
