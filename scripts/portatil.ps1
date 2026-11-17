# Modo portátil: cuando estos scripts viven dentro de "agricolix data" (después de abrir
# Agricolix.exe por primera vez), el sistema usa su propio Python y PostgreSQL. En ese caso
# cada acción se delega al lanzador, que ya sabe encender, apagar y cambiar los datos.
$raizAgricolix = Split-Path -Parent $PSScriptRoot
$pythonPortatil = Join-Path $raizAgricolix 'runtime\python\python.exe'
$EsPortatil = Test-Path -LiteralPath $pythonPortatil
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = 'utf-8'

# Abre Agricolix como aplicación (Edge sin pestañas ni barra de direcciones).
# Si Edge no está instalado o no se puede abrir, usa el navegador predeterminado.
function Abrir-Agricolix {
    $url = 'http://127.0.0.1:5173'
    $rutas = @(${env:ProgramFiles(x86)}, $env:ProgramFiles, $env:LOCALAPPDATA) | Where-Object { $_ } |
        ForEach-Object { Join-Path $_ 'Microsoft\Edge\Application\msedge.exe' }
    $edge = $rutas | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if ($edge) {
        try { Start-Process -FilePath $edge -ArgumentList "--app=$url" -ErrorAction Stop; return }
        catch { }
    }
    Start-Process $url
}

function Invoke-Portatil([string]$Accion) {
    $lanzador = Join-Path (Join-Path $raizAgricolix 'launcher') 'agricolix.py'
    if (-not (Test-Path -LiteralPath $lanzador)) { throw 'Falta el lanzador del sistema. Abre Agricolix.exe.' }
    & $pythonPortatil $lanzador --raiz (Split-Path -Parent $raizAgricolix) $Accion
    if ($LASTEXITCODE -ne 0) { throw 'La operación no se completó.' }
}
