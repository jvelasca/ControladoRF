# RF Explorer

Driver sweep-only para analizadores [RF Explorer](https://www.rf-explorer.com/) conectados por USB (UART CP210x).

## Hardware soportado

| Parámetro | Valor por defecto en ControladoRF |
|-----------|-----------------------------------|
| Rango | 15 MHz – 2,7 GHz (modelos WSUB3G; ajuste según modelo) |
| Enlace | USB → CP210x, **500000 baud** |
| Captura | Barrido UART propietario |
| IQ / demod | No soportado |

Modelos con otro rango (6G, IoT, …) pueden funcionar parcialmente; compruebe el lapso en el propio equipo.

## Protocolo

Implementación en `src/core/rf/devices/rf_explorer/protocol.py`:

1. Reset: bytes `#\\x04\\x00\\x00`
2. Configurar span: `#C2-F:startMHz,stopMHz,topdBm,bottomdBm`
3. Solicitar traza: `#C2-:`
4. Parseo de líneas `$S` (frecuencia inicial MHz, paso MHz, niveles dBm)

Referencia oficial: [RF Explorer API](https://github.com/RFExplorer/RFExplorer-for-.NET/wiki/RF-Explorer-API).

## Selección en la GUI

1. Conecte el RF Explorer por USB e instale el driver CP210x.
2. Instale `pyserial`: `pip install pyserial`
3. En Monitor → FUENTE, elija la entrada `RF Explorer · COMx`.
4. Pulse PLAY: solo modo **Analizador**; SDR, demod y audio permanecen bloqueados.

## Limitaciones

- Sin streaming IQ → no demodulación FM/AM/DIG ni grabación baseband IQ.
- Ganancia LNA/VGA de la barra LCD no aplica (controles desactivados).
- Latencia de barrido depende del span (varios segundos en lapsos amplios).

## Depuración

- Compruebe el puerto en Administrador de dispositivos (Windows) o `ls /dev/tty*`.
- Cierre otras apps que usen el puerto (RF Explorer PC Client).
- Mensajes de error típicos: puerto vacío, timeout sin líneas `$S`.

## Código

| Archivo | Rol |
|---------|-----|
| `devices/rf_explorer/device.py` | `RfExplorerDevice` (RfDevice) |
| `devices/rf_explorer/protocol.py` | UART y parseo |
| `monitor/serial_discovery.py` | Detección COM |
| `rf/source_profile.py` | Restricciones UI |
