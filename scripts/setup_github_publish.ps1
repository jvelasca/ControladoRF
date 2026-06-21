#Requires -Version 5.1
<#
.SYNOPSIS
  Crea el repo GitHub (si falta), sube el codigo fuente y publica la release W11.

.Ejemplo
  powershell -ExecutionPolicy Bypass -File scripts\setup_github_publish.ps1
#>
param(
    [string]$Notes = "",
    [switch]$SkipSourcePush,
    [switch]$SkipRelease
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
Set-Location $Root
. (Join-Path $ScriptDir "github_cli.ps1")
. (Join-Path $ScriptDir "git_cli.ps1")

function Assert-GhAuth {
    gh auth status 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw @"
GitHub CLI no autenticado en esta terminal.
Ejecute:  gh auth login
(Login en github.com en el navegador NO basta; hace falta gh auth login)
"@
    }
    $login = gh api user --jq .login 2>&1
    if ($LASTEXITCODE -ne 0) { throw "No se pudo obtener el usuario GitHub: $login" }
    Write-Host "GitHub CLI: $login" -ForegroundColor Green
    return $login
}

function Get-ProjectConfig {
    $version = (Get-Content (Join-Path $Root "src\VERSION") -Raw).Trim()
    $cfg = Get-Content (Join-Path $Root "src\resources\update_config.json") -Raw | ConvertFrom-Json
    $owner = [string]$cfg.github_owner
    $repo = [string]$cfg.github_repo
    if ([string]::IsNullOrWhiteSpace($owner) -or [string]::IsNullOrWhiteSpace($repo)) {
        throw "Configure github_owner y github_repo en src\resources\update_config.json"
    }
    return @{
        Version = $version
        Slug    = "$owner/$repo"
        Owner   = $owner
        Repo    = $repo
    }
}

function Ensure-Git {
    . (Join-Path $ScriptDir "git_cli.ps1")
}

function Ensure-RepoOnGitHub {
    param([hashtable]$Cfg)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    gh repo view $Cfg.Slug 2>$null | Out-Null
    $exists = ($LASTEXITCODE -eq 0)
    $ErrorActionPreference = $prev
    if ($exists) {
        Write-Host "Repositorio remoto OK: $($Cfg.Slug)" -ForegroundColor Green
        return
    }
    Write-Host "Creando repositorio $($Cfg.Slug)..." -ForegroundColor Cyan
    gh repo create $Cfg.Slug --public --description "CONTROLADORF - Monitor RF / HackRF"
    if ($LASTEXITCODE -ne 0) { throw "No se pudo crear el repositorio $($Cfg.Slug)" }
}

function Push-Source {
    param([hashtable]$Cfg)
    Ensure-Git
    if (-not (Test-Path (Join-Path $Root ".git"))) {
        git init
        git branch -M main
    }
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    git remote get-url origin 2>$null | Out-Null
    $hasRemote = ($LASTEXITCODE -eq 0)
    $ErrorActionPreference = $prev
    if (-not $hasRemote) {
        git remote add origin "https://github.com/$($Cfg.Slug).git"
    }
    git add -A
    $status = git status --porcelain
    if ($status) {
        git commit -m "CONTROLADORF $($Cfg.Version) - release W11"
    } else {
        Write-Host "Sin cambios nuevos para commit." -ForegroundColor DarkGray
    }
    git push -u origin main
    Write-Host "Codigo fuente publicado en https://github.com/$($Cfg.Slug)" -ForegroundColor Green
}

Write-Host ""
Write-Host "=== CONTROLADORF - publicar en GitHub ===" -ForegroundColor Cyan
$login = Assert-GhAuth
$cfg = Get-ProjectConfig
Write-Host "Cuenta:    $login"
Write-Host "Repo:      $($cfg.Slug)"
Write-Host "Version:   $($cfg.Version)"
Write-Host ""

if (-not $SkipSourcePush) {
    Ensure-RepoOnGitHub -Cfg $cfg
    Push-Source -Cfg $cfg
}

if (-not $SkipRelease) {
    $publishArgs = @("-ExecutionPolicy", "Bypass", "-File", (Join-Path $Root "scripts\publish_github_release.ps1"))
    if ($Notes) { $publishArgs += @("-Notes", $Notes) }
    & powershell @publishArgs
}

Write-Host ""
Write-Host "Listo. Compruebe:" -ForegroundColor Green
Write-Host "  https://github.com/$($cfg.Slug)"
Write-Host "  https://github.com/$($cfg.Slug)/releases/tag/v$($cfg.Version)"
