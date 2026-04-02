$ErrorActionPreference = "Stop"

$RepoOwner = if ($env:REPO_OWNER) { $env:REPO_OWNER } else { "redpersongpt" }
$RepoName = if ($env:REPO_NAME) { $env:REPO_NAME } else { "cashcrab" }
$CashCrabRef = if ($env:CASHCRAB_REF) { $env:CASHCRAB_REF } else { "main" }
$InstallRoot = if ($env:CASHCRAB_HOME) { $env:CASHCRAB_HOME } else { Join-Path $env:LOCALAPPDATA "CashCrab" }
$BinDir = if ($env:CASHCRAB_BIN_DIR) { $env:CASHCRAB_BIN_DIR } else { Join-Path $InstallRoot "bin" }
$VenvDir = Join-Path $InstallRoot "venv"
$SourceDir = Join-Path $InstallRoot "source"
$ArchiveUrl = "https://github.com/$RepoOwner/$RepoName/archive/refs/heads/$CashCrabRef.zip"

function Say([string]$Message) {
    Write-Host $Message
}

function Step([string]$Message) {
    Write-Host ""
    Write-Host "==> $Message"
}

function Banner {
    Write-Host "  ____           __    ______           __"
    Write-Host " / ___|__ _ ___ / /_  / ____/________ _/ /_"
    Write-Host "/ /__/ _` / __// __ \/ /   / ___/ __ `/ __ \"
    Write-Host "\___/\__,_/\__/ \____/_/   /_/   \__,_/\__/"
    Write-Host ""
    Write-Host "CashCrab installer"
}

function Install-PythonIfMissing {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        return
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        return
    }

    Step "Python 3 not found. Trying to install it"

    if (Get-Command winget -ErrorAction SilentlyContinue) {
        winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
        return
    }

    throw "Python 3 is missing and winget was not found. Install Python 3 first, then rerun this command."
}

function Get-PythonCommand {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        return @("py", "-3")
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        return @("python")
    }
    throw "Python 3 is still not available in PATH."
}

function Add-ToUserPath {
    param([string]$PathToAdd)

    $current = [Environment]::GetEnvironmentVariable("Path", "User")
    $parts = @()
    if ($current) {
        $parts = $current.Split(";") | Where-Object { $_ }
    }

    if ($parts -notcontains $PathToAdd) {
        $newPath = ($parts + $PathToAdd) -join ";"
        [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
        Say "Added to user PATH: $PathToAdd"
    }
}

Banner
Step "Checking installer dependencies"
Install-PythonIfMissing

$python = Get-PythonCommand
$pythonArgs = @()
if ($python.Length -gt 1) {
    $pythonArgs = $python[1..($python.Length - 1)]
}

$tempDir = Join-Path ([System.IO.Path]::GetTempPath()) ("cashcrab-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $tempDir | Out-Null

try {
    Step "Downloading CashCrab"
    $zipPath = Join-Path $tempDir "cashcrab.zip"
    Invoke-WebRequest -Uri $ArchiveUrl -OutFile $zipPath
    Expand-Archive -Path $zipPath -DestinationPath $tempDir -Force

    $extracted = Join-Path $tempDir "$RepoName-$CashCrabRef"
    if (-not (Test-Path $extracted)) {
        throw "Could not find extracted source directory: $extracted"
    }

    New-Item -ItemType Directory -Force -Path $InstallRoot, $BinDir | Out-Null
    if (Test-Path $SourceDir) {
        Remove-Item -Recurse -Force $SourceDir
    }
    Copy-Item -Recurse -Force $extracted $SourceDir

    Step "Creating private environment"
    & $python[0] @pythonArgs -m venv $VenvDir

    $pip = Join-Path $VenvDir "Scripts\pip.exe"
    $cashcrabExe = Join-Path $VenvDir "Scripts\cashcrab.exe"

    Step "Installing app dependencies"
    & $pip install --upgrade pip setuptools wheel | Out-Null
    & $pip install $SourceDir | Out-Null

    $cmdLauncher = @"
@echo off
"$cashcrabExe" %*
"@
    Set-Content -Path (Join-Path $BinDir "cashcrab.cmd") -Value $cmdLauncher -Encoding ASCII

    $psLauncher = @"
& "$cashcrabExe" @args
"@
    Set-Content -Path (Join-Path $BinDir "cashcrab.ps1") -Value $psLauncher -Encoding ASCII

    Add-ToUserPath -PathToAdd $BinDir

    Step "Checking optional media tools"
    if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
        Say "ffmpeg: found"
    } else {
        Say "WARN: ffmpeg not found. Video generation may fail until you install it."
    }

    if ((Get-Command magick -ErrorAction SilentlyContinue) -or (Get-Command convert -ErrorAction SilentlyContinue)) {
        Say "ImageMagick: found"
    } else {
        Say "WARN: ImageMagick not found. Some MoviePy text or subtitle operations may need it."
    }

    Write-Host ""
    Write-Host "CashCrab is installed."
    Write-Host ""
    Write-Host "Command:"
    Write-Host "  cashcrab"
    Write-Host ""
    Write-Host "If the command is not found right away, restart PowerShell."
}
finally {
    if (Test-Path $tempDir) {
        Remove-Item -Recurse -Force $tempDir
    }
}
