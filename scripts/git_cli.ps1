#Requires -Version 5.1
# Localiza Git en Windows (PATH a veces no se actualiza tras winget install).

function Initialize-Git {
    if (Get-Command git -ErrorAction SilentlyContinue) {
        return
    }
    $candidates = @(
        (Join-Path $env:ProgramFiles "Git\cmd\git.exe"),
        (Join-Path $env:ProgramFiles "Git\bin\git.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "Git\cmd\git.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Git\cmd\git.exe")
    )
    foreach ($exe in $candidates) {
        if (Test-Path $exe) {
            $dir = Split-Path $exe -Parent
            $env:Path = "$dir;$env:Path"
            return
        }
    }
    throw @"
Git no encontrado en el PATH.

Instale con:
  winget install --id Git.Git -e

Luego cierre y abra la terminal, o reinicie Cursor.
"@
}

Initialize-Git
