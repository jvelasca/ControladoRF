#Requires -Version 5.1
<#
.SYNOPSIS
  Comprueba las herramientas HackRF incluidas en la distribución CONTROLADORF.

.PARAMETER SkipVerify
  Solo configura PATH; no ejecuta hackrf_info (útil en post-instalación sin HackRF conectado).
#>
param(
    [switch]$SkipVerify
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$BinDir = Join-Path $Root "rf-tools\bin"
$HackrfInfo = Join-Path $BinDir "hackrf_info.exe"

function Write-Step($msg) {
    Write-Host ""
    Write-Host "==> $msg" -ForegroundColor Cyan
}

if (-not (Test-Path $HackrfInfo)) {
    throw "No se encontró $HackrfInfo. Descomprima el ZIP completo."
}

Write-Step "Configurando PATH local"
$env:HACKRF_LIB_DIR = $BinDir
$env:PATH = "$BinDir;" + $env:PATH
Write-Host "HACKRF_LIB_DIR = $BinDir" -ForegroundColor Green

Write-Step "Comprobando hackrf_info"
if ($SkipVerify) {
    Write-Host "Omitida verificación USB (-SkipVerify)." -ForegroundColor DarkGray
} else {
    & $HackrfInfo
    $code = $LASTEXITCODE
    if ($code -ne 0) {
        Write-Host ""
        Write-Host "hackrf_info falló (código $code)." -ForegroundColor Yellow
        Write-Host @"

Posibles causas en Windows 11:
  1. HackRF no conectado por USB.
  2. Driver USB no instalado (primera vez en este PC).

Instale el driver con Zadig (una sola vez):
  https://zadig.akeo.ie/
  - Options → List All Devices
  - Dispositivo: HackRF One (1d50:6089)
  - Driver: WinUSB → Replace Driver

Luego vuelva a ejecutar este script.
"@ -ForegroundColor Yellow
        exit $code
    }
}

Write-Step "Listo"
Write-Host @"

Las herramientas RF están configuradas para esta carpeta.
Inicie: $(Join-Path $Root "ControladoRF*.exe")

Nota: el driver WinUSB (Zadig) es independiente de rf-tools;
solo hace falta instalarlo una vez por equipo.
"@ -ForegroundColor Green
