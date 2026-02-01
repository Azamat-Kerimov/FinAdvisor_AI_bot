# Сборка фронта и запуск API (React + FastAPI)
# Используйте для проверки сайта локально или перед деплоем

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

if (-not (Test-Path ".env")) {
    Write-Host "Файл .env не найден. Скопируйте .env.example в .env и заполните." -ForegroundColor Red
    exit 1
}

Write-Host "Сборка фронта..." -ForegroundColor Cyan
& (Join-Path $PSScriptRoot "build_frontend.ps1")
if ($LASTEXITCODE -ne 0) { exit 1 }

Write-Host "Запуск API на http://0.0.0.0:8000" -ForegroundColor Cyan
python -m uvicorn api:app --host 0.0.0.0 --port 8000
