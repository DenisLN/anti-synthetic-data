$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path $PSScriptRoot -Parent
Set-Location $ProjectRoot

$destination = Join-Path (Split-Path $ProjectRoot -Parent) "tcc-instrumentacao-bancada.zip"
$items = Get-ChildItem -Force | Where-Object {
    $_.Name -notin @("env", ".venv", "__pycache__", "resultados", "logs", "backups", ".git")
}
if (Test-Path $destination) {
    Remove-Item $destination
}
Compress-Archive -Path $items.FullName -DestinationPath $destination -CompressionLevel Optimal
Write-Host "Pacote criado: $destination"

