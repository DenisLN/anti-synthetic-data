$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$destination = Join-Path (Split-Path $PSScriptRoot -Parent) "tcc-instrumentacao-bancada.zip"
$items = Get-ChildItem -Force | Where-Object {
    $_.Name -notin @("env", ".venv", "__pycache__", "resultados", "logs", "backups", ".git")
}
if (Test-Path $destination) {
    Remove-Item $destination
}
Compress-Archive -Path $items.FullName -DestinationPath $destination -CompressionLevel Optimal
Write-Host "Pacote criado: $destination"

