# DAB+ en ControladoRF

## Análisis nativo (modo DIG)

ControladoRF incluye análisis DAB+ Mode I en Python:

- Sincronismo OFDM por **intervalo de guarda** (CP)
- Demodulación **QPSK diferencial** por portadora
- Detección de **ensemble** (bloque DAB+ presente)
- Constelación, **EVM** y **MER**
- Bloque Band III más cercano (p. ej. **202.928 MHz**)

Requisitos: captura **IQ @ 2.048 MHz**, modo **DIG**, VFO en la frecuencia del ensemble.

## Audio DAB+ — welle.io (recomendado)

La decodificación de audio DAB+ (AAC+, lista de programas) no se reimplementa aquí.
Se usa **[welle.io](https://github.com/AlbrechtL/welle.io)** (incluye código de **[dablin](https://github.com/Opendigitalradio/dablin)**).

### Instalación (Windows)

1. Compilar o instalar **welle-cli** con soporte **SoapySDR + HackRF**
2. Asegurarse de que `welle-cli` está en el PATH

Documentación: https://www.welle.io

### Uso con HackRF

El HackRF no puede usarse a la vez en ControladoRF y welle-cli.

1. **STOP** en ControladoRF
2. Ejemplo (ajuste canal según bloque):

```bash
welle-cli -F soapysdr,driver=hackrf -c 11C -w 7970
```

3. Abrir http://localhost:7970/ para lista de servicios y audio

ControladoRF detecta si `welle-cli` está instalado y muestra una pista en el panel digital cuando hay ensemble.

### Alternativas

| Proyecto | Uso |
|----------|-----|
| [welle.io](https://github.com/AlbrechtL/welle.io) | Receptor DAB/DAB+ completo (GUI + welle-cli) |
| [dablin](https://github.com/Opendigitalradio/dablin) | Decodificador DAB/DAB+ (CLI, usado por welle) |
| [qt-dab](https://github.com/JvanKatwijk/qt-dab) | Receptor DAB (origen de welle.io) |
