# HackRF One — hardware y límites

Referencia: [HackRF hardware components](https://hackrf.readthedocs.io/en/latest/hardware_components.html), [libhackrf hackrf.h](https://github.com/greatscottgadgets/hackrf/blob/master/host/libhackrf/src/hackrf.h).

El motor RF (`core/rf/devices/hackrf/`) encapsula libhackrf y `hackrf_sweep`; la GUI no llama APIs USB directamente.

## Dos modos de adquisición

| Modo | API / módulo | BW | Resolución mínima |
|------|----------------|-----|-------------------|
| **IQ continuo** | `HackRfIqStream` → `hackrf_transfer` | 2–20 MHz | `sample_rate / fft_size` |
| **Barrido** | `hackrf_sweep` CLI | hasta ~6 GHz span | **100 kHz** por bin (`-w`) |

Política: SPAN ≤ 20 MHz → IQ; SPAN mayor → barrido. RBW manual < 100 kHz con SPAN que cabe en IQ → cambio automático a IQ.

## Bloques RX (resumen)

Antena → RF amp (on/off) → mezclador RFFC5072 → MAX2837 (LNA 0–40 dB paso 8, VGA 0–62 dB paso 2, filtro BB) → ADC 8 bit → USB.

Mapeo `SpectrumParams`:

| Parámetro | Control |
|-----------|---------|
| `center_freq_hz` | `hackrf_set_freq` |
| `lna_gain_db`, `vga_gain_db`, `rf_amp_enable` | ganancias RX |
| `baseband_filter_bw_hz` | filtro anti-alias |
| `sample_rate_hz` | ancho IQ |
| `rbw_hz` (barrido) | `hackrf_sweep -w` |

## Ganancia y dBm en pantalla

Compensación unificada vía `iq_rx_gain_compensation_db()` en IQ y barrido.

## Lo que HackRF no ofrece

- RBW/VBW analógicos continuos (solo BB discreto + FFT o bins de barrido).
- RBW de barrido por debajo de 100 kHz (usar IQ).
- Full duplex RX.

## Código en el repositorio

| Ruta | Rol |
|------|-----|
| `src/core/rf/devices/hackrf/device.py` | `RfDevice` |
| `src/core/rf/devices/hackrf/iq_stream.py` | Sesión IQ |
| `src/core/monitor/hackrf_sweep_source.py` | Parser + `run_hackrf_sweep` |
| `src/core/monitor/hackrf_iq_capture.py` | Proceso `hackrf_transfer` |
| `src/core/monitor/hackrf_rx_gains.py` | Snap LNA/VGA |
