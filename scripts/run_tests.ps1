$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$env:PYTHONPATH = "src"
$Python = Join-Path $Root "env\Scripts\python.exe"

Write-Host "== Instalando dependencias de test ==" -ForegroundColor Cyan
& $Python -m pip install -q -r requirements.txt

Write-Host "`n== Smoke startup ==" -ForegroundColor Cyan
& $Python (Join-Path $Root "scripts\smoke_startup.py")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "`n== Tests unitarios (tests/) ==" -ForegroundColor Cyan
& $Python -m pytest tests -v --tb=short
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "`n== Tests GUI (tests_gui/) ==" -ForegroundColor Cyan
& $Python -m pytest tests_gui -v --tb=short
exit $LASTEXITCODE
