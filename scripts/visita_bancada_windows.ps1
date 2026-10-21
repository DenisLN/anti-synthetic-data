# Visita à bancada num comando (scripts\VISITA_BANCADA.cmd). Mesmo preparo do
# START_BENCH (ambiente, bench_config.ps1, fator da probe perguntado na hora);
# depois scripts\visita_bancada.py conduz as etapas. Tensão e frequência são
# definidas por etapa pelo orquestrador; as confirmações que energizam são
# digitadas pelo operador em cada etapa.
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path $PSScriptRoot -Parent
Set-Location $ProjectRoot
$utf8 = New-Object System.Text.UTF8Encoding($false)
[Console]::InputEncoding = $utf8
[Console]::OutputEncoding = $utf8
$OutputEncoding = $utf8
$env:PYTHONUTF8 = "1"

Write-Host "Preparando/atualizando o ambiente Python..."
& (Join-Path $PSScriptRoot "setup_windows.ps1")
$python = Join-Path $ProjectRoot "env\Scripts\python.exe"

. (Join-Path $PSScriptRoot "bench_config.ps1")

if (-not ($args -contains "--plano")) {
    $probe = Read-Host "Digite o fator EXATO escrito na probe de tensão instalada (ex.: 10, 100)"
    $parsedProbe = 0.0
    if (-not [double]::TryParse(
        $probe,
        [Globalization.NumberStyles]::Float,
        [Globalization.CultureInfo]::InvariantCulture,
        [ref]$parsedProbe
    ) -or $parsedProbe -le 0) {
        throw "Fator de probe inválido. Não é seguro continuar."
    }
    $env:VOLTAGE_PROBE_ATTENUATION = $probe
}

New-Item -ItemType Directory -Force -Path logs | Out-Null
& $python (Join-Path $PSScriptRoot "visita_bancada.py") @args
exit $LASTEXITCODE
