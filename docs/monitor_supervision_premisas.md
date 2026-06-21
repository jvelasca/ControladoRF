# Supervisión RF — Premisas de producto y ventaja competitiva

Documento de **premisas estratégicas** para el módulo Monitor / Supervisión de ControladoRF.
Complementa [monitor_supervision.md](monitor_supervision.md) (arquitectura técnica) y
[monitor_supervision_ayuda.md](monitor_supervision_ayuda.md) (operación).

**Última revisión:** 2026-06-12

---

## 1. Misión

ControladoRF aspira a ser **superior a las aplicaciones profesionales de referencia**
(Shure Wireless Workbench, Sennheiser WSM, Wisycom Wireless Manager, sistemas broadcast NMS)
utilizando **hardware SDR de coste medio-bajo** (p. ej. HackRF) y software abierto, portable
y orientado al técnico RF en directo.

> **Premisa central:** el valor no está solo en medir, sino en **configurar, entender y actuar**
> sobre alarmas con la misma claridad que un monitor broadcast de sala de control — sin licencias
> propietarias ni hardware dedicado de gama alta.

---

## 2. Principios de diseño (no negociables)

| # | Principio | Implicación |
|---|-----------|-------------|
| P1 | **Transparencia de alarmas** | Cada alarma debe indicar *qué check*, *qué umbral* y *qué modo* (vs ruido / vs referencia). |
| P2 | **Presets + personalización** | Plantillas integradas (solo lectura) + copia editable; nunca bloquear al operador. |
| P3 | **Referencia en el aire** | Supervisión nominal: «esto es válido ahora» → vigilar caídas Δ dB / Δ MER. |
| P4 | **Matriz profesional** | Tablas canal × preset × umbrales × reglas; columnas redimensionables y persistentes. |
| P5 | **Hardware accesible** | Optimizar para SDR económico; no exigir analizador de bolsillo ni receptor dedicado. |
| P6 | **Proyecto portable** | Umbrales, presets, referencias y layout UI viajan en el `.crf`. |
| P7 | **Operación en vivo** | Bulk apply, fijar referencia masiva, ack/latch, log SQLite exportable. |

---

## 3. Modelo de tres capas (estándar industria)

```
Catálogo de checks  →  Preset de alarmas  →  Asignación por canal + referencia
(qué medir)            (qué dispara qué)     (punto cero en el aire)
```

### Checks soportados (v2)

| Check | Descripción |
|-------|-------------|
| `snr_above_noise` | SNR sobre piso de ruido local (FFT) |
| `carrier_present` | Presencia de portadora vs margen |
| `mer_db` | MER digital (dwell IQ) |
| `dig_sync` | Pérdida de sync digital |

### Modos de umbral

| Modo | Uso típico |
|------|------------|
| `noise_relative` | Coordinación / buscar interferencias (estilo Workbench) |
| `nominal_delta` | Ensayo general / show en directo (caída vs referencia fijada) |

---

## 4. Ventajas sobre la competencia (roadmap)

Funcionalidades que nos diferencian o nos diferenciarán:

| Área | Competencia típica | ControladoRF (objetivo) |
|------|-------------------|-------------------------|
| **Coste hardware** | Receptores/analizadores dedicados | HackRF / SDR accesible |
| **Matriz de umbrales** | Diálogos dispersos, poco legibles | Matriz canal + preset + reglas en lenguaje natural |
| **Referencia nominal** | Limitada o manual externa | «Fijar referencia» integrado, bulk, persistido |
| **Presets** | Fijos o ocultos en XML | Integrados + copia + import/export JSON |
| **Digital MER** | Solo en hardware caro | Dwell IQ periódico sobre barrido |
| **Histórico** | CSV propietario | CSV sesión + SQLite en proyecto + TXT |
| **Inventario unificado** | Apps separadas | Inventario + Monitor + supervisión en un `.crf` |
| **i18n** | Inglés principalmente | ES/EN nativo |
| **Open project** | Cerrado | Proyecto JSON portable, extensible |

### Próximas mejoras prioritarias (superioridad sostenida)

1. **MER nominal completo** — caída MER vs referencia en dwell (Fase C).
2. **Perfiles exportables** — paquete preset + referencias por venue/show.
3. **Supresión mantenimiento** — silenciar alarmas por zona/tiempo (estilo NMS broadcast).
4. **Baseline adaptativo opcional** — referencia con ventana móvil para entornos muy dinámicos.
5. **Correlación interferencia** — sugerir canal vecino cuando SNR cae en grupo de frecuencias.
6. **Informe PDF de supervisión** — snapshot de alarmas + umbrales para producción.
7. **API/script** — disparar fijar referencia / export log desde automatización.

---

## 5. UI — convenciones

| Panel | Rol |
|-------|-----|
| **Gestor frecuencias** | Matriz operativa canal × preset × umbrales × referencia |
| **ALARMAS** | Matriz maestra de presets + registro/ack + presets integrados |
| **Árbol flotante** | Estado en vivo, ack, contexto |
| **F5 / diálogo ámbito** | Overrides avanzados (zona, fabricante, modelo) |

Persistencia de columnas: `freq_manager_table_header`, `alarmas_preset_matrix_header` en layout del proyecto.

---

## 6. Flujo operativo recomendado

```
1. Importar inventario → presets inferidos por tecnología
2. Play → niveles estables en ensayo general
3. Seleccionar canales → «Fijar referencia» (o todos supervisados)
4. Preset «Nominal estándar» (−3 dB aviso / −6 dB crítico)
5. Show en directo → alarmas con causa legible en árbol e histórico
```

---

## 7. Referencias cruzadas

- Arquitectura app: [arquitectura_APP.md](arquitectura_APP.md)
- Monitor general: [monitor.md](monitor.md)
- Supervisión técnica: [monitor_supervision.md](monitor_supervision.md)
- Ayuda operador (F1): [monitor_supervision_ayuda.md](monitor_supervision_ayuda.md)
