$ErrorActionPreference = 'Stop'
$raizAgricolix = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot 'portatil.ps1')
try {
    if ($EsPortatil) { Invoke-Portatil '--respaldar'; exit 0 }
    $backendAgricolix = Join-Path $raizAgricolix 'FASE 2\DonaLaura\backend'
    Push-Location $backendAgricolix
    try { & '.venv\Scripts\python.exe' respaldo.py; if ($LASTEXITCODE -ne 0) { throw 'El respaldo no se completó.' } }
    finally { Pop-Location }
} catch {
    Write-Host "No se pudo respaldar: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
