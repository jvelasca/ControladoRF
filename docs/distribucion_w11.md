# Distribución Windows 11 — CONTROLADORF

Guía para generar instaladores / paquetes ZIP al subir versiones.

---

## Resumen

| Script | Qué genera |
|--------|------------|
| `scripts/build_distribucion_w11.py` | **Paquete completo W11** (recomendado para distribuir) |
| `scripts/build_onefile_release.py` | Solo el `.exe` (pruebas rápidas) |

Salida por defecto en ambos casos:

```
%USERPROFILE%\Documents\distribuciones python\
```

---

## Flujo de release (checklist)

### 1. Subir versión

Edite `src/VERSION` (semver, una línea):

```
1.0.1
```

Opcional: anote cambios en el commit o changelog del proyecto.

### 2. Preparar herramientas HackRF (solo la primera vez o tras limpiar `tools\`)

En la máquina de build (Windows 11):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_hackrf_windows.ps1
```

Esto instala **PothosSDR portable** en `tools\PothosSDR\` con `hackrf_info`, `hackrf_sweep`, `hackrf_transfer` y `libhackrf.dll`.

> El script de distribución puede ejecutar este paso automáticamente si falta PothosSDR.

### 3. Generar paquete + instalador (recomendado)

**Un solo comando** (compila, Setup.exe y publica en GitHub):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\release_w11.ps1 -Notes "Notas de la versión"
```

