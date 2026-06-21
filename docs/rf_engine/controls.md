# Controles del Monitor (RBW / FFT / SWT / SUAV)

## Analizador + IQ (SPAN ≤ 20 MHz)

Visibles: **FFT**, **SUAV**. RBW y SWT ocultos (no aplican a IQ continuo).

La barra de estado puede mostrar `FFT N · X kHz` donde X kHz es el bin derivado.

## Analizador + barrido (SPAN > 20 MHz)

| LCD | AUTO | Manual |
|-----|------|--------|
| RBW | Preset estable ~SPAN/801 | 100 kHz – 5 MHz (hardware) |
| FFT | 801 pts display | 256 – 8192 pts display |
| SWT | Estimado del ciclo | Periodo mínimo entre frames |
| SUAV | OFF (1 bin) | ×3, ×5, ×11, … |

## SDR

Igual que IQ: **FFT** + **SUAV**. Captura siempre por flujo IQ.

## RBW por debajo de 100 kHz

No existe en `hackrf_sweep`. Si el lapso cabe en 20 MHz, al elegir RBW < 100 kHz el sistema cambia a **modo IQ** con esa resolución.

## Reinicio tras cambios

Tras cambiar RBW/FFT/SWT en barrido o tras IQ↔barrido: **STOP → PLAY** recomendado.

## Waterfall MIN/MAX

Sliders independientes; al mover uno no arrastra el otro salvo corrección min ≥ max.
