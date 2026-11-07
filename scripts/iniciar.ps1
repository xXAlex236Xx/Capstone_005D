param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$raizAgricolix = Split-Path -Parent $PSScriptRoot
$backendAgricolix = Join-Path $raizAgricolix 'FASE 2\DonaLaura\backend'
$frontendAgricolix = Join-Path $raizAgricolix 'FASE 2\DonaLaura\frontend'
$logsAgricolix = Join-Path $raizAgricolix '.local'
New-Item -ItemType Directory -Path $logsAgricolix -Force | Out-Null

function Responde($urlAgricolix) {
    try { return (Invoke-WebRequest -Uri $urlAgricolix -UseBasicParsing -TimeoutSec 3).StatusCode -eq 200 }
    catch { return $false }
}

try {
    $pythonAgricolix = Join-Path $backendAgricolix '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $pythonAgricolix)) { throw 'Falta el entorno Python. Sigue la instalación del README.' }
    if (-not (Test-Path -LiteralPath (Join-Path $frontendAgricolix 'node_modules\vite\bin\vite.js'))) { throw 'Faltan las dependencias de la interfaz. Ejecuta npm install en frontend.' }
    if (-not (Test-Path -LiteralPath (Join-Path $backendAgricolix '.env'))) { throw 'Falta backend/.env. Copia .env.example y configura la conexión de PostgreSQL.' }
    $nodeAgricolix = (Get-Command node -ErrorAction Stop).Source
    $procesosAgricolix = @()
    $archivoProcesos = Join-Path $logsAgricolix 'procesos.json'
    if (Test-Path -LiteralPath $archivoProcesos) { $procesosAgricolix = Get-Content -LiteralPath $archivoProcesos -Raw | ConvertFrom-Json }
    $procesosVigentes = @()
    foreach ($registroVigente in $procesosAgricolix) {
        $procesoVigente = Get-Process -Id $registroVigente.id -ErrorAction SilentlyContinue
        if ($procesoVigente -and $procesoVigente.StartTime.ToUniversalTime().ToString('o') -eq $registroVigente.inicio) { $procesosVigentes += $registroVigente }
    }
    $procesosAgricolix = @($procesosVigentes)
    if (-not (Responde 'http://127.0.0.1:8000/health')) {
        Push-Location $backendAgricolix
        try { & $pythonAgricolix crear_admin.py; if ($LASTEXITCODE -ne 0) { throw 'No se pudo preparar la base de datos. Comprueba PostgreSQL y .env.' } }
        finally { Pop-Location }
        $proceso = Start-Process -FilePath $pythonAgricolix -ArgumentList @('-m','uvicorn','main:app','--host','127.0.0.1','--port','8000') -WorkingDirectory $backendAgricolix -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logsAgricolix 'backend.log') -RedirectStandardError (Join-Path $logsAgricolix 'backend-error.log') -PassThru
        $procesosAgricolix += @{ id=$proceso.Id; inicio=$proceso.StartTime.ToUniversalTime().ToString('o'); tipo='backend' }
    }
    if (-not (Responde 'http://127.0.0.1:5173/')) {
        $proceso = Start-Process -FilePath $nodeAgricolix -ArgumentList @('./node_modules/vite/bin/vite.js','--host','127.0.0.1','--port','5173','--strictPort') -WorkingDirectory $frontendAgricolix -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logsAgricolix 'frontend.log') -RedirectStandardError (Join-Path $logsAgricolix 'frontend-error.log') -PassThru
        $procesosAgricolix += @{ id=$proceso.Id; inicio=$proceso.StartTime.ToUniversalTime().ToString('o'); tipo='frontend' }
    }
    ConvertTo-Json -InputObject @($procesosAgricolix) | Set-Content -LiteralPath $archivoProcesos -Encoding UTF8
    $finAgricolix = (Get-Date).AddSeconds(35)
    do {
        if ((Responde 'http://127.0.0.1:8000/health') -and (Responde 'http://127.0.0.1:5173/')) {
            Write-Host 'Agricolix disponible en http://127.0.0.1:5173'
            $primerAcceso = Join-Path $logsAgricolix 'primer-acceso.txt'
            if (Test-Path -LiteralPath $primerAcceso) { Write-Host "Acceso inicial: $primerAcceso" }
            if (-not $NoBrowser) { Start-Process 'http://127.0.0.1:5173' -WindowStyle Hidden }
            exit 0
        }
        Start-Sleep -Milliseconds 400
    } while ((Get-Date) -lt $finAgricolix)
    throw 'La aplicación no respondió a tiempo. Revisa los registros de .local y que los puertos 8000 y 5173 estén libres.'
} catch {
    Write-Host "No se pudo iniciar Agricolix: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
