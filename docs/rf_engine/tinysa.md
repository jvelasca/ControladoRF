# TinySA

Driver sweep-only para [TinySA / TinySA Ultra](https://github.com/erikkaashoek/TinySA) por consola serie USB.

## Hardware soportado

| Parámetro | Valor por defecto en ControladoRF |
|-----------|-----------------------------------|
| Rango | 100 kHz – 960 MHz (Ultra; clásico puede variar) |
| Enlace | USB CDC, **115200 baud** |
| Comando | `scanraw start_hz stop_hz points` |
| IQ / demod | No soportado |

## Protocolo

Implementación en `src/core/rf/devices/tinysa/protocol.py`:

```
scanraw 350000000 430000000 201
```

Respuesta: líneas `frecuencia_hz,nivel_db` hasta el prompt `ch>`.

Puntos limitados a 101–290 según span (firmware TinySA).

Referencia: wiki TinySA / comandos `help scanraw` en la consola del equipo.

## Selección en la GUI

1. Conecte el TinySA por USB.
2. Instale `pyserial`: `pip install pyserial`
3. En Monitor → FUENTE, elija `TinySA · COMx`.
4. Modo **Analizador** obligatorio; export CSV Workbench/SoundBase disponible.

## Limitaciones

- `scanraw` es barrido crudo (sin calibración `scan` completa del menú).
- Sin IQ → demod, audio digital y supervisión IQ desactivados.
- LNA/VGA HackRF de la barra no aplican.

## Depuración

- Abra un terminal serie externo solo para pruebas (115200); cierre antes de usar ControladoRF.
- Si no hay datos: compruebe que el TinySA no esté en otro modo bloqueante (menu, cal).

## Código

| Archivo | Rol |
|---------|-----|
| `devices/tinysa/device.py` | `TinySaDevice` |
| `devices/tinysa/protocol.py` | scanraw + parseo |
| `monitor/serial_discovery.py` | Detección COM |

Ver también [analyzer_sources.md](analyzer_sources.md).
