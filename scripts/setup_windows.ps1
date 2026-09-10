$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path $PSScriptRoot -Parent
Set-Location $ProjectRoot

$venvPython = Join-Path $ProjectRoot "env\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        py -3.11 -m venv env
    }
    elseif (Get-Command python -ErrorAction SilentlyContinue) {
        python -m venv env
    }
    else {
        throw "Ambiente env e Python ausentes. Instale Python 3.11 x64."
    }
}

$supported = & $venvPython -c "import sys; print(int((3, 9) <= sys.version_info[:2] <= (3, 12)))"
if ($LASTEXITCODE -ne 0 -or $supported.Trim() -ne "1") {
    throw "O ambiente env deve usar Python 3.9 a 3.12 (3.11 recomendado)."
}

& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "Falha ao atualizar pip." }
& $venvPython -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Falha ao instalar requirements.txt." }

Write-Host ""
Write-Host "Ambiente criado em $ProjectRoot\env"
Write-Host "Antes do preflight:"
Write-Host "1. Instale Keysight IO Libraries Suite ou NI-VISA x64."
Write-Host "2. Conecte a USB da AMETEK e confirme a porta COM10 no Windows."
Write-Host "3. Não conecte simultaneamente o cabo DB9 RS-232 da AMETEK."
Write-Host "4. O start_bench_windows.ps1 solicitará o fator real da probe."
