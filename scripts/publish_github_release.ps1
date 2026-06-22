#Requires -Version 5.1
<#
.SYNOPSIS
  Publica el ZIP y Setup W11 en GitHub Releases (usa update_config.json).

  Preferible: scripts\release_w11.ps1 (compila + publica en un paso).

.PARAMETER Version
  Versión semver. Por defecto lee src\VERSION.

.PARAMETER Repo
  owner/name. Por defecto lee update_config.json.

.PARAMETER Notes
  Notas markdown de la release.
#>
param(
    [string]$Version = "",
    [string]$Repo = "",
    [string]$Notes = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
. (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "github_cli.ps1")

if (-not $Version) {
    $Version = (Get-Content (Join-Path $Root "src\VERSION") -Raw).Trim()
}

if (-not $Repo) {
    $cfg = Get-Content (Join-Path $Root "src\resources\update_config.json") -Raw | ConvertFrom-Json
    $Repo = "$($cfg.github_owner)/$($cfg.github_repo)"
}

$DistRoot = Join-Path $env:USERPROFILE "Documents\distribuciones python"
$Zip = Join-Path $DistRoot "ControladoRF-$Version-w11.zip"
$Setup = Join-Path $DistRoot "ControladoRF-$Version-w11-Setup.exe"

if (-not (Test-Path $Zip)) {
    throw "No se encontró $Zip. Ejecute: scripts\release_w11.ps1 -SkipPublish"
}

$Tag = "v$Version"
$Assets = @($Zip)
if (Test-Path $Setup) { $Assets += $Setup }

if (-not $Notes) {
    $Notes = "CONTROLADORF $Version - Windows 11"
}

Write-Host "Publicando $Tag en $Repo ..." -ForegroundColor Cyan
$prev = $ErrorActionPreference
$ErrorActionPreference = "Continue"
gh release view $Tag --repo $Repo 2>$null | Out-Null
$releaseExists = ($LASTEXITCODE -eq 0)
$ErrorActionPreference = $prev
if ($releaseExists) {
    foreach ($asset in $Assets) {
        gh release upload $Tag $asset --repo $Repo --clobber
    }
    gh release edit $Tag --repo $Repo --title "CONTROLADORF $Version (Windows 11)" --notes $Notes
} else {
    gh release create $Tag @Assets `
        --repo $Repo `
        --title "CONTROLADORF $Version (Windows 11)" `
        --notes $Notes
}

Write-Host "Release publicada: https://github.com/$Repo/releases/tag/$Tag" -ForegroundColor Green
