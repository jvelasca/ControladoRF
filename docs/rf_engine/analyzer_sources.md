# Fuentes analizador sweep-only

ControladoRF distingue dos familias de equipo en el Monitor:

| Familia | Modo | IQ / demod | Captura |
|---------|------|------------|---------|
| SDR (HackRF, …) | Analizador + SDR | Sí (SDR) | IQ fluido o barrido según SPAN |
| Analizador (RF Explorer, TinySA) | Solo Analizador | No | Barrido serie |

## Identificadores de fuente

Las fuentes serie usan el formato `familia@PUERTO`:

- `rf_explorer@COM5`
- `tinysa@COM3`

La detección USB rellena automáticamente el puerto COM cuando `pyserial` está instalado.

## Restricciones automáticas

Al seleccionar RF Explorer o TinySA, la aplicación:

1. Fuerza **modo Analizador** (desactiva el botón SDR).
2. Fija `capture_mode = sweep`.
3. Desactiva demodulación, audio e IQ.
4. Muestra avisos en barra de estado, panel RADIO y banner del espectro.

Claves i18n: `monitor_source_*` en `src/i18n/es.json` / `en.json`.

## Motor RF

- Capacidades: `src/core/rf/capabilities.py` (`supports_iq_stream=False`).
- Política: `analyzer_only_sweep` en `src/core/rf/acquisition/policy.py`.
- Drivers: `src/core/rf/devices/rf_explorer/`, `src/core/rf/devices/tinysa/`.
- Perfil UI: `src/core/rf/source_profile.py`.

## Exportación

La exportación CSV Workbench/SoundBase (`TraceExportFormat` en `monitor_export.py`) funciona igual que con HackRF en modo barrido: frecuencia + nivel por bin.

## Documentación por equipo

- [rf_explorer.md](rf_explorer.md)
- [tinysa.md](tinysa.md)

## Tests

```bash
python -m pytest tests/core/rf/test_analyzer_sources.py -q
```
