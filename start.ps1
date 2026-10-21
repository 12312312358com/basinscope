$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
$env:HOST = if ($env:HOST) { $env:HOST } else { "127.0.0.1" }
$env:PORT = if ($env:PORT) { $env:PORT } else { "5001" }
$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) { $python = "python" }
Write-Host "BasinScope: http://$env:HOST`:$env:PORT"
& $python "app.py"
