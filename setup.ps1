# LocalConvert - Windows Setup Script
# Run from PowerShell (not as Administrator unless needed):
#   powershell -ExecutionPolicy Bypass -File setup.ps1
#
# Or right-click setup.ps1 → "Run with PowerShell"

param(
    [switch]$Recreate
)

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
function Write-Err($msg)  { Write-Host "  [X]  $msg" -ForegroundColor Red }
function Write-Info($msg) { Write-Host "  [*]  $msg" -ForegroundColor Cyan }

# ── banner ─────────────────────────────────────────────────────────────

Write-Host @"
  LocalConvert Setup
  Install all dependencies automatically
"@ -ForegroundColor Cyan

# ── Python venv + pip packages ─────────────────────────────────────────

Write-Step "1/2  Python virtual environment"

$pythonCmd = $null
foreach ($cmd in @("python3", "python")) {
    $found = Get-Command $cmd -ErrorAction SilentlyContinue
    if ($found) {
        $ver = & $cmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
        if ($ver -as [version] -ge [version]"3.10") {
            $pythonCmd = $cmd
            break
        }
    }
}

if (-not $pythonCmd) {
    Write-Err "Python >= 3.10 not found. Install from https://www.python.org/downloads/"
    exit 1
}
Write-OK "Found: $pythonCmd ($(& $pythonCmd --version 2>&1))"

if ($Recreate -and (Test-Path $VenvDir)) {
    Write-Info "Removing existing venv..."
    Remove-Item -Recurse -Force $VenvDir
}

if (Test-Path $VenvDir) {
    Write-Info "Virtual environment already exists at $VenvDir"
    Write-Info "Use -Recreate to rebuild from scratch."
} else {
    Write-Info "Creating virtual environment..."
    & $pythonCmd -m venv $VenvDir
    Write-OK "Virtual environment created at $VenvDir"
}

$pipExe = Join-Path $VenvDir "Scripts" "pip.exe"
$pythonVenv = Join-Path $VenvDir "Scripts" "python.exe"

Write-Info "Upgrading pip..."
& $pythonVenv -m pip install --upgrade pip --quiet

Write-Info "Installing Python packages from requirements.txt..."
& $pipExe install -r (Join-Path $ScriptDir "requirements.txt")

Write-OK "Python packages installed"

# ── system tools ───────────────────────────────────────────────────────

Write-Step "2/2  System tools (LibreOffice, Pandoc, Calibre, FFmpeg, ...)"

$useWinget = Get-Command winget -ErrorAction SilentlyContinue
$useChoco  = Get-Command choco -ErrorAction SilentlyContinue

if (-not $useWinget -and -not $useChoco) {
    Write-Warn "No supported package manager found (winget or chocolatey)."
    Write-Warn "Install these tools manually:"
    Write-Host "  - LibreOffice  https://www.libreoffice.org/download/"
    Write-Host "  - Pandoc       https://pandoc.org/installing.html"
    Write-Host "  - Calibre      https://calibre-ebook.com/download"
    Write-Host "  - FFmpeg       https://ffmpeg.org/download.html"
    Write-Host "  - Tesseract    https://github.com/UB-Mannheim/tesseract/wiki"
    Write-Host "  - ImageMagick  https://imagemagick.org/script/download.php"
} elseif ($useWinget) {
    Write-Info "Using winget..."
    # LibreOffice
    if (-not (Get-Command soffice -ErrorAction SilentlyContinue)) {
        Write-Info "Installing LibreOffice..."
        winget install --id TheDocumentFoundation.LibreOffice --silent --accept-package-agreements --accept-source-agreements
    }
    # Pandoc
    if (-not (Get-Command pandoc -ErrorAction SilentlyContinue)) {
        Write-Info "Installing Pandoc..."
        winget install --id JohnMacFarlane.Pandoc --silent --accept-package-agreements --accept-source-agreements
    }
    # FFmpeg
    if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
        Write-Info "Installing FFmpeg..."
        winget install --id Gyan.FFmpeg --silent --accept-package-agreements --accept-source-agreements
    }
    # Calibre
    if (-not (Get-Command ebook-convert -ErrorAction SilentlyContinue)) {
        Write-Info "Installing Calibre..."
        winget install --id calibre.calibre --silent --accept-package-agreements --accept-source-agreements
    }
    # Tesseract
    if (-not (Get-Command tesseract -ErrorAction SilentlyContinue)) {
        Write-Info "Installing Tesseract..."
        winget install --id UB-Mannheim.TesseractOCR --silent --accept-package-agreements --accept-source-agreements
    }
    # ImageMagick
    if (-not (Get-Command magick -ErrorAction SilentlyContinue)) {
        Write-Info "Installing ImageMagick..."
        winget install --id ImageMagick.ImageMagick --silent --accept-package-agreements --accept-source-agreements
    }
    Write-OK "Winget packages processed"
} else {
    # chocolatey
    Write-Info "Using Chocolatey..."
    $pkgs = @()
    if (-not (Get-Command soffice -ErrorAction SilentlyContinue))       { $pkgs += "libreoffice-fresh" }
    if (-not (Get-Command pandoc -ErrorAction SilentlyContinue))        { $pkgs += "pandoc" }
    if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue))        { $pkgs += "ffmpeg" }
    if (-not (Get-Command tesseract -ErrorAction SilentlyContinue))      { $pkgs += "tesseract" }
    if (-not (Get-Command ebook-convert -ErrorAction SilentlyContinue))  { $pkgs += "calibre" }
    if (-not (Get-Command magick -ErrorAction SilentlyContinue))         { $pkgs += "imagemagick" }
    if ($pkgs.Count -gt 0) {
        choco install -y @pkgs
    }
    Write-OK "Chocolatey packages processed"
}

# ── verify ─────────────────────────────────────────────────────────────

Write-Step "Verification"

$allOk = $true

function Check-Tool($name) {
    if (Get-Command $name -ErrorAction SilentlyContinue) {
        Write-OK "$name"
    } else {
        Write-Warn "$name  (not found)"
        $script:allOk = $false
    }
}

Check-Tool soffice
Check-Tool pandoc
Check-Tool ffmpeg
Check-Tool ffprobe
Check-Tool tesseract
Check-Tool ebook-convert
Check-Tool magick

if (Test-Path $pythonVenv) {
    Write-OK "Python venv  ($VenvDir)"
} else {
    Write-Warn "Python venv  (missing)"
    $allOk = $false
}

Write-Host ""
if ($allOk) {
    Write-OK "All dependencies verified!"
} else {
    Write-Warn "Some dependencies are missing — see warnings above."
    Write-Info "Missing tools will disable their respective conversions."
}

# ── next steps ─────────────────────────────────────────────────────────

Write-Step "Ready"
Write-Host @"
  Activate the virtual environment and run LocalConvert:

    .\venv\Scripts\Activate.ps1
    python -m app.main

  Or run without activating first:

    .\venv\Scripts\python.exe -m app.main

  Or run the tests:

    .\venv\Scripts\Activate.ps1
    python -m pytest app/tests/ -q
"@