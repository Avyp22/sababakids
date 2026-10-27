# Refreshes the Holon events snapshot from a computer in Israel.
# holon.muni.il only answers Israeli IPs, so neither Render nor GitHub Actions can
# fetch it; without this the snapshot goes stale and check-event-sources fails.
#
# Run by hand:   powershell -ExecutionPolicy Bypass -File backend\refresh_holon.ps1
# Or daily via Windows Task Scheduler (see DEPLOIEMENT.md).
#
# Uses its own folder in %LOCALAPPDATA%\sababakids (Python venv + a clone of the
# `event-data` branch) and pushes with your usual git credentials.
$ErrorActionPreference = "Stop"

$Repo = Split-Path -Parent $PSScriptRoot
$Home_ = Join-Path $env:LOCALAPPDATA "sababakids"
$Venv = Join-Path $Home_ "venv"
$Data = Join-Path $Home_ "event-data"
$Py = Join-Path $Venv "Scripts\python.exe"
$Log = Join-Path $Home_ "refresh_holon.log"

New-Item -ItemType Directory -Force $Home_ | Out-Null
Start-Transcript -Path $Log -Append | Out-Null
try {
    if (-not (Test-Path $Py)) {
        python -m venv $Venv
        & $Py -m pip install -q httpx==0.28.1 beautifulsoup4==4.15.0 lxml==6.1.3 tzdata
    }

    if (-not (Test-Path (Join-Path $Data ".git"))) {
        git clone -q --branch event-data --single-branch https://github.com/Avyp22/sababakids.git $Data
    }
    git -C $Data pull -q --rebase origin event-data

    Push-Location (Join-Path $Repo "backend")
    try { & $Py snapshot_events.py --out $Data holon } finally { Pop-Location }

    git -C $Data add -A
    git -C $Data diff --cached --quiet
    if ($LASTEXITCODE -ne 0) {
        git -C $Data commit -q -m "Holon snapshot from a computer in Israel"
        git -C $Data pull -q --rebase origin event-data   # the GitHub job may have pushed meanwhile
        git -C $Data push -q origin event-data
        Write-Output "Holon snapshot published."
    } else {
        Write-Output "No change."
    }
} finally {
    Stop-Transcript | Out-Null
}
