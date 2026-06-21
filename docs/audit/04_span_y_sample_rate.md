# Fase 4 — SPAN en SDR “no cambia”

## Flujo esperado

```text
UI span slider / overlay
  → patch_manual_span()
  → refresh_capture_and_span_limits() ×2
  → apply_span_mode()  → snap SR, manual_span_hz := rate
  → apply_params() (NO gain_only)
  → prepare_params_for_capture()
  → runner.sync_from_params()
  → restart_if_needed(sample_rate_hz)
```

**Archivos:** `monitor_freq_span_logic.py` `patch_manual_span`, `spectrum_params.py` `apply_span_mode`, `monitor_controller.py`.

---

## Por qué puede fallar (hipótesis verificables)

### F1 — `max_span_hz` obsoleto en `patch_manual_span`

Primera línea usa `updated.max_span_hz` **antes** de `refresh_capture`. Tras cambiar modo/fuente, el clamp puede ser incorrecto (demasiado bajo o alto).

**Archivo:** `monitor_freq_span_logic.py` 527–528.

### F2 — Snap 0,5 MHz y piso 2 MHz

- `snap_iq_sample_rate_hz` redondea a 500 kHz.
- Mínimo 2 MHz (`SPAN_MIN_IQ_HZ`).
- Usuario mueve poco → **no hay cambio** visible o vuelve al mismo snap.

### F3 — `gain_only_sdr` por error

Si el parche de span arrastra un cambio de display (REF auto, waterfall), `is_sdr_rf_gain_only_patch` es false pero si **solo** falla la detección inversa (span patch marcado como gain-only imposible), el problema es otro.

Si span + P en un solo `apply_params` coalesced, puede ganar el último parche.

### F4 — Merge parcial desde overlays

`_apply_params_from_overlay_sliders` copia `span_hz` / `manual_span_hz` pero no siempre `sample_rate_hz`. Debería sanearse en `refresh_capture`, salvo que se omita.

**Archivo:** `monitor_controller.py` ~1554–1571.

### F5 — UI muestra span pedido, telemetría muestra SR real

Franja “Captura” muestra `sample_rate_hz` del runner. Si no cambió por snap, parece “roto”.

### F6 — `sync_iq_display` no llamado en algunos caminos

En `gain_only_sdr` se omite `sync_iq_display` — correcto para P. Para span debe ejecutarse el camino completo; si `apply_params` falla silenciosamente (`except` en 1653), el span no aplica.

---

## Prueba manual mínima

1. SDR, PLAY, span manual 2 MHz → anotar SR telemetría.
2. Subir a 5 MHz (un paso del slider) → SR debe pasar a 5_000_000.
3. Si UI cambia y SR no → breakpoint en `patch_manual_span` y en `restart_if_needed`.
4. Revisar `logs/monitor_flow.log` por `sample_rate_hz` en `hardware_changes`.

---

## Checklist fase 4

- [ ] Reproducir con log: ¿llega `patch_manual_span` a `apply_params`?
- [ ] ¿`hardware_changes` incluye `sample_rate_hz`?
- [ ] ¿`restart_if_needed` ve `rate_changed=True`?
- [ ] Corregir orden `max_span_hz` refresh en `patch_manual_span`.
- [ ] Overlay merge: incluir `sample_rate_hz` o forzar `refresh` siempre tras span.

**Siguiente fase:** [05_plan_remediacion.md](05_plan_remediacion.md)
