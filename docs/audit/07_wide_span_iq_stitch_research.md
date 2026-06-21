# Fase 7 — SPAN > 20 MHz: investigación (pausa jun 2026)

**Estado:** pausa activa. Sin más parches hasta elegir arquitectura.

## Síntoma actual (operador)

- **20 MHz:** portadoras FM fluidas, aspecto realista.
- **21 MHz:** siguen viéndose portadoras, pero **menos realistas**, con **saltos en todo el espectro**.

Tras limpiar “trampas” de perfiles RBW/SWT, el problema **no es** reset de controles: es **cómo se construye el trazo por encima del BW instantáneo del HackRF**.

---

## 1. Qué dice el hardware (HackRF / MAX2837)

| Parámetro | Valor típico | Implicación |
|-----------|--------------|-------------|
| Sample rate máximo | **20 Msps** | Ventana analógica/digitada ≈ **±10 MHz** alrededor del LO |
| Arquitectura | Superheterodino + ADC 8 bit | Solo un “chunk” de espectro a la vez |
| Filtro BB | Auto ~75 % del SR (doc/firmware) | Bordes del paso de banda con rolloff y aliasing |
| SPAN >> 20 MHz | Requiere **retunear LO** | No existe FFT continua nativa sobre 20 MHz reales |

Fuentes: [HackRF tools (hackrf_sweep)](https://hackrf.readthedocs.io/en/latest/hackrf_tools.html), [StackExchange — sampling rate vs rango](https://electronics.stackexchange.com/questions/745858/what-is-the-sampling-rate), código `hackrf_sweep.c` en [greatscottgadgets/hackrf](https://github.com/greatscottgadgets/hackrf/blob/master/host/hackrf-tools/src/hackrf_sweep.c).

---

## 2. Tres arquitecturas estándar (analizadores profesionales)

```text
A) SWEPT (analizador clásico)
   LO barre → IF/RBW → detector → un punto de frecuencia a la vez
   SPAN muy ancho OK; pierde eventos cortos entre pasos

B) RTSA / FFT (LO fijo)
   LO parked → IQ → FFT en tiempo (casi) real
   Solo dentro del RTBW (real-time bandwidth)

C) SWEPT REAL-TIME (híbrido, p.ej. Signal Hound)
   Secuencia de FFT rápidas en segmentos → “pegado” de trozos
   SPAN > RTBW con POI limitada por tiempo entre segmentos
```

Referencias: nota Signal Hound “swept real-time”, slides IEEE spectrum analysis (swept vs RTSA), ITU spectrum analyzer training.

**Conclusión:** pedir **21 MHz fluidos como a 20 MHz** en un HackRF **no encaja** en el modelo B puro. Hay que elegir A, C o un subconjunto honesto de B (mostrar solo BW útil).

---

## 3. Qué hacen otras apps

### SDR++ / SDR “de consumo”

- Espectro y waterfall dentro del **sample width** del SDR (p.ej. 2 MHz RTL, ~20 MHz HackRF).
- Multi-VFO = varias sintonías **dentro** del mismo ancho, no stitch de varios LO.
- **Range scanner** = barrido experimental por rango, no vista continua ancha tipo analizador.
- Manual: [SDR++ User Guide (PDF)](https://wtfda.org/wp-content/uploads/SDRs/SDRpp_manual.pdf).

### hackrf_sweep (referencia oficial GSG)

Modo **interleaved** (por defecto):

1. Captura bloque **20 MHz** @ 20 Msps.
2. **Descarta** bordes ~2,5 MHz + centro ~5 MHz (DC spike + rolloff).
3. Retune **+5 MHz** y repite; luego salto mayor (~15 MHz) y reinicia ciclo.
4. Ensambla solo trozos “limpios” (~10 MHz útiles por paso de sintonía).

Cita maintainer (issue #349): *“throws out the top and bottom 2.5MHz, as well as the middle 5MHz… retune by 5MHz… gives us much better data at the cost of some speed.”*

Issue #1460 explica por qué **no** usan pasos lineales de 5 MHz sin interleave: DC, rolloff del filtro, velocidad.

**RBW mínimo efectivo en barrido:** orden **100 kHz–2,4 kHz** según bins FFT del bloque, no ~SR/1024.

### GNU Radio / multi-HackRF

- Stitch ancho con **varios SDR** + solape + sincronización fase/frecuencia (paper GRCON / rtl-sdr.com multi-HackRF).
- Requiere alineación DSP seria; no es “max-hold de dos FFT sueltas”.

---

## 4. Qué hace ControladoRF hoy (≤20 vs 21 MHz)

### ≤ 20 MHz — modo IQ continuo (correcto para HackRF)

```text
hackrf_transfer / libhackrf → ring buffer continuo
  → read_latest(N) cada frame
  → FFT Hanning → calibración → pintado
```

Un solo LO, trazo **coherente en el tiempo** → aspecto fluido.

### 21 MHz — entra `iq_stitch` (origen probable del síntoma)

Condición en `device.py`: `span > sample_rate + 50 kHz`.

Para FC=97,3 MHz, SPAN=21 MHz:

| Magnitud | Valor |
|----------|-------|
| Ventana pedida | 86,80 – 107,80 MHz |
| Capturas | **2** |
| Centros LO | **96,8 MHz** y **113,8 MHz** |
| Cobertura unión | 86,80 – 123,80 MHz |

Problemas vs estándar hackrf_sweep:

1. **Retune grande** (paso ~17 MHz por solape 15 %) para cubrir solo **~1 MHz** extra respecto a 20 MHz.
2. **Dos instantáneas distintas** por frame (no stream continuo).
3. Fusión **`max()` por bin** en solape → picos que **saltan** frame a frame.
4. Cada tile aplica notch DC + guardia de bordes → **costuras** visibles.
5. `ensure_stream` reinicia sintonía entre tiles → latencia + transientes.

```text
Frame N:   [tile @ 96.8 MHz] → retune → [tile @ 113.8 MHz] → max-merge → pintar
Frame N+1: repite (nuevos max aleatorios en FM) → SALTOS GLOBALES
```

A 20 MHz **no** ocurre esto: mismo buffer, misma fase temporal.

---

## 5. Diagnóstico del salto 20 → 21 MHz

| | 20 MHz | 21 MHz |
|---|--------|--------|
| Modo captura | IQ stream continuo | IQ stitch (2 LO/frame) |
| Coherencia temporal | Sí | No |
| Algoritmo de unión | N/A | max-hold naive |
| Receta GSG (interleave + crop) | N/A | **No implementada** |
| SWT en UI | N/A (correcto) | N/A (correcto) |

**Hipótesis principal (alta confianza):** el síntoma “irreal + saltos” es **esperable** con la implementación actual de stitch, no un bug menor de RBW.

---

## 6. IDEAS FRESCAS (para retomar)

No implementar aún. Ordenadas por alineación con documentación HackRF.

### Idea A — “Honesto SDR++” (mínimo riesgo)

- En analizador IQ: **SPAN visible ≤ 20 MHz** (o ≤ 0,75×SR = banda útil del filtro).
- SPAN manual > 20 MHz: aviso + clamp o segunda escala “solo visual”.
- **Pros:** fluido, predecible, sin saltos. **Contras:** no es lapso analizador > 20 MHz real.

### Idea B — Barrido nativo GSG (recomendado para SPAN > 20 MHz)

- SPAN > 20 MHz → **`hackrf_sweep` interleaved** (como SDR# / herramientas oficiales).
- RBW ≥ 100 kHz, SWT visible, traza más lenta pero **físicamente consistente**.
- **Pros:** alineado con chip y docs. **Contras:** pierde sensación “tiempo real” FM.

### Idea C — Stitch “de verdad” (hackrf_sweep en software)

- Reimplementar receta interleaved: pasos **5 MHz**, descartar centro + bordes, crop en solape.
- Un **ciclo completo** de stitch antes de actualizar pantalla; opcional promediado en solape (no max).
- Tiempo de asentamiento tras retune (>350 ms por tile hoy puede ser insuficiente en el 2.º LO).
- **Pros:** IQ compuesto usable hasta ~70 MHz. **Contras:** mucho trabajo; POI limitada.

### Idea D — Híbrido por umbral

- **20–25 MHz:** quedarse en **un solo LO** (FC usuario) + mostrar 20 MHz útiles + sombrear 0,5–1 MHz “no cubierto” **o** auto-clamp a 20 MHz.
- **>25 MHz:** barrido (B) o stitch C.
- **Pros:** elimina el peor caso (21 MHz = 2 retunes por frame). **Contras:** regla compuesta.

### Idea E — Dos modos UI explícitos

- **Tiempo real** (≤20 MHz) vs **Exploración** (barrido / stitch lento).
- El operador elige; no mezclar semánticas de RBW/SWT entre modos.

---

## 7. Protocolo de verificación (cuando retomemos)

1. Log por frame: `capture_kind`, `n_tiles`, `centers_mhz`, `capture_ms`, `merge_bins`.
2. Comparar misma FC/ganancias: SDR++ @ 20 MHz vs ControladoRF @ 20 y @ 21 MHz.
3. Comparar @ 21 MHz: ControladoRF stitch vs `hackrf_sweep -f ... -w 100000` exportado.
4. Medir varianza de bin FM (97,3 MHz) en 100 frames @ 20 vs @ 21 MHz.

---

## 8. Decisión pendiente (producto)

**Decisión (jun 2026): lapso ancho correcto** — implementado:

- **SPAN ≤ 20 MHz:** IQ continuo (tiempo real, RBW fino ~SR/FFT).
- **SPAN > 20 MHz:** **`hackrf_sweep`** (modo interleaved GSG, RBW ≥ 100 kHz, SWT activo).

Se eliminó el path de **IQ stitch** en runtime (`device.capture_iq_spectrum` ya no retunea ni fusiona tiles).

Ver `iq_stitch_plan.span_exceeds_instant_bw()` y `policy._wants_sweep()`.

---

## Referencias

- [HackRF — hackrf_sweep](https://hackrf.readthedocs.io/en/latest/hackrf_tools.html)
- [Issue #349 — interleaved mode](https://github.com/greatscottgadgets/hackrf/issues/349)
- [Issue #1460 — por qué descartar centro/bordes](https://github.com/greatscottgadgets/hackrf/issues/1460)
- [Issue #864 — parámetros de stepping](https://github.com/greatscottgadgets/hackrf/issues/864)
- [SDR++ manual PDF](https://wtfda.org/wp-content/uploads/SDRs/SDRpp_manual.pdf)
- [Signal Hound — swept real-time](https://signalhound.com/wp-content/uploads/2023/11/Aero-Avionics-Workflows-AppNote-231109.pdf)
- [GNU Radio GRCON — wideband from narrow channels](https://pubs.gnuradio.org/index.php/grcon/article/download/59/42/)
