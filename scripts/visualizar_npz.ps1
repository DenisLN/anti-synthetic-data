param(
    [Parameter(Mandatory = $true)]
    [string]$Npz,
    [int]$Captura = -1,
    [switch]$SemAbrir
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path $PSScriptRoot -Parent
Set-Location $ProjectRoot

$argumentos = @($Npz)
if ($Captura -ge 0) {
    $argumentos += @("--captura", "$Captura")
}
if ($SemAbrir) {
    $argumentos += @("--sem-abrir")
}

& (Join-Path $ProjectRoot "env\Scripts\python.exe") (Join-Path $ProjectRoot "logica\visualizador.py") @argumentos
if ($LASTEXITCODE -ne 0) {
    throw "Visualização falhou com código $LASTEXITCODE."
}
