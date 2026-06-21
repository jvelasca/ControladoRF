# Fase 6 — Portadoras invisibles, picos solo en FI/FF

**Estado:** auditoría activa (jun 2026). **Parar parches** hasta cerrar esta fase con números.

## Síntoma (operador)

- No se ven portadoras FM en **ninguna** combinación (IQ, barrido, AUTO, MANUAL).
- Solo aparecen **picos en FI y FF** (frecuencia inicial / final del lapso visible).
- FC típica de prueba: **97,3 MHz**.
- Esto ya ocurrió en el pasado; los parches recientes no han cerrado el problema.

## Resultados auditoría en hardware (19 jun 2026, esta máquina)

Ejecutado `python scripts/audit_rf_chain.py --fc 97.3e6 --rate 10e6 --lna 24 --vga 36`:

| Etapa | Pico global | FI / FC / FF |
|-------|-------------|--------------|
| 1 dBFS bruto | **97,3 MHz** | −73,9 / **−36,6** / −84,6 dB |
| 6 compute_spectrum_frame | **97,3 MHz** | −101,9 / **−64,6** / −112,6 dBm |
| AUTO | ref −57,4 dBm, rango 60 dB | centro **por encima** del piso visible |

**Conclusión etapa 1:** la portadora está en el centro en FFT bruta — **no es fallo de antena ni de pintado puro**.

Ruta GUI (`RfSession.capture_once`, misma que el monitor):

| SR | Pico global | Comentario |
|----|-------------|------------|
| 10 MHz | 97,3 MHz @ −67,6 dBm | FI/FF más bajos que el centro |
| 20 MHz | variable: 87,3 MHz (FI) o 97,3 MHz | lobos de borde compiten con el centro |

### Trampa en `monitor_flow.log`

La línea `iq_peak` usa `find_peak_excluding_dc`, que **excluye** el bin central (zona LO) y los bordes del paso de banda. Por eso reporta 87,5 / 102,3 MHz aunque el **máximo global** esté en 97,3 MHz. **No usar `iq_peak` como prueba de portadoras invisibles.**

---


Con FC=97,3 MHz y SR=10 MHz (FI=92,3 / FF=102,3 MHz), la telemetría `iq_peak` reporta repetidamente:

| peak_mhz | Relación |
|----------|----------|
| 87,300 / 87,800 | ≈ FI (borde inferior) |
| 102,290 / 106,781 | ≈ FF (borde superior) |

**No** reporta picos en 97,3 MHz (centro / emisora sintonizada).

Conclusión: el problema **no es solo pintado** — en la traza numérica el máximo está en los bordes del paso de banda, no en el centro.

---

## Mapa de la cadena (analizador en PLAY)

```text
Antena
  → HackRF (LNA/VGA/P, filtro BB MAX2837, ADC 8 bit)
  → USB
  → HackRfIqCapture (libhackrf o hackrf_transfer)
       ├── _fft_buffer.read_latest(N)   ← espectro (snapshot)
       └── _demod_buffer                ← audio
  → iq_bytes_to_complex (/128)
  → FFT Hanning → dBFS
  → − ganancia_RX + offset +32 dB   (calibrate_hackrf_antenna_power_db)
  → notch DC + atenuación bordes    (display)
  → AnalysisPipeline (suavizado / hold)
  → apply_display_scale (AUTO ref/rango)
  → MonitorController._auto_ref_smooth
  → resample_power_to_grid → QPainter (espectro)
```

**Barrido (SPAN > ~21 MHz):** `hackrf_sweep` CLI sustituye el bloque IQ; misma calibración dBm y pintado.

Archivos clave:

| Etapa | Archivo |
|-------|---------|
| Captura IQ | `hackrf_iq_capture.py`, `iq_stream.py` |
| FFT + calibración | `iq_fft.py`, `spectrum_fft.py` |
| Barrido | `hackrf_sweep_source.py` |
| AUTO escala | `presentation/scale.py`, `display_scale.py`, `monitor_controller._deliver_frame` |
| Eje frecuencia | `spectrum_plot_mapping.plot_freq_bounds` |
| Política IQ/barrido | `bridge.py`, `acquisition/policy.py` |

---

## Hipótesis ordenadas (de más probable a menos)

### H1 — Lobos en FI/FF + escala AUTO (confirmada parcialmente en logs)

- El paso de banda mostrado = **sample_rate** (±SR/2).
- El filtro BB HackRF auto ≈ **75 % del SR** (`hackrf_baseband.default_baseband_filter_for_sample_rate`).
- Los **últimos ~12,5 %** de cada lado del eje son zona de transición del filtro / basura de aliasing → picos en FI/FF.
- **AUTO** usa `max(power)` → ancla la referencia a esos picos → el centro queda **por debajo del piso visible**.

