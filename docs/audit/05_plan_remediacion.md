# Fase 5 — Plan de remediación (después de la auditoría)

No implementar hasta cerrar checklist de fases 1–4 en hardware real.

## Principios de arreglo

1. **Un solo dueño de params** en PLAY (`RfSpectrumRunner` + objeto compartido con GUI).
2. **Un solo dueño de reconfigure HW** en PLAY (runner/session; `SpectrumEngine` solo demod).
3. **Mismas reglas de span** en SDR: `manual_span_hz` → SR siempre en un solo sitio (`apply_span_mode`).
4. **Ganancias en vivo** cuando libhackrf; si transfer, minimizar `stop()` o migrar a lib.

---

## Orden recomendado

| # | Tema | Severidad | Entregable |
|---|------|-----------|------------|
| 1 | Unificar params + reconfigure bajo runner | CRÍTICO | `get_params()` == runner; quitar reconfigure fantasma en engine |
| 2 | P / LNA / VGA sin perder stream | CRÍTICO | P toggle con libhackrf; test integración + log claro |
| 3 | SPAN SDR end-to-end | ALTO | Fix `patch_manual_span` + overlay merge; test E2E span→SR |
| 4 | Analizador ↔ SDR coherencia visual | ALTO | Documentar o unificar offset; matriz de prueba |
| 5 | Histéresis IQ/sweep o eliminar | MEDIO | Implementar o borrar constante + tests |
| 6 | Demod reset en IQ restart | MEDIO | Tras `stop()`, flag gap + reset cadena |
| 7 | `apply_operating_mode` solo en transición de modo | MEDIO | Menos side-effects en sliders |
| 8 | Colapsar `RfSession` duplicada en view model | BAJO | Una sesión por PLAY |

---

## Criterios de cierre (por síntoma usuario)

### P preamp

- [ ] Con PLAY 30 s, toggle P ×10: FPS nunca cae a 0 > 2 s.
- [ ] Audio y traza recuperan en < 500 ms (lib) o documentado (transfer).

### Coherencia analizador / SDR

- [ ] Misma FC, span IQ 2.5M, LNA/VGA/P: portadora dentro de ±3 dB (tras normalizar offset documentado).

### SPAN SDR

- [ ] Cada paso del slider cambia `sample_rate_hz` en telemetría o explica snap (mismo valor).

---

## Deuda técnica aceptada (por ahora)

- Barrido por CLI cada frame (rendimiento).
- `SpectrumEngine` aún almacena params del proyecto.
- Demod y espectro con compensación de ganancia distinta.

---

## Registro de auditoría

| Fecha | Alcance | Notas |
|-------|---------|-------|
| 2026-06-18 | Fases 0–5 documentadas | Pausa post-migración motor RF; síntomas P/span/coherencia |
| 2026-06-18 | Remediación fases 1–8 (código) | Params en controller; reconfigure solo runner; histéresis sweep; SPAN overlay SR; demod gap en stop |

### Estado implementación (2026-06-18)

| # | Tema | Estado |
|---|------|--------|
| 1 | Params + reconfigure bajo runner | Hecho — `_project_params`, `request_hw_reconfigure` en engine |
| 2 | P/LNA/VGA sin perder stream | Parcial — freq sin teardown; gap demod en `stop()`; libhackrf live |
| 3 | SPAN SDR end-to-end | Hecho — `patch_manual_span` + merge overlay/status SR |
| 4 | Coherencia ATT SDR | Hecho — `rf_attenuation_db` sincronizado en SDR |
| 5 | Histéresis IQ/sweep | Hecho — `SWEEP_STICKY_MIN_SPAN_HZ` en bridge |
| 6 | Demod reset IQ restart | Hecho — `gap_detected` tras `stop()` |
| 7 | `apply_operating_mode` solo transición | Hecho |
| 8 | Sesión RF única | Hecho — view model usa `runner.session` |

Pendiente validación hardware (checklist cierre abajo).
