# Informe calibración guiada

- Sesión: `20260619_165402`
- Inicio: 2026-06-19T16:54:02.089139+00:00
- Fin: 2026-06-19T17:14:18.058008+00:00

## Resumen

| Métrica | Valor |
|---------|-------|
| OK operador | 10 |
| Falla operador | 7 |
| Omitidos | 0 |
| Backend FAIL | 0 |
| Registros incoherentes | 7 |

## Checklist

### ✓ 1. 1. Comprobar dispositivo

- **Operador:** pass | **Backend:** PASS
- **Diagnóstico backend:**
  - Backend OK — confirme dispositivo y PLAY visualmente.

### ✗ 2. 2. Iniciar captura

- **Operador:** fail | **Backend:** PASS
- **Comentario operador:** en modo SDR funciona bien  pero en modo analizador al pasar de un SPAN de 20 a 21 mhz cambia completamente el espectro aunque todo sigua en auto y la  traza no se parece en nada (es mala). Por otra parte en ambos modos al pulsar (...) en AMPT su modo auto Y LOS parametrso modificables como "nivel de referencia"  no ofrece nives de modificacion ahí y rango/posicion de ref (que si ofrece valores) no es claro y coherente. Hay que reacer todo esto ahí de forma mas clara.
- **Etiquetas:** escala, traza, span_modo, ganancia
- **Incoherencias:**
  - Operador FAIL pero backend PASS — problema visual/stream no capturado por invariantes.
- **Diagnóstico backend:**
  - Backend OK — confirme dispositivo y PLAY visualmente.

### ✗ 3. 3. SPAN 10 MHz — modo IQ

- **Operador:** fail | **Backend:** PASS
- **Comentario operador:** en modo SDR funciona bien  pero en modo analizador al pasar de un SPAN de 20 a 21 mhz cambia completamente el espectro aunque todo sigua en auto y la  traza no se parece en nada (es mala). Por otra parte en ambos modos al pulsar (...) en AMPT su modo auto Y LOS parametrso modificables como "nivel de referencia"  no ofrece nives de modificacion ahí y rango/posicion de ref (que si ofrece valores) no es claro y coherente. Hay que reacer todo esto ahí de forma mas clara. NO veo lo que dices de done muestra los resultados.
- **Etiquetas:** escala, traza, span_modo, ganancia
- **Incoherencias:**
  - Operador FAIL pero backend PASS — problema visual/stream no capturado por invariantes.
- **Diagnóstico backend:**
  - Backend OK — parámetros y cadena coherentes.

### ✓ 4. 4. Calidad de traza IQ

- **Operador:** pass | **Backend:** PASS
- **Diagnóstico backend:**
  - Backend OK — validación visual pendiente del operador.

### ✓ 5. 5. FFT manual 4096

- **Operador:** pass | **Backend:** PASS
- **Comentario operador:** mas fina y ondulate pero OK
- **Diagnóstico backend:**
  - Backend OK — parámetros y cadena coherentes.

### ✓ 6. 6. RBW manual 50 kHz (IQ)

- **Operador:** pass | **Backend:** PASS
- **Comentario operador:** mas fina y ondulate pero OK
- **Diagnóstico backend:**
  - Backend OK — parámetros y cadena coherentes.

### ✗ 7. 7. SPAN 20 MHz — límite IQ

- **Operador:** fail | **Backend:** PASS
- **Comentario operador:** no muestra nada en SWT pone - y no deja cambiar nada
- **Etiquetas:** rbw_fft
- **Incoherencias:**
  - Operador FAIL pero backend PASS — problema visual/stream no capturado por invariantes.
- **Diagnóstico backend:**
  - Backend OK — parámetros y cadena coherentes.

### ✗ 8. 8. Transición 19 → 21 MHz

- **Operador:** fail | **Backend:** PASS
- **Comentario operador:** falla como he dicho antes y deja de verse las portadoras
- **Incoherencias:**
  - Operador FAIL pero backend PASS — problema visual/stream no capturado por invariantes.
  - Comentario sin etiquetas conocidas — revisar texto manualmente.
- **Diagnóstico backend:**
  - Backend OK — parámetros y cadena coherentes.

### ✗ 9. 9. Barrido 50 MHz AUTO

- **Operador:** fail | **Backend:** PASS
- **Comentario operador:** falla como he dicho antes y deja de verse las portadoras
- **Incoherencias:**
  - Operador FAIL pero backend PASS — problema visual/stream no capturado por invariantes.
  - Comentario sin etiquetas conocidas — revisar texto manualmente.
- **Diagnóstico backend:**
  - Backend OK — parámetros y cadena coherentes.

### ✗ 10. 10. RBW manual en barrido

- **Operador:** fail | **Backend:** PASS
- **Comentario operador:** falla como he dicho antes y deja de verse las portadoras
- **Incoherencias:**
  - Operador FAIL pero backend PASS — problema visual/stream no capturado por invariantes.
  - Comentario sin etiquetas conocidas — revisar texto manualmente.
- **Diagnóstico backend:**
  - Backend OK — parámetros y cadena coherentes.

### ✗ 11. 11. FFT manual en barrido

- **Operador:** fail | **Backend:** PASS
- **Comentario operador:** falla como he dicho antes y deja de verse las portadoras
- **Incoherencias:**
  - Operador FAIL pero backend PASS — problema visual/stream no capturado por invariantes.
  - Comentario sin etiquetas conocidas — revisar texto manualmente.
- **Diagnóstico backend:**
  - Backend OK — parámetros y cadena coherentes.

### ✓ 12. 12. Histéresis — bajar a 18 MHz

- **Operador:** pass | **Backend:** PASS
- **Diagnóstico backend:**
  - Backend OK — parámetros y cadena coherentes.

### ✓ 13. 13. Volver a IQ — 10 MHz

- **Operador:** pass | **Backend:** PASS
- **Diagnóstico backend:**
  - Backend OK — parámetros y cadena coherentes.

### ✓ 14. 14. Escala AUTO

- **Operador:** pass | **Backend:** PASS
- **Diagnóstico backend:**
  - Backend OK — validación visual pendiente del operador.

### ✓ 15. 15. Escala manual

- **Operador:** pass | **Backend:** PASS
- **Diagnóstico backend:**
  - Backend OK — validación visual pendiente del operador.

### ✓ 16. 16. Cambio LNA

- **Operador:** pass | **Backend:** PASS
- **Diagnóstico backend:**
  - Backend OK — parámetros y cadena coherentes.

### ✓ 17. 17. Cambio VGA

- **Operador:** pass | **Backend:** PASS
- **Diagnóstico backend:**
  - Backend OK — parámetros y cadena coherentes.

## Acciones sugeridas

- **prep_play**: revisar comentario y diagnóstico backend.
- **iq_span_10m**: revisar comentario y diagnóstico backend.
- **iq_span_20m**: revisar comentario y diagnóstico backend.
- **transition_19_21**: revisar comentario y diagnóstico backend.
- **sweep_span_50m**: revisar comentario y diagnóstico backend.
- **sweep_rbw_manual**: revisar comentario y diagnóstico backend.
- **sweep_fft_manual**: revisar comentario y diagnóstico backend.
