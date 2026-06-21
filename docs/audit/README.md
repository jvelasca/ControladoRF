# Auditoría ControladoRF — índice

Pausa de desarrollo activo (jun 2026). Objetivo: localizar problemas **generales** antes de parches puntuales.

| Fase | Documento | Alcance |
|------|-----------|---------|
| **0** | Este README | Cómo usar la auditoría |
| **1** | [01_arquitectura_y_flujos.md](01_arquitectura_y_flujos.md) | Quién captura, quién guarda params, dual-path |
| **2** | [02_analizador_vs_sdr.md](02_analizador_vs_sdr.md) | Mismos valores, distinto comportamiento |
| **3** | [03_hardware_iq_ganancias.md](03_hardware_iq_ganancias.md) | P preamp, paradas de datos, lib vs transfer |
| **4** | [04_span_y_sample_rate.md](04_span_y_sample_rate.md) | SPAN en SDR que no aplica, snaps, límites |
| **5** | [05_plan_remediacion.md](05_plan_remediacion.md) | Orden de arreglos y criterios de cierre |
| **6** | [06_portadoras_fi_ff.md](06_portadoras_fi_ff.md) | **Portadoras invisibles, picos FI/FF** (auditoría activa) |

Documentación motor RF (estado deseado): [../rf_engine/README.md](../rf_engine/README.md).

## Síntomas reportados (entrada a la auditoría)

1. **P (preamp)** — al activar, a veces deja de recibir datos.
2. **Coherencia** — mismos LNA/VGA/P/SPAN en analizador y SDR no se ven igual.
3. **SPAN en SDR** — cambiar span no se refleja en captura.

## Cómo auditar en runtime

1. Activar log de flujo: `logs/monitor_flow.log` (claves `apply_params`, `stream_restart`, `reconfigure`).
2. PLAY en SDR, span 2–5 MHz, anotar `sample_rate_hz` en franja de estado (Captura · FPS).
3. Toggle P → buscar `stream_restart`, huecos > 500 ms sin frames, mensajes `Reiniciando captura IQ`.
4. Cambiar SPAN ±1 paso → verificar que `sample_rate_hz` y bins de traza cambian.
5. Repetir en analizador IQ (span ≤ 20 MHz) con mismas ganancias y comparar dBm de portadora.

## Auditoría portadoras / picos FI-FF (fase 6)

```powershell
python scripts/audit_rf_chain.py --fc 97.3e6 --rate 10e6 --lna 24 --vga 36
```

Salida: `logs/audit_rf_chain_latest.txt` — ver [06_portadoras_fi_ff.md](06_portadoras_fi_ff.md).

## Tests de regresión existentes

```bash
python -m pytest tests/core/test_sdr_gain_patch.py tests/core/test_demod_squelch.py tests/core/test_monitor_mode_transition.py tests/core/test_monitor_freq_span_logic.py tests/core/rf/ -q
```

Algunos tests de histéresis IQ/sweep pueden no reflejar el comportamiento real (ver fase 2).
