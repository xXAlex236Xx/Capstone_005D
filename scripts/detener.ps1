$ErrorActionPreference = 'Stop'
$raizAgricolix = Split-Path -Parent $PSScriptRoot
$archivoProcesos = Join-Path $raizAgricolix '.local\procesos.json'
if (-not (Test-Path -LiteralPath $archivoProcesos)) { Write-Host 'No hay procesos registrados por el iniciador.'; exit 0 }
$procesosAgricolix = Get-Content -LiteralPath $archivoProcesos -Raw | ConvertFrom-Json
foreach ($registro in $procesosAgricolix) {
    $procesoAgricolix = Get-Process -Id $registro.id -ErrorAction SilentlyContinue
    # Un PID puede reutilizarse: verificar también el instante de inicio.
    if ($procesoAgricolix -and $procesoAgricolix.StartTime.ToUniversalTime().ToString('o') -eq $registro.inicio) {
        # taskkill /T incluye los procesos Python hijos, siempre de un PID registrado y verificado.
        & taskkill.exe /PID $registro.id /T /F | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'No se pudo detener un servidor. Ejecuta el archivo con el mismo usuario que lo inició.' }
    }
}
Write-Host 'Se detuvieron los servidores iniciados por Agricolix.'
