param(
    [ValidateSet("Full", "Communication", "Trigger", "LowVoltage", "Run")]
    [string]$Stage = "Full"
)

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

if ($Stage -in @("Full", "LowVoltage", "Run")) {
    # Pergunta interativa sobre a Tensão RMS e Frequência para o teste
    $vrmsInput = Read-Host "Digite a TENSÃO RMS desejada para o teste em V (ex.: 127, 220, 380)"
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

    # Range sempre 300 Vrms; todos os limites iguais ao teto do hardware.
    if ($vrms -le 270.0) {
        $sourceRange = 300.0
    } else {
        throw "Tensão $vrms Vrms excede o range máximo da AMETEK MX30 (300 Vrms)."
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
}
Write-Host "  -> Probe Tensão: $env:VOLTAGE_PROBE_ATTENUATION x"

New-Item -ItemType Directory -Force -Path logs | Out-Null
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$log = "logs\startup-bench-$Stage-$timestamp.log"

function Invoke-CheckedPython {
    param([string[]]$Arguments)
    $previousPreference = $ErrorActionPreference
    $nativeExitCode = 1
    try {
        $ErrorActionPreference = "Continue"
        & $python @Arguments 2>&1 | Tee-Object -FilePath $log -Append
        $nativeExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousPreference
    }
    if ($nativeExitCode -ne 0) {
        throw "Inicialização abortada em: python $Arguments (código $nativeExitCode)"
    }
}

$preflightPy = Join-Path $logica "preflight.py"
$mestrePy = Join-Path $logica "mestre.py"

switch ($Stage) {
    "Communication" {
        Write-Host "Comunicação e identificação, OUTPUT OFF"
        Invoke-CheckedPython -Arguments @($preflightPy)
    }
    "Trigger" {
        Write-Host "Aquisição forçada do Keysight, OUTPUT OFF (BNC ainda não testado)"
        Invoke-CheckedPython -Arguments @($preflightPy, "--trigger-test")
    }
    "LowVoltage" {
        $confirmation = Read-Host "Confirme probe, cabos, E-stop e EUT. Digite ENERGIZAR-5V"
        if ($confirmation -cne "ENERGIZAR-5V") {
            throw "Execução cancelada sem energização."
        }
        $env:ARM_OUTPUT = "YES"
        Write-Host "Validação automática em baixa tensão (5 Vrms)"
        Invoke-CheckedPython -Arguments @($preflightPy, "--low-voltage")
    }
    "Run" {
        $confirmation = Read-Host "Todos os preflights passaram? Digite EXECUTAR-20-CLASSES"
        if ($confirmation -cne "EXECUTAR-20-CLASSES") {
            throw "Execução cancelada."
        }
        $env:ARM_OUTPUT = "YES"
        $env:REAL_CAPTURES_PER_CLASS = "1"
        Write-Host "Uma captura de cada uma das 20 classes"
        Invoke-CheckedPython -Arguments @($mestrePy)
    }
    "Full" {
        Write-Host "Etapa 1/4: comunicação e identificação, OUTPUT OFF"
        Invoke-CheckedPython -Arguments @($preflightPy)

        Write-Host "Etapa 2/4: aquisição forçada do Keysight, OUTPUT OFF (BNC ainda não testado)"
        Invoke-CheckedPython -Arguments @($preflightPy, "--trigger-test")

        $confirmation = Read-Host "Confirme probe, cabos, E-stop e EUT. Digite ENERGIZAR"
        if ($confirmation -cne "ENERGIZAR") {
            throw "Execução cancelada sem energização."
        }
        $env:ARM_OUTPUT = "YES"
        Write-Host "Etapa 3/4: validação automática em baixa tensão (5 Vrms)"
        Invoke-CheckedPython -Arguments @($preflightPy, "--low-voltage")

        Write-Host "Etapa 4/4: uma captura de cada uma das 20 classes"
        $env:REAL_CAPTURES_PER_CLASS = "1"
        Invoke-CheckedPython -Arguments @($mestrePy)
    }
}

Write-Host "Execução concluída. Confirme OUTPUT OFF no painel."
Write-Host "Log: $log"
