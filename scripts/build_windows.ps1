$ErrorActionPreference = "Stop"

function Write-Step($Message) {
    Write-Host "[GVC BUILD] $Message" -ForegroundColor Cyan
}

function Fail($Message) {
    Write-Host "[GVC BUILD] ERROR: $Message" -ForegroundColor Red
    throw $Message
}

function Pause-IfInteractive {
    if ($env:CI -eq "true") { return }
    if ($Host.Name -ne "ConsoleHost") { return }
    Write-Host ""
    Read-Host "Press Enter to close"
}

try {
    $root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
    Set-Location $root
    Write-Step "Project root: $root"

    if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
        Fail "Python was not found in PATH. Install Python 3.11+ and reopen PowerShell."
    }
    Write-Step "Python detected."

    if (!(Test-Path "bin/ffmpeg.exe")) {
        Fail "Missing file: bin/ffmpeg.exe"
    }
    if (!(Test-Path "bin/ffprobe.exe")) {
        Fail "Missing file: bin/ffprobe.exe"
    }
    Write-Step "FFmpeg binaries found in ./bin."

    Write-Step "Installing build dependencies..."
    & python -m pip install -e ".[build]"
    if ($LASTEXITCODE -ne 0) {
        Fail "Failed installing project with pip install -e .[build]"
    }

    Write-Step "Running PyInstaller (GUI mode)..."
    & python -m PyInstaller `
      --noconfirm `
      --clean `
      --distpath dist `
      --workpath .pyinstaller/build `
      gvc.spec
    if ($LASTEXITCODE -ne 0) {
        Fail "PyInstaller failed. Check the messages above for details."
    }

    if (!(Test-Path "dist/gvc/gvc.exe")) {
        Fail "Build finished but dist/gvc/gvc.exe was not found."
    }

    Write-Host ""
    Write-Host "[GVC BUILD] Build completed successfully." -ForegroundColor Green
    Write-Host "[GVC BUILD] Output: dist/gvc/" -ForegroundColor Green
    Write-Host "[GVC BUILD] Temporary PyInstaller files: .pyinstaller/build/" -ForegroundColor DarkGray
    Write-Host "[GVC BUILD] Run with: .\\dist\\gvc\\gvc.exe" -ForegroundColor Green
}
catch {
    Write-Host ""
    Write-Host "[GVC BUILD] Build failed." -ForegroundColor Red
    Write-Host "[GVC BUILD] Details: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "[GVC BUILD] Tip: run this script from a PowerShell terminal to keep messages visible." -ForegroundColor Yellow
}
finally {
    Pause-IfInteractive
}
