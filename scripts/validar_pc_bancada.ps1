# P-16: roda a suite OFFLINE no PC Windows da bancada e grava a evidencia
# (docs\evidencias\<data>\pc_bancada.json + pc_bancada.log).
#
# Nao toca instrumento algum: so `unittest discover` (tests\ nao abre VISA),
# `git` e consultas de versao. Recusa sobrescrever evidencia existente.
# Uso (PowerShell, na raiz do projeto, depois de scripts\setup_windows.ps1):
#     .\scripts\validar_pc_bancada.ps1
# Depois: python scripts\fechar_pendencias.py --sessao <dir> --pc-bancada docs\evidencias\<data>\pc_bancada.json --saida <novo.json>
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path $PSScriptRoot -Parent
Set-Location $ProjectRoot
$utf8 = New-Object System.Text.UTF8Encoding($false)
[Console]::InputEncoding = $utf8
[Console]::OutputEncoding = $utf8
$OutputEncoding = $utf8
$env:PYTHONUTF8 = "1"

$python = Join-Path $ProjectRoot "env\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "env\Scripts\python.exe ausente. Rode scripts\setup_windows.ps1 antes."
}

$data = Get-Date -Format "yyyy-MM-dd"
$pasta = Join-Path $ProjectRoot (Join-Path "docs\evidencias" $data)
$destinoJson = Join-Path $pasta "pc_bancada.json"
$destinoLog = Join-Path $pasta "pc_bancada.log"
if ((Test-Path $destinoJson) -or (Test-Path $destinoLog)) {
    throw "Ja existe $destinoJson ou $destinoLog; nao sobrescrevo evidencia. Mova-os ou rode em outra data."
}
New-Item -ItemType Directory -Force -Path $pasta | Out-Null

function Invoke-Capturando([string[]]$Argumentos) {
    # Native command com stderr: em PS 5.1 + Stop vira excecao; relaxa so aqui.
    $anterior = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $saida = & $python @Argumentos 2>&1 | ForEach-Object { "$_" }
        return @{ Saida = @($saida); Codigo = $LASTEXITCODE }
    }
    finally { $ErrorActionPreference = $anterior }
}

function Invoke-Git([string[]]$Argumentos) {
    # Sem git no PATH: codigo 127, nunca herda $LASTEXITCODE de outro comando.
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        return @{ Saida = @(); Codigo = 127 }
    }
    $anterior = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $global:LASTEXITCODE = 0
    try {
        $saida = & git @Argumentos 2>&1 | ForEach-Object { "$_" }
        return @{ Saida = @($saida); Codigo = $LASTEXITCODE }
    }
    finally { $ErrorActionPreference = $anterior }
}

# Contrato com scripts/fechar_pendencias.py (P-16): valor que comeca com "indisponivel"
# NAO conta como versao registrada.
$versoesCodigo = @'
import importlib.metadata as m, json, platform, sys
def v(n):
    try:
        return m.version(n)
    except Exception as exc:
        return "indisponivel: %s" % exc
print(json.dumps({"python": sys.version, "python_executavel": sys.executable,
                  "numpy": v("numpy"), "pymeasure": v("PyMeasure"), "pyvisa": v("PyVISA"),
                  "plataforma": platform.platform(), "sistema": platform.system()}))
'@
# Arquivo temporario em vez de "-c": o PowerShell 5.1 nao escapa aspas duplas
# internas ao passar argumentos a programas nativos, e o codigo chegaria truncado.
$versoesPy = Join-Path ([IO.Path]::GetTempPath()) ("asd_versoes_{0}.py" -f [guid]::NewGuid())
[IO.File]::WriteAllText($versoesPy, $versoesCodigo, (New-Object System.Text.UTF8Encoding($false)))
try { $versoes = Invoke-Capturando @($versoesPy) }
finally { Remove-Item -Force -ErrorAction SilentlyContinue $versoesPy }
$infoVersoes = $null
try { $infoVersoes = ($versoes.Saida -join "`n") | ConvertFrom-Json } catch { $infoVersoes = $null }