Requisitos previos (una vez):
- [GitHub CLI](https://cli.github.com/) → `gh auth login`
- [Inno Setup 6](https://jrsoftware.org/isinfo.php) → `winget install JRSoftware.InnoSetup`
- `src\resources\update_config.json` con `enabled: true` y su cuenta GitHub

Solo compilar sin publicar:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\release_w11.ps1 -SkipPublish
```

Compilar manualmente:

```powershell
$env:PYTHONPATH = "src"
python scripts\build_distribucion_w11.py --installer
```

**Salida (formato actual — carpeta, no one-file):**

```
Documents\distribuciones python\
  ControladoRF-1.0.1-w11\
    ControladoRF.exe          ← lanzador principal
    _internal\                ← librerías (PyQt6, Python embebido)
    rf-tools\bin\             ← libhackrf + CLIs
    instalar_rf.ps1
    LEEME.txt
    manifest.json
    VERSION.txt
  ControladoRF-1.0.1-w11.zip
  ControladoRF-1.0.1-w11-Setup.exe   ← instalador recomendado (Inno Setup)
```

Ventajas frente al `.exe` único anterior:
- Arranque más rápido (sin descomprimir 100 MB cada vez).
- Sin bucles de consola por re-extracción PyInstaller.
- Más fácil de actualizar (sustituir carpeta o ZIP).

### 4. Probar en un PC limpio

1. Descomprimir el ZIP en una carpeta local (p. ej. `C:\ControladoRF`).
2. Conectar HackRF One.
3. **Primera vez en ese PC:** instalar driver USB con [Zadig](https://zadig.akeo.ie/) → WinUSB para `HackRF One (1d50:6089)`.
4. Ejecutar `instalar_rf.ps1`.
5. Abrir **`ControladoRF.exe`** (mantener `rf-tools\` y `_internal\` en la misma carpeta).
6. Monitor → Fuente → comprobar que detecta HackRF y arranca captura.

### 5. Publicar en GitHub Releases

Automático con `scripts\release_w11.ps1` (lee `update_config.json`).

Manual (solo subir assets ya compilados):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\publish_github_release.ps1
```

La app instalada comprobará actualizaciones al arrancar (Ayuda → Buscar actualizaciones…).
Descarga prioritaria: **Setup.exe**; alternativa: ZIP portable.

### 6. Distribuir

Distribuya el **Setup.exe** a usuarios finales. El ZIP queda como respaldo o actualización manual.

---

## Opciones del script principal

```powershell
# Sin copiar rf-tools (solo exe + scripts; pruebas)
python scripts\build_distribucion_w11.py --skip-rf-tools

# No descargar/instalar PothosSDR automáticamente
python scripts\build_distribucion_w11.py --skip-pothos-install

# Solo carpeta, sin ZIP
python scripts\build_distribucion_w11.py --no-zip

# Otra carpeta de salida
python scripts\build_distribucion_w11.py --output-dir "D:\releases"

# Reutilizar caché PyInstaller (más rápido)
python scripts\build_distribucion_w11.py --no-clean
```

---

## Contenido del paquete

| Elemento | Incluido | Notas |
|----------|----------|-------|
| App CONTROLADORF | Sí | `ControladoRF.exe` + `_internal\` |
| libhackrf + CLIs | Sí | `rf-tools\bin\` |
| Driver USB WinUSB | **No** | Una vez por PC vía Zadig (ver `LEEME.txt`) |
| Python | No | Embebido en el .exe |
| Proyectos del usuario | No | Se crean en `Documentos\ControladoRF\` |

---

## Estructura de archivos del sistema de build

```
scripts/
  build_distribucion_w11.py      ← entrada principal (release W11)
  build_onefile_release.py       ← solo .exe one-file (legacy/pruebas)
  publish_github_release.ps1     ← sube ZIP a GitHub Releases
  install_hackrf_windows.ps1     ← instala PothosSDR en tools\
  release/
    common.py                    ← PyInstaller, versión, icono
    rf_tools.py                  ← copia rf-tools desde PothosSDR
    package_w11.py               ← ensambla carpeta + ZIP
packaging/w11/
  instalar_rf.ps1                ← script post-instalación para el usuario
src/
  VERSION                        ← versión de la build
  app_paths.py                   ← rutas dev vs empaquetado
  core/monitor/hackrf_paths.py     ← busca rf-tools\bin junto al .exe
```

---

## Qué hace cada versión nueva

1. Cambiar `src/VERSION`.
2. Ejecutar `python scripts\build_distribucion_w11.py`.
3. Probar el ZIP en W11.
4. Publicar `ControladoRF-<version>-w11.zip`.

El nombre del ZIP y de la carpeta incluyen la versión automáticamente.

---

## Driver USB vs herramientas RF

Son dos capas distintas:

| Capa | Qué es | Incluido en ZIP |
|------|--------|-----------------|
| **Herramientas** | `libhackrf.dll`, `hackrf_sweep.exe`, … | Sí (`rf-tools\`) |
| **Driver USB** | WinUSB en el dispositivo HackRF | No — Zadig, una vez por equipo |

La app detecta `rf-tools\bin` automáticamente si está junto al `.exe` (ver `hackrf_paths.py`).

---

## Datos de usuario en instalaciones empaquetadas

Al ejecutar el `.exe` empaquetado:

| Dato | Ubicación |
|------|-----------|
| Proyectos `.crf` | Donde el usuario guarde (Archivo → Guardar) |
| Workspaces / BD | `Documentos\ControladoRF\workspace\` |
| Logs | `Documentos\ControladoRF\logs\` |

---

## Consola negra parpadeando (corregido en builds recientes)

Causas en builds **one-file** antiguos:
- `hackrf_sweep` / `hackrf_transfer` abrían CMD en cada captura.
- Detección USB vía PowerShell sin ventana oculta.
- Subprocess con `sys.executable` relanzaba el `.exe` empaquetado.

**Solución:** subprocess oculto + empaquetado **onedir** (`ControladoRF.exe` + `_internal\`).

---

## Actualizaciones vía GitHub

1. Configure `src\resources\update_config.json` (`enabled`, `github_owner`, `github_repo`).
2. Publique releases con `scripts\publish_github_release.ps1`.
3. En la app: **Ayuda → Buscar actualizaciones…** (también al arrancar si está activo).

La instalación **no es automática**: se abre la descarga del ZIP; el usuario sustituye la carpeta.

---

## Solución de problemas (build)

| Problema | Acción |
|----------|--------|
| `hackrf_info.exe no encontrado` | Ejecutar `install_hackrf_windows.ps1` |
| PyInstaller falla | `pip install pyinstaller>=6.0` en el venv |
| ZIP muy grande (~400–600 MB) | Normal: incluye PyQt6 + numpy + rf-tools |
| `hackrf_info` falla en build | Normal sin HackRF USB conectado; aviso, no error fatal |
| Copia incompleta rf-tools | Revisar `RF_TOOL_PATTERNS` en `scripts/release/rf_tools.py` |

---

## Relacionado

- [monitor_sdr_setup.md](monitor_sdr_setup.md) — arquitectura SDR y primer uso
- `scripts/install_hackrf_windows.ps1` — instalación dev de PothosSDR
