#Requires -Version 5.1
# Utilidades compartidas para localizar GitHub CLI (gh) en Windows.

function Initialize-GitHubCli {
    if (Get-Command gh -ErrorAction SilentlyContinue) {
        return
    }
    $candidates = @(
        (Join-Path $env:ProgramFiles "GitHub CLI\gh.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "GitHub CLI\gh.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\GitHub CLI\gh.exe")
    )
    foreach ($exe in $candidates) {
        if (Test-Path $exe) {
            $dir = Split-Path $exe -Parent
            $env:Path = "$dir;$env:Path"
            return
        }
    }
    throw @"
GitHub CLI (gh) no encontrado en el PATH.

Instale con:
  winget install --id GitHub.cli -e

Luego cierre y abra la terminal, o ejecute:
  `$env:Path += ';C:\Program Files\GitHub CLI'
"@
}

Initialize-GitHubCli