$commit = Invoke-Git @("rev-parse", "HEAD")
# Mesma regra de logica/mestre.py::info_do_codigo: sujo = alteracao em arquivo RASTREADO
# (qualquer pasta) ou arquivo novo nao ignorado em logica/, experimentos_nativos/,
# experimentos_waveform/ e scripts/. Arquivo novo em docs/ etc. nao conta.
$status = Invoke-Git @("status", "--short", "--untracked-files=no")
$novos = Invoke-Git @("ls-files", "--others", "--exclude-standard", "--", "logica", "experimentos_nativos", "experimentos_waveform", "scripts")
$gitSujo = $null
if ($status.Codigo -eq 0 -and $novos.Codigo -eq 0) {
    $gitSujo = ((@($status.Saida | Where-Object { $_.Trim() }).Count -gt 0) -or (@($novos.Saida | Where-Object { $_.Trim() }).Count -gt 0))
}

$inicio = Get-Date
$teste = Invoke-Capturando @("-m", "unittest", "discover", "-s", "tests", "-p", "test*.py", "-v")
$fim = Get-Date
[System.IO.File]::WriteAllText($destinoLog, (($teste.Saida -join "`r`n") + "`r`n"), $utf8)

# Ancorado no resumo FINAL do unittest ("Ran N tests in Xs", linha em branco e
# "OK ..." / "FAILED (...)" como ultima linha nao vazia); linhas de teste do -v
# que contenham "OK" ou "FAILED" no meio nao contam.
$linhas = @($teste.Saida | ForEach-Object { "$_".TrimEnd() } | Where-Object { $_ -ne "" })
$executados = $null
$falhas = 0; $erros = 0; $skips = 0
$ultima = if ($linhas.Count -gt 0) { $linhas[$linhas.Count - 1] } else { "" }
$idxRan = -1
for ($i = $linhas.Count - 1; $i -ge 0; $i--) {
    if ($linhas[$i] -match "^Ran (\d+) tests? in ([0-9.]+)s$") { $executados = [int]$Matches[1]; $idxRan = $i; break }
}
if ($idxRan -ge 0) {
    $resumoFinal = ($linhas[($idxRan + 1)..($linhas.Count - 1)] | Select-Object -Last 1)
    if ($resumoFinal -match "^FAILED \((.*)\)$") {
        $detalhe = $Matches[1]
        if ($detalhe -match "failures=(\d+)") { $falhas = [int]$Matches[1] }
        if ($detalhe -match "errors=(\d+)") { $erros = [int]$Matches[1] }
        if ($detalhe -match "skipped=(\d+)") { $skips = [int]$Matches[1] }
    }
    elseif ($resumoFinal -match "^OK(?: \((.*)\))?$") {
        if ($Matches[1] -and $Matches[1] -match "skipped=(\d+)") { $skips = [int]$Matches[1] }
    }
}
$logHash = (Get-FileHash -Algorithm SHA256 -Path $destinoLog).Hash.ToLower()

$resultado = [ordered]@{
    esquema          = 1
    gerado_em        = (Get-Date).ToString("o")
    ferramenta       = "scripts/validar_pc_bancada.ps1"
    hostname         = $env:COMPUTERNAME
    usuario          = $env:USERNAME
    sistema          = $infoVersoes.sistema
    plataforma       = $infoVersoes.plataforma
    python           = $infoVersoes.python
    python_executavel = $infoVersoes.python_executavel
    numpy            = $infoVersoes.numpy
    pymeasure        = $infoVersoes.pymeasure
    pyvisa           = $infoVersoes.pyvisa
    git_commit       = $(if ($commit.Codigo -eq 0) { ($commit.Saida -join "").Trim() } else { $null })
    git_status_short = @($status.Saida | Where-Object { $_.Trim() })
    git_sujo         = $gitSujo
    comando          = '.\env\Scripts\python.exe -m unittest discover -s tests -p "test*.py" -v'
    codigo_saida     = $teste.Codigo
    testes_executados = $executados
    falhas           = $falhas
    erros            = $erros
    skips            = $skips
    duracao_s        = [math]::Round(($fim - $inicio).TotalSeconds, 3)
    log              = "pc_bancada.log"
    log_sha256       = $logHash
}
$json = $resultado | ConvertTo-Json -Depth 5
[System.IO.File]::WriteAllText($destinoJson, $json + "`r`n", $utf8)

Write-Host ""
Write-Host "Testes: $executados | falhas: $falhas | erros: $erros | skips: $skips | codigo de saida: $($teste.Codigo)"
Write-Host "Evidencia: $destinoJson"
Write-Host "Log:       $destinoLog"
if ($teste.Codigo -ne 0) {
    Write-Host "A suite FALHOU: a evidencia foi gravada mesmo assim, mas P-16 nao fecha."
    exit 1
}
if ($gitSujo) { Write-Host "AVISO: arvore git suja; commite antes de usar esta evidencia." }