**Prueba:** AMPT MANUAL ref=−30 dBm, rango 80 dB. Si aparecen portadoras → H1 confirmada (no fallo de RF).

### H2 — Calibración dBm (−ganancia +32) deja el centro demasiado bajo

- Offset +32 dB es empírico (GQRX/SDR++), no verificado en este hardware.
- Si el centro real está a −90 dBm y los bordes a −40 dBm tras calibración, solo se ven bordes.

**Prueba:** script `audit_rf_chain.py` etapas 1→3: comparar dBFS bruto en centro vs bordes **antes** de calibrar.

### H3 — Span mostrado ≠ span útil del filtro

- SPAN en toolbar = SR en IQ; pero energía RF útil ≈ 0,75×SR.
- SDR++ suele acotar el ancho visible al filtro; nosotros pintamos el 100 % → siempre hay “orejas” en FI/FF.

**Prueba:** comparar con SDR++ misma FC, SR 10 MHz, mismas ganancias.

### H4 — Captura / driver (lib vs transfer, dispositivo ocupado)

- Tras barrido, IQ puede arrancar en **mock** o sin muestras válidas (ver log `iq_peak source=mock`).
- `read_latest` sin continuidad de fase → espectro deformado.

**Prueba:** STOP → PLAY; comprobar barra de estado `source=hackrf`; ejecutar audit con HackRF solo.

### H5 — Doble copia de parámetros (fase 1 C1)

- GUI lee `engine.params`; captura usa `runner._params`.
- Desfase no explica picos **siempre** en FI/FF en logs (datos reales del runner).

---

## Protocolo de auditoría (hacer en este orden)

### Paso 0 — Congelar cambios

No más parches de visualización hasta tener un `audit_rf_chain_latest.txt` con HackRF real.

### Paso 1 — Script sin GUI

```powershell
cd "ControladoRF V1\ControladoRF V1"
python scripts/audit_rf_chain.py --fc 97.3e6 --rate 10e6 --lna 24 --vga 36
python scripts/audit_rf_chain.py --mock
```

Comparar: en **mock** el pico interior debe estar cerca de FC; en **HackRF** ver si el pico sigue en FI/FF en etapa `1_raw_fft_dBFS` (RF/FFT) o solo después de calibración (H2).

### Paso 2 — Tabla de decisión

| Etapa 1 (dBFS bruto) | Etapa 3 (dBm) | Causa probable |
|----------------------|---------------|----------------|
| Pico en FI/FF | Pico en FI/FF | Hardware / filtro BB / SR demasiado ancho |
| Pico en centro | Pico en FI/FF | Calibración o AUTO |
| Pico en centro | Pico en centro, GUI vacía | Pintado / params desincronizados |

### Paso 3 — Referencia cruzada SDR++

Mismas FC 97,3 MHz, SR 10 MHz, LNA 24, VGA 36, P OFF. Captura de pantalla + dBm de una emisora conocida.

### Paso 4 — Una variable cada vez en GUI

1. IQ 10 MHz, AMPT MANUAL ref −30, rango 80  
2. Igual con AUTO  
3. Subir a 21 MHz (barrido), esperar 15 s, volver a 10 MHz IQ  

Anotar en cada paso: ¿modo IQ o barrido? ¿source hackrf o mock?

---

## Criterios de cierre (antes de tocar código otra vez)

1. `audit_rf_chain` con HackRF: **pico_interior** dentro de ±3 MHz de una emisora real **o** explicación documentada de por qué el aire está vacío en FC.
2. Con AMPT MANUAL (−30 / 80 dB) las portadoras se ven **o** se demuestra que `power_db` interior está por debajo de −110 dBm (señal/calibración).
3. Decisión explícita: ¿recortar eje al filtro BB? ¿revisar offset +32? ¿fijar AUTO solo con `interior_power_db`?

---

## Relación con calibración wizard

El backend de calibración pasó **17/17** en parámetros; el operador falló en pasos visuales (transición 20→21 MHz). Eso encaja: **la configuración numérica es coherente; la cadena perceptual (escala + bordes + barrido) no.**

Ver `docs/calibration/findings_20260619.md`.

---

## Siguiente documento

Cuando el paso 1 esté hecho, rellenar `logs/audit_rf_chain_latest.txt` y abrir issue interno con la fila de la tabla de decisión que corresponda. Solo entonces aplicar **un** fix acotado (no varios a la vez).
