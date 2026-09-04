# LocalConvert - Windows Uninstall Script
# Run from PowerShell:
#   powershell -ExecutionPolicy Bypass -File uninstall.ps1

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvDir = Join-Path $ScriptDir "venv"

function Write-Step($msg) {
    Write-Host ""
    Write-Host "=== $msg ===" -ForegroundColor Green
    Write-Host ""
}

function Write-OK($msg)  { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "  [!]  $msg" -ForegroundColor Yellow }
function Write-Info($msg) { Write-Host "  [*]  $msg" -ForegroundColor Cyan }

Write-Host ""
Write-Warn "This will remove the Python virtual environment."
Write-Warn "It will NOT auto-uninstall system tools (LibreOffice, Pandoc, etc.)"
Write-Warn "  -- use Windows Settings > Apps to remove those manually."
Write-Host ""
$yn = Read-Host "  Continue? [y/N]"
if ($yn -notmatch '^[yY]') {
    Write-Info "Aborted."
    exit 0
}

Write-Step "1/1  Python virtual environment"
if (Test-Path $VenvDir) {
    Write-Info "Removing $VenvDir ..."
    Remove-Item -Recurse -Force $VenvDir
    Write-OK "Virtual environment removed"
} else {
    Write-OK "No virtual environment found"
}

Write-Host ""
Write-OK "Done."
Write-Info "Config folder left untouched -- remove manually if desired."
Write-Info "Docker output/config folders left untouched."
