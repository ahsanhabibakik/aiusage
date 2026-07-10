# One-line installer for aiusage-tracker on Windows.
#   irm https://raw.githubusercontent.com/ahsanhabibakik/aiusage/main/scripts/install.ps1 | iex
#
# Tiered like install.sh: with Python 3.9+ it installs into an isolated
# venv; without Python it downloads the self-contained aiusage.exe from
# GitHub Releases (no runtime needed). Then wires Claude Code's statusLine,
# adds a Startup shortcut, and launches the tray. Safe to re-run; idempotent.
$ErrorActionPreference = "Stop"

$Repo = "ahsanhabibakik/aiusage"
$InstallDir = Join-Path $env:LOCALAPPDATA "aiusage-tracker"
$BinDir = Join-Path $InstallDir "bin"
New-Item -ItemType Directory -Force -Path $BinDir | Out-Null

function Get-PythonCmd {
    foreach ($cmd in @("python", "python3", "py")) {
        try {
            $v = & $cmd -c "import sys; print('{}.{}'.format(*sys.version_info[:2])); sys.exit(0 if sys.version_info >= (3,9) else 1)" 2>$null
            if ($LASTEXITCODE -eq 0) { return $cmd }
        } catch {}
    }
    return $null
}

$py = Get-PythonCmd
$AiusageExe = $null

if ($py) {
    Write-Host "aiusage-tracker: Python found -- installing to venv at $InstallDir"
    $VenvDir = Join-Path $InstallDir "venv"
    & $py -m venv $VenvDir
    $pip = Join-Path $VenvDir "Scripts\pip.exe"
    & $pip install --quiet --upgrade aiusage-tracker 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "aiusage-tracker: PyPI install failed, falling back to GitHub source"
        & $pip install --quiet --upgrade "git+https://github.com/$Repo.git"
    }
    $AiusageExe = Join-Path $VenvDir "Scripts\aiusage.exe"
} else {
    Write-Host "aiusage-tracker: no Python 3.9+ found -- downloading standalone binary"
    $AiusageExe = Join-Path $BinDir "aiusage.exe"
    $url = "https://github.com/$Repo/releases/latest/download/aiusage-windows-x86_64.exe"
    Invoke-WebRequest -Uri $url -OutFile "$AiusageExe.tmp" -UseBasicParsing
    Move-Item -Force "$AiusageExe.tmp" $AiusageExe
}

# Make `aiusage` available on PATH via a shim in a user-PATH directory.
if (-not (($env:Path -split ";") -contains $BinDir)) {
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if (-not (($userPath -split ";") -contains $BinDir)) {
        [Environment]::SetEnvironmentVariable("Path", "$userPath;$BinDir", "User")
    }
}
$shim = Join-Path $BinDir "aiusage.cmd"
"@echo off`r`n`"$AiusageExe`" %*" | Set-Content -Path $shim -Encoding ascii

# Wire Claude Code's statusLine + let the package's own setup handle the rest.
& $AiusageExe setup

# Startup shortcut so the tray survives reboots.
$startup = [Environment]::GetFolderPath("Startup")
$ws = New-Object -ComObject WScript.Shell
$lnk = $ws.CreateShortcut((Join-Path $startup "aiusage.lnk"))
$lnk.TargetPath = $AiusageExe
$lnk.Arguments = "tray"
$lnk.WindowStyle = 7  # minimized
$lnk.Save()
Write-Host "aiusage-tracker: Startup shortcut added"

# Launch now if not already running.
$running = Get-Process | Where-Object { $_.Path -eq $AiusageExe } 2>$null
if (-not $running) {
    Start-Process -FilePath $AiusageExe -ArgumentList "tray" -WindowStyle Hidden
    Write-Host "aiusage-tracker: tray launched"
}

Write-Host ""
Write-Host "Done. Tray icon running, Claude Code statusLine wired, Startup entry set."
Write-Host "Open a NEW Claude Code session to see the status bar (don't run /statusline --"
Write-Host "that's Claude Code's own config wizard and will overwrite this)."
Write-Host "Update any time with:  aiusage update"
