# Weltrade Trading Terminal - PowerShell Dependency Installer
$ErrorActionPreference = "Stop"
$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Definition

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "   WELTRADE SYNTHETICS TRADING TERMINAL - FULL DEPENDENCY INSTALLER" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[1/4] Checking Python installation..." -ForegroundColor Yellow
python --version

Write-Host ""
Write-Host "[2/4] Checking Node.js & npm installation..." -ForegroundColor Yellow
node --version
npm.cmd --version

Write-Host ""
Write-Host "[3/4] Installing Backend Python packages (MetaTrader5, FastAPI, Uvicorn, Playwright)..." -ForegroundColor Yellow
Set-Location (Join-Path $RootDir "backend")
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

Write-Host ""
Write-Host "[3b/4] Installing Playwright Chromium for Weltrade Safe Vault automation..." -ForegroundColor Yellow
python -m playwright install chromium

Write-Host ""
Write-Host "[4/4] Installing Frontend Node.js packages (React, Lightweight Charts, Lucide, Vite)..." -ForegroundColor Yellow
Set-Location (Join-Path $RootDir "frontend")
npm.cmd install

Write-Host ""
Write-Host "[4b/4] Verifying Frontend build..." -ForegroundColor Yellow
npm.cmd run build

Set-Location $RootDir
Write-Host ""
Write-Host "============================================================================" -ForegroundColor Green
Write-Host "   INSTALLATION COMPLETE! Run .\start.bat to launch the app." -ForegroundColor Green
Write-Host "============================================================================" -ForegroundColor Green
