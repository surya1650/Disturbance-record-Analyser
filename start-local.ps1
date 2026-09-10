param([int]$Port = 8091, [switch]$Install)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$env:OPENBLAS_NUM_THREADS = '1'
$env:PYTHONPATH = Join-Path $PSScriptRoot 'src'
$localPython = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $localPython)) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the local Python environment.' }
    $Install = $true
}
if ($Install) {
    & $localPython -m pip install -e '.[app]'
    if ($LASTEXITCODE -ne 0) { throw 'Application dependencies could not be installed.' }
}
Write-Host "Open http://127.0.0.1:$Port in your browser. Press Ctrl+C to stop."
& $localPython -m dranalyser.application --port $Port
exit $LASTEXITCODE
