param(
    [int]$CapturesPerClass = 1,
    [string]$SnrLevels = "30"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path $PSScriptRoot -Parent
Set-Location $ProjectRoot
$env:BENCH_MODE = "0"
$env:ARM_OUTPUT = "NO"
$env:SIM_CAPTURES_PER_CLASS = "$CapturesPerClass"
$env:SNR_LEVELS_DB = $SnrLevels

& (Join-Path $ProjectRoot "env\Scripts\python.exe") (Join-Path $ProjectRoot "logica\mestre.py")
if ($LASTEXITCODE -ne 0) {
    throw "Simulação falhou com código $LASTEXITCODE."
}

