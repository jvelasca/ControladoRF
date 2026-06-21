#Requires -Version 5.1
<#
.SYNOPSIS
  Instala libhackrf + herramientas HackRF en Windows para CONTROLADORF Monitor.

.DESCRIPTION
  1. Descarga PothosSDR (incluye hackrf_info, libhackrf.dll, dependencias).
  2. Instala en tools\PothosSDR (portable, sin tocar Program Files).
  3. Extrae cabeceras hackrf.h desde el código fuente oficial.
  4. Instala python_hackrf en el venv del proyecto.
  5. Verifica hackrf_info y el backend Python.

  Ejecutar desde la raíz del proyecto:
    powershell -ExecutionPolicy Bypass -File scripts\install_hackrf_windows.ps1
#>
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Tools = Join-Path $Root "tools"
$PothosDir = Join-Path $Tools "PothosSDR"
$PothosExe = Join-Path $Tools "PothosSDR-2021.07.25-vc16-x64.exe"
$PothosUrl = "https://downloads.myriadrf.org/builds/PothosSDR/PothosSDR-2021.07.25-vc16-x64.exe"
$HackrfSrcZip = Join-Path $Tools "hackrf-src.zip"
$HackrfSrcUrl = "https://github.com/greatscottgadgets/hackrf/archive/refs/tags/v2024.02.1.zip"
$HackrfInclude = Join-Path $Tools "hackrf-include"
$VenvPython = Join-Path $Root "env\Scripts\python.exe"
$VenvPip = Join-Path $Root "env\Scripts\pip.exe"
$EnvScript = Join-Path $Root "scripts\hackrf_env.ps1"

function Write-Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }

New-Item -ItemType Directory -Force -Path $Tools | Out-Null

# --- 1. PothosSDR (binarios) ---
Write-Step "PothosSDR / libhackrf"
if (-not (Test-Path $PothosExe)) {
    Write-Host "Descargando $PothosUrl ..."
    Invoke-WebRequest -Uri $PothosUrl -OutFile $PothosExe
}

$BinDir = Join-Path $PothosDir "bin"
if (-not (Test-Path (Join-Path $BinDir "hackrf_info.exe"))) {
    Write-Host "Instalando PothosSDR en $PothosDir (puede tardar 1-2 min)..."
    New-Item -ItemType Directory -Force -Path $PothosDir | Out-Null
    $proc = Start-Process -FilePath $PothosExe -ArgumentList "/S", "/D=$PothosDir" -Wait -PassThru
    if ($proc.ExitCode -ne 0) {
        throw "Instalador PothosSDR terminó con código $($proc.ExitCode)"
    }
}

if (-not (Test-Path (Join-Path $BinDir "hackrf_info.exe"))) {
    throw "No se encontró hackrf_info.exe en $BinDir"
}
Write-Host "OK: hackrf_info en $BinDir" -ForegroundColor Green

# --- 2. Cabeceras hackrf.h ---
Write-Step "Cabeceras libhackrf"
if (-not (Test-Path $HackrfSrcZip)) {
    Write-Host "Descargando fuentes HackRF..."
    Invoke-WebRequest -Uri $HackrfSrcUrl -OutFile $HackrfSrcZip
}
if (-not (Test-Path (Join-Path $HackrfInclude "hackrf.h"))) {
    Expand-Archive -Path $HackrfSrcZip -DestinationPath (Join-Path $Tools "hackrf-src-unpack") -Force
    $srcRoot = Get-ChildItem (Join-Path $Tools "hackrf-src-unpack") -Directory | Select-Object -First 1
    $includeSrc = Join-Path $srcRoot.FullName "host\libhackrf\src"
    New-Item -ItemType Directory -Force -Path $HackrfInclude | Out-Null
    Copy-Item (Join-Path $includeSrc "hackrf.h") $HackrfInclude -Force
}
Write-Host "OK: hackrf.h en $HackrfInclude" -ForegroundColor Green

# --- 3. Variables de entorno del proyecto ---
Write-Step "Generando scripts\hackrf_env.ps1"
@(
    "# Auto-generado por install_hackrf_windows.ps1",
    "`$Root = `"$Root`"",
    "`$env:HACKRF_LIB_DIR = `"$BinDir`"",
    "`$env:HACKRF_INCLUDE_DIR = `"$HackrfInclude`"",
    "`$env:PATH = `"$BinDir;`" + `$env:PATH",
    "Write-Host 'HackRF PATH: ' `$env:HACKRF_LIB_DIR"
) | Set-Content -Path $EnvScript -Encoding UTF8

# --- 4. python_hackrf (opcional; Fase B usa hackrf_sweep CLI) ---
Write-Step "python_hackrf (opcional)"
if (-not (Test-Path $VenvPip)) {
    throw "No existe el venv en env\. Cree el entorno Python del proyecto primero."
}
$env:HACKRF_LIB_DIR = $BinDir
$env:HACKRF_INCLUDE_DIR = $HackrfInclude
$env:INCLUDE = "$HackrfInclude;$env:INCLUDE"
$env:PATH = "$BinDir;$env:PATH"

& $VenvPip install python_hackrf 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "OK: python_hackrf instalado" -ForegroundColor Green
} else {
    Write-Host "AVISO: python_hackrf no compiló — Fase B usa hackrf_sweep CLI (suficiente)" -ForegroundColor Yellow
}

# --- 5. Verificación ---
Write-Step "Verificación"
& (Join-Path $BinDir "hackrf_info.exe")
try {
    $pyCheck = @"
import python_hackrf as ph
devs = ph.HackRFDevice.get_all_devices()
print('python_hackrf OK:', len(devs), 'dispositivo(s)')
"@
    & $VenvPython -c $pyCheck
} catch {
    Write-Host "python_hackrf no disponible (opcional)" -ForegroundColor Yellow
}

Write-Step "Spike hackrf_sweep"
& $VenvPython (Join-Path $Root "scripts\monitor_spike_hackrf_sweep.py")

Write-Step "Instalación completada"
Write-Host @"

Antes de usar la app Monitor, cargue el entorno en cada sesión PowerShell:

  . .\scripts\hackrf_env.ps1

Luego ejecute la app o los diagnósticos:

  `$env:PYTHONPATH='src'
  .\env\Scripts\python.exe scripts\monitor_sdr_setup.py --backend

"@ -ForegroundColor Yellow
