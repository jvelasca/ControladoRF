# Changelog — CONTROLADORF

## 1.1.0

### Monitor — toolbar y resolución
- Toolbar con marcos de altura uniforme (FC/SPAN, RF, BW, modo Analizador/SDR).
- Botón **F ON/OFF** junto a RBW (estilo Pre ON/OFF): traza fina IQ con detector pico, FFT AUTO ampliada y suavizado ligero (`trace_smooth_bins = 3`).
- **RBW manual** respetado en barrido > 20 MHz (`DefaultAcquisitionPolicy` + snap a preset HackRF).
- Menú **… SPAN** restaurado (`monitor_span_menu.py`): modos manual/completo/cero/último y edición de lapso.
- AMPT AUTO muestra nivel de referencia real; relleno bajo traza (DISPLAY); escala AUTO estabilizada.

### Monitor — RF y fuentes
- Canalización RF global (modo canal, estándares, exclusiones en espectro).
- Fuentes analizador: RF Explorer y TinySA (documentación en `docs/rf_engine/`).
- Perfil IQ/SDR, auto-tune de ganancias y métricas RF mejoradas.

### Radio / demodulación
- Panel radio rediseñado, RDS WFM, audio estéreo en hilo principal, squelch y calidad RF.

### App
- Formulario de contacto/desarrollador, descubrimiento serial, migraciones BD canalización.

### Tests
- Cobertura Qt toolbar/RBW/SPAN, RBW barrido amplio, traza fina IQ, pintado espectro.

## 1.0.2

- Instalador profesional Windows (Inno Setup Setup.exe).
- Actualizaciones automáticas vía GitHub Releases (Setup + ZIP).
- Empaquetado onedir; corrección bucle consola negra.

## 1.0.1

- Distribución W11 en carpeta + ZIP (no one-file).
- Herramientas HackRF incluidas en `rf-tools\bin`.
- Subprocess ocultos en Windows.

## 1.0.0

- Primera distribución empaquetada Windows 11.
