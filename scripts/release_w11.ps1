#Requires -Version 5.1
<#
.SYNOPSIS
  Flujo completo de release W11: compilar, instalador Setup y publicar en GitHub.

.DESCRIPTION
  1. Lee versión (src\VERSION) y repo GitHub (src\resources\update_config.json)
  2. Compila paquete onedir + ZIP + Setup.exe (Inno Setup)
  3. Publica en GitHub Releases (Setup + ZIP) para activar actualizaciones automáticas

.PARAMETER Notes
  Notas de la release (markdown). Si no se indica, usa CHANGELOG.md o un texto por defecto.

.PARAMETER SkipPublish
  Solo compila; no sube a GitHub.

.PARAMETER SkipInstaller
  No genera Setup.exe (solo carpeta + ZIP).

.PARAMETER OutputDir
  Carpeta de salida (por defecto: Documentos\distribuciones python)

.Ejemplo
  powershell -ExecutionPolicy Bypass -File scripts\release_w11.ps1 -Notes "Correcciones monitor RF"
#>
param(
    [string]$Notes = "",
    [switch]$SkipPublish,
    [switch]$SkipInstaller,
    [string]$OutputDir = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root
. (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "github_cli.ps1")

function Get-ProjectVersion {
    $versionFile = Join-Path $Root "src\VERSION"
    if (-not (Test-Path $versionFile)) { throw "No se encontró src\VERSION" }
    return (Get-Content $versionFile -Raw).Trim()
}

function Get-GitHubConfig {
    $configPath = Join-Path $Root "src\resources\update_config.json"
    if (-not (Test-Path $configPath)) { throw "No se encontró update_config.json" }
    $cfg = Get-Content $configPath -Raw | ConvertFrom-Json
    $owner = [string]$cfg.github_owner
    $repo = [string]$cfg.github_repo
    if ([string]::IsNullOrWhiteSpace($owner) -or $owner.StartsWith("TU_")) {
        throw "Configure github_owner en src\resources\update_config.json"
    }
    if ([string]::IsNullOrWhiteSpace($repo)) {
        throw "Configure github_repo en src\resources\update_config.json"
    }
    return @{
        Owner   = $owner.Trim()
        Repo    = $repo.Trim()
        Slug    = "$($owner.Trim())/$($repo.Trim())"
        Enabled = [bool]$cfg.enabled
    }
}

function Get-ReleaseNotes {
    param([string]$Version)
    if ($Notes) { return $Notes }
    $changelog = Join-Path $Root "CHANGELOG.md"
    if (Test-Path $changelog) {
        $text = Get-Content $changelog -Raw
        if ($text -match "(?ms)##\s*$([regex]::Escape($Version)).*?(?=##\s|\z)") {
            return $Matches[0].Trim()
        }
        if ($text.Length -gt 4000) { return $text.Substring(0, 4000) + "`n..." }
        return $text.Trim()
    }
    return "CONTROLADORF $Version - Windows 11`n`nDescargue el instalador Setup.exe o el ZIP portable."
}

function Resolve-Python {
    $venv = Join-Path $Root "env\Scripts\python.exe"
    if (Test-Path $venv) { return $venv }
    $py = Get-Command python -ErrorAction SilentlyContinue
    if ($py) { return $py.Source }
    throw "No se encontró Python. Active el venv env\ o instale Python 3."
}

$Version = Get-ProjectVersion
$GitHub = Get-GitHubConfig
$DistRoot = if ($OutputDir) { $OutputDir } else { Join-Path $env:USERPROFILE "Documents\distribuciones python" }
$Python = Resolve-Python

Write-Host ""
Write-Host "=== CONTROLADORF Release W11 ===" -ForegroundColor Cyan
Write-Host "Versión:  $Version"
Write-Host "GitHub:   $($GitHub.Slug)"
Write-Host "Salida:   $DistRoot"
Write-Host "Updates:  $(if ($GitHub.Enabled) { 'activadas' } else { 'DESACTIVADAS - ponga enabled:true en update_config.json' })"
Write-Host ""

$buildArgs = @(
    "scripts\build_distribucion_w11.py",
    "--output-dir", $DistRoot
)
if (-not $SkipInstaller) {
    $buildArgs += "--installer"
}

Write-Host "Compilando paquete..." -ForegroundColor Yellow
& $Python @buildArgs
if ($LASTEXITCODE -ne 0) { throw "Falló la compilación (código $LASTEXITCODE)" }

$Zip = Join-Path $DistRoot "ControladoRF-$Version-w11.zip"
$Setup = Join-Path $DistRoot "ControladoRF-$Version-w11-Setup.exe"

if (-not (Test-Path $Zip)) { throw "No se generó $Zip" }
Write-Host "ZIP OK:   $Zip" -ForegroundColor Green
if (Test-Path $Setup) {
    Write-Host "Setup OK: $Setup" -ForegroundColor Green
} elseif (-not $SkipInstaller) {
    Write-Host "AVISO: No se generó Setup.exe. Instale Inno Setup 6." -ForegroundColor Yellow
}

if ($SkipPublish) {
    Write-Host ""
    Write-Host "Publicación omitida (-SkipPublish)." -ForegroundColor DarkGray
    exit 0
}

$Tag = "v$Version"
$ReleaseNotes = Get-ReleaseNotes -Version $Version
$Assets = @($Zip)
if (Test-Path $Setup) { $Assets += $Setup }

Write-Host ""
Write-Host "Publicando $Tag en $($GitHub.Slug)..." -ForegroundColor Cyan

$existing = gh release view $Tag --repo $GitHub.Slug 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "La release $Tag ya existe; subiendo assets..." -ForegroundColor Yellow
    foreach ($asset in $Assets) {
        gh release upload $Tag $asset --repo $GitHub.Slug --clobber
    }
    gh release edit $Tag --repo $GitHub.Slug --title "CONTROLADORF $Version (Windows 11)" --notes $ReleaseNotes
} else {
    gh release create $Tag @Assets `
        --repo $GitHub.Slug `
        --title "CONTROLADORF $Version (Windows 11)" `
        --notes $ReleaseNotes
}

$releaseUrl = "https://github.com/$($GitHub.Slug)/releases/tag/$Tag"
Write-Host ""
Write-Host "Release publicada:" -ForegroundColor Green
Write-Host "  $releaseUrl"
Write-Host ""
Write-Host "Los usuarios con enabled:true recibirán aviso de actualización al arrancar la app."
