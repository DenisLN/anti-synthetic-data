param(
    [int]$CapturesPerClass = 1,
    [string]$SnrLevels = "30"
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$env:BENCH_MODE = "0"
$env:ARM_OUTPUT = "NO"
$env:SIM_CAPTURES_PER_CLASS = "$CapturesPerClass"
$env:SNR_LEVELS_DB = $SnrLevels

& .\env\Scripts\python.exe mestre.py
if ($LASTEXITCODE -ne 0) {
    throw "Simulação falhou com código $LASTEXITCODE."
}

