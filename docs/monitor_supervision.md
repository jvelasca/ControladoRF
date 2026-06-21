# Supervisión Monitor — decisiones y arquitectura

Documento de referencia para la **supervisión de portadoras** del módulo Monitor. Complementa
[monitor.md](monitor.md), [monitor_supervision_premisas.md](monitor_supervision_premisas.md)
(visión de producto) y la guía operativa [monitor_supervision_ayuda.md](monitor_supervision_ayuda.md).

**Estado:** v2 — presets, matriz canal×check, referencia nominal, alarmas MER/sync.

---

## 1. Decisiones cerradas

| # | Tema | Decisión |
|---|------|----------|
| 1 | **Ubicación UI** | Acordeón: GESTOR FRECUENCIAS (matriz operativa) + ALARMAS (presets + log) + árbol flotante. |
| 2 | **Alcance** | Todos los canales del inventario entran en supervisión por defecto (`enabled: true`). |
| 3 | **Umbrales** | Presets por tecnología + overrides por canal; modos `noise_relative` y `nominal_delta`. |
| 4 | **Precedencia legacy** | Canal → Modelo → Fabricante → Tipo → Zona → Proyecto (diálogo F5). |
| 5 | **Referencia nominal** | `ChannelReferenceCapture` por canal; fijar en el aire antes de supervisión Δ dB. |
| 6 | **Presets integrados** | Solo lectura; copiar a preset usuario para editar. |
| 7 | **Warning memorizado** | Ack manual o auto-reset configurable. |
| 8 | **Log histórico** | CSV sesión + SQLite proyecto; export CSV/TXT. |
| 9 | **Tipos de alarma** | Catálogo canónico (`alarm_catalog.py`). |
| 10 | **Layout tablas** | Columnas redimensionables; estado en proyecto. |

---

## 2. Persistencia (schema v2)

`project.modules.monitor.supervision` — `SupervisionState.version = 2`

| Campo | Descripción |
|-------|-------------|
| `default_preset_id` | Preset por defecto del proyecto |
| `user_presets` | Presets personalizados (dict) |
| `targets[].preset_id` | Preset asignado al canal |
| `targets[].check_overrides` | Overrides parciales por check |
| `targets[].threshold_mode` | Override de modo (`noise_relative` / `nominal_delta`) |
| `targets[].reference` | Referencia nominal capturada |
| `rule_overrides` | Overrides legacy por ámbito (F5) |

---

## 3. Pipeline

```
Inventario → sync_supervision_targets()
  → SupervisionEngine.process_frame()
  → resolve_effective_thresholds() por canal
  → evaluate checks (ruido o Δ vs referencia)
  → AlarmManager → CSV + SQLite
  → GUI (matriz, árbol, espectro)
```

Dwell digital (MER/sync): ver §6.

---

## 4. Archivos principales

| Ruta | Rol |
|------|-----|
| `threshold_checks.py` | Catálogo de checks |
| `alarm_presets.py` | Presets integrados por tecnología |
| `threshold_resolver.py` | Resolución efectiva + filas matriz UI |
| `alarm_rule_format.py` | Textos legibles de reglas de alarma |
| `rule_evaluator.py` | Evaluación SNR/portadora nominal y vs ruido |
| `alarm_manager.py` | Debounce, latch, ack |
| `monitor_freq_manager_panel.py` | Matriz operativa canal |
| `monitor_alarm_preset_matrix_widget.py` | Matriz maestra presets |
| `monitor_supervision_thresholds_dialog.py` | Overrides por ámbito (F5) |

Tests: `tests/core/test_threshold_presets.py`, `test_nominal_threshold.py`, `test_supervision_rules.py`.

---

## 5. Supervisión digital (MER/sync)

Canales con `modulation_class` digital pueden medirse por barrido + dwell IQ.

| Modo | SNR (FFT) | MER/sync (dwell) |
|------|-----------|------------------|
| Solo SNR | Sí | No |
| SNR + MER/sync | Sí | Sí (periódico o SNR degradado) |

---

## 6. Atajos

F1 ayuda · F5 umbrales ámbito · F8 localizar · F9 ack — ver ayuda operativa.

---

## 7. Log REC y barra de estado

| Componente | Rol |
|--------------|-----|
| `supervision_log_session.py` | Sesiones REC: carpeta, `alarms.csv`, `session.json`, `report.txt` |
| `supervision_log_paths.py` | Resolución de rutas log/export |
| `monitor_alarmas_toolbar.py` | Barra panel ALARMAS + ventana flotante |
| `supervision_status_bar_widget.py` | Indicadores + REC en barra de estado app |
| `app_status_bar_panel.py` | Proyecto · supervisión · workspace |

Settings: `log_directory`, `log_export_directory`, `log_trigger`, `rec_start_mode`.

Ayuda operativa: [monitor_supervision_ayuda.md](monitor_supervision_ayuda.md) / [monitor_supervision_help.md](monitor_supervision_help.md).
