param([switch]$Original)
$ErrorActionPreference = 'Stop'
$raizAgricolix = Split-Path -Parent $PSScriptRoot
$backendAgricolix = Join-Path $raizAgricolix 'FASE 2\DonaLaura\backend'
$pythonAgricolix = Join-Path $backendAgricolix '.venv\Scripts\python.exe'
try {
    & (Join-Path $PSScriptRoot 'detener.ps1')
    Push-Location $backendAgricolix
    try {
        if ($Original) { & $pythonAgricolix demo.py --original }
        else { & $pythonAgricolix demo.py --activar }
        if ($LASTEXITCODE -ne 0) { throw 'No se cambió el entorno. Revisa la configuración de demostración.' }
    } finally { Pop-Location }
    & (Join-Path $PSScriptRoot 'iniciar.ps1')
} catch {
    Write-Host "No se pudo cambiar el entorno: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host 'Puedes usar Iniciar Agricolix.cmd para iniciar la configuración vigente.'
    exit 1
}
