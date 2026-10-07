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
$logica = Join-Path $ProjectRoot "logica"

. (Join-Path $PSScriptRoot "bench_config.ps1")

if ([string]::IsNullOrWhiteSpace($env:VOLTAGE_PROBE_ATTENUATION)) {
    $probe = Read-Host "Digite o fator EXATO da probe de tensão instalada (ex.: 10, 100)"
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

# Tensão/frequência do teste: perguntadas uma única vez aqui (não mudam durante
# a sessão da CLI) porque BASE_VOLTAGE_RMS/GRID_FREQUENCY_HZ/os limites
# derivados são lidos como constantes de módulo no processo Python assim que
# ele inicia (logica/mestre.py) — reiniciar essa escolha exigiria reiniciar o
# processo, não só um comando da CLI.
$vrmsInput = Read-Host "Digite a TENSÃO RMS FASE-NEUTRO do teste em V (ex.: 127 ou 220; máximo 270)"
$vrms = 0.0
if (-not [double]::TryParse(
    $vrmsInput,
    [Globalization.NumberStyles]::Float,
    [Globalization.CultureInfo]::InvariantCulture,
    [ref]$vrms
) -or $vrms -le 0) {
    throw "Tensão RMS inválida."
}

$freqInput = Read-Host "Digite a FREQUÊNCIA desejada para o teste em Hz (ex.: 60, 50)"
$freq = 0.0
if (-not [double]::TryParse(
    $freqInput,
    [Globalization.NumberStyles]::Float,
    [Globalization.CultureInfo]::InvariantCulture,
    [ref]$freq
) -or $freq -le 0) {
    throw "Frequência inválida."
}

$env:BASE_VOLTAGE_RMS = "$vrms"
$env:GRID_FREQUENCY_HZ = "$freq"

# Seed base (v1.13): opcional, pela variável BASE_SEED (inteiro >= 0) antes de
# rodar START_BENCH, ou por "set seed N" dentro da CLI. Sem ela, o padrão do
# código (20260827). Nada a digitar aqui.
if (-not [string]::IsNullOrWhiteSpace($env:BASE_SEED)) {
    $parsedSeed = [long]0
    if (-not [long]::TryParse($env:BASE_SEED.Trim(), [ref]$parsedSeed) -or $parsedSeed -lt 0) {
        throw "BASE_SEED inválida ($env:BASE_SEED): use um inteiro >= 0."
    }
    $seedTexto = "$parsedSeed (variável BASE_SEED)"
} else {
    $seedTexto = "padrão do código (mude com 'set seed N' na CLI)"
}

# Range sempre 300 Vrms; todos os limites iguais ao teto do hardware.
# 380 V (v1.13, decisão do dono: opção B — não suportado): a MX30-3Pi gera no
# máximo 300 Vrms POR FASE (fase-neutro) e 425 Vp (manual §4.14 p. 84), e a
# bancada mede UMA fase, L-N. 380 Vrms L-N (537 Vp) é impossível nesta fonte.
# Num sistema 220/380 V, 380 V é a tensão de LINHA (fase-fase) e cada fase tem
# 380/√3 = 219,4 V — teste com 220. Medir 380 V fase-fase (fases a 0/120/240°,
# sonda diferencial ou CH1-CH2) é a opção A, documentada em CHANGELOG/v1.13.md
# e NÃO implementada. Os 270 V deixam ~10% de folga para os swells até o
# limite rms por fase.
if ($vrms -le 270.0) {
    $sourceRange = 300.0
} else {
    $porFase = [math]::Round($vrms / [math]::Sqrt(3), 1)
    throw ("Tensão $vrms Vrms recusada: a bancada aceita no máximo 270 Vrms FASE-NEUTRO. " +
        "A AMETEK MX30-3Pi gera até 300 Vrms por fase (425 Vp), e a bancada mede uma fase L-N. " +
        "Se $vrms V for a tensão de LINHA (fase-fase) de um sistema trifásico, cada fase tem " +
        "$vrms / raiz(3) = $porFase V: rode de novo e digite essa tensão por fase, se for ate 270 " +
        "(ex.: sistema 220/380 V -> digite 220). " +
        "Medir fase-fase exige modo trifásico e outra fiação (opção A, CHANGELOG/v1.13.md, não implementada).")
}
$eutMaxRms = $sourceRange   # = 300 — sem restrição abaixo do range físico

# Pico máximo = 98% do teto do range 300 V → 415 Vp (muito generoso).
$eutMaxPeak = [math]::Round($sourceRange * [math]::Sqrt(2) * 0.98, 1)

$env:SOURCE_VOLTAGE_RANGE_RMS = "$sourceRange"
$env:EUT_MAX_VOLTAGE_RMS      = "$eutMaxRms"
$env:EUT_MAX_PEAK_V           = "$eutMaxPeak"

Write-Host "Configuração da bancada:"
Write-Host "  -> Tensão RMS: $env:BASE_VOLTAGE_RMS Vrms"
Write-Host "  -> Limite EUT: $env:EUT_MAX_VOLTAGE_RMS Vrms | Pico Máx: $env:EUT_MAX_PEAK_V Vp | Range Fonte: $env:SOURCE_VOLTAGE_RANGE_RMS Vrms"
Write-Host "  -> Frequência: $env:GRID_FREQUENCY_HZ Hz"
Write-Host "  -> Probe Tensão: $env:VOLTAGE_PROBE_ATTENUATION x"
Write-Host "  -> Seed base: $seedTexto"

New-Item -ItemType Directory -Force -Path logs | Out-Null

# A partir daqui a sessão é conduzida pela CLI interativa (logica/cli.py):
# comm/trigger/lowvoltage/native/run são comandos explícitos digitados pelo
# operador, não mais um fluxo fixo de 5 etapas obrigatórias — ver README
# seção 5.3 e o "help" da própria CLI.
& $python (Join-Path $logica "cli.py")
exit $LASTEXITCODE
