# Monitor — Instalación y equipos SDR

Guía de arquitectura para conectar **HackRF One** (predeterminado), **Airspy R2/Mini** y **Airspy HF+** en Windows, macOS y Linux, alineada con fuentes SDR++.

## Principios

1. **USB primero, driver después** — La app detecta el hardware por USB sin cargar libhackrf (rápido, no bloquea la GUI).
2. **Instalación guiada** — Panel FUENTE + script CLI; pasos concretos por SO.
3. **Captura en hilo worker** — Nunca abrir SDR en el hilo Qt.
4. **Simulación siempre disponible** — Desarrollo/UI sin hardware.
5. **Catálogo extensible** — Nuevos equipos = entrada en `sdr_catalog.py`.

## Equipos soportados (catálogo)

| ID | Equipo | Plugin SDR++ | USB (VID:PID) | CLI | Estado IQ |
|----|--------|--------------|---------------|-----|-----------|
| `hackrf` | HackRF One | hackrf_source | 1d50:6089 | hackrf_info | En progreso (python_hackrf) |
| `airspy` | Airspy R2/Mini | airspy_source | 1d50:60a1 | airspy_info | Pendiente |
| `airspy_hf` | Airspy HF+ | airspyhf_source | 1d50:60e1 | airspy_info | Pendiente |
| `mock` | Simulación | — | — | — | OK |

**Predeterminado del proyecto:** `hackrf`

## Arquitectura de capas

```
┌─────────────────────────────────────────────────────────┐
│  GUI: panel FUENTE + asistente + combo dispositivos      │
├─────────────────────────────────────────────────────────┤
│  device_discovery  →  USB (PnP / lsusb / profiler)       │
│  sdr_setup         →  CLI, .dll/.so, python backend      │
│  sdr_catalog       →  pasos instalación por plataforma     │
├─────────────────────────────────────────────────────────┤
│  spectrum_engine (worker)  →  spectrum_source.open/read  │
└─────────────────────────────────────────────────────────┘
```

### Archivos clave

| Ruta | Rol |
|------|-----|
| `src/core/monitor/sdr_catalog.py` | Definición equipos + pasos install |
| `src/core/monitor/sdr_setup.py` | Informes SetupReport |
| `src/core/monitor/device_discovery.py` | Combo fuentes + USB |
| `src/gui/monitor/monitor_source_setup_widget.py` | Asistente embebido |
| `src/gui/monitor/monitor_setup_dialog.py` | Asistente modal |
| `scripts/monitor_sdr_setup.py` | Diagnóstico CLI |

## Flujo primer uso (operador)

1. Abrir pestaña **Monitor** → sección **FUENTE**.
2. Esperar escaneo USB (segundos) — ver **Equipo detectado** con nombre y S/N.
3. Revisar cuadro **USB / CLI / Lib / Python / Listo**.
4. Si falta algo → seguir **Pasos recomendados** o **Asistente completo**.
5. **Comprobar de nuevo** (opcional con backend `--backend`).
6. Seleccionar fuente (HackRF ★ si conectado) → **Iniciar**.
7. Mientras no haya backend IQ → usar **Simulación**.

## Scripts de diagnóstico

```powershell
# Windows — desde la raíz del proyecto
$env:PYTHONPATH="src"
.\env\Scripts\python.exe scripts\monitor_sdr_setup.py
.\env\Scripts\python.exe scripts\monitor_sdr_setup.py --backend
.\env\Scripts\python.exe scripts\monitor_sdr_setup.py --json
.\env\Scripts\python.exe scripts\monitor_spike_engine.py
.\env\Scripts\python.exe scripts\monitor_spike_hackrf.py
```

```bash
# macOS / Linux
export PYTHONPATH=src
python3 scripts/monitor_sdr_setup.py --backend
python3 scripts/monitor_spike_engine.py
```

## Instalación por plataforma (resumen)

### HackRF One

| SO | Acción mínima |
|----|----------------|
| **Windows** | HackRF tools / PothosSDR → `hackrf_info` en PATH → opcional `pip install python_hackrf` |
| **macOS** | `brew install hackrf` |
| **Linux** | `apt install hackrf libhackrf-dev` + reglas udev |

### Airspy / HF+

| SO | Acción mínima |
|----|----------------|
| **Windows** | Paquete airspy.com + `airspy_info` |
| **macOS** | `brew install airspy` |
| **Linux** | `libairspy-dev airspy-tools` + udev |

## Roadmap backend IQ

| Fase | Entregable |
|------|------------|
| **A** *(actual)* | Catálogo + USB + asistente + mock + HackRF open con timeout |
| **B** *(hecho en Windows)* | Captura espectro HackRF vía `hackrf_sweep` CLI + PothosSDR portable |
| **C** | Airspy / HF+ vía libairspy |
| **D** | Backend unificado **SoapySDR** (opcional, muchos SDR++) |
| **E** | RTL-SDR y resto catálogo SDR++ |

## Relación con SDR++

SDR++ usa plugins por fuente (`hackrf_source`, `airspy_source`, …). CONTROLADORF **no embebe SDR++**; replica el mismo **modelo mental**:

- Detectar hardware
- Driver nativo o Soapy
- Stream IQ → FFT

Ventaja: integración con inventario RF y alarmas del show.

## Notas Windows (este PC)

- HackRF visible en USB (`VID_1D50&PID_6089`) sin instalar backend.
- `python_hackrf` requiere compilar contra `hackrf.h` — instalar **HackRF tools** primero.
- Usar asistente FUENTE → copiar comandos → **Comprobar de nuevo**.
