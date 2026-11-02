# Print this morning's receipt, by hand.
#
# What the desktop shortcut runs (tools/shortcut.ps1 makes it). Runs main.py
# with the venv python - never a bare `python`, which may be another version -
# from the repo root, shows the run in the window and appends it, timestamped,
# to out/morning.log so a bad morning can be diagnosed after the window has
# gone.
#
# Any arguments pass straight through to main.py:
#   tools\morning.ps1 --dry-run
#   tools\morning.ps1 --preview --date 2026-12-21

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUNBUFFERED = "1"          # stream lines as they happen, not at exit
[Console]::OutputEncoding = [Text.Encoding]::UTF8

$python = Join-Path $root ".venv\Scripts\python.exe"
$log = Join-Path $root "out\morning.log"
New-Item -ItemType Directory -Force (Split-Path $log) | Out-Null

function Write-Log([string]$line) {
    Write-Host $line
    Add-Content -Path $log -Value $line -Encoding UTF8
}

$stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Write-Log ""
Write-Log "=== $stamp  main.py $($args -join ' ')"

if (-not (Test-Path $python)) {
    Write-Log "no venv python at $python - see README.md, Setup"
    $code = 1
} else {
    # 2>&1 so tracebacks reach the log too. PowerShell 5.1 wraps each stderr
    # line in an ErrorRecord; "$_" turns it back into the plain text.
    $ErrorActionPreference = "Continue"
    & $python main.py @args 2>&1 | ForEach-Object { Write-Log "$_" }
    $code = $LASTEXITCODE
}

Write-Log "=== exit $code  ($(Get-Date -Format 'HH:mm:ss'))"

# A good morning closes itself; a bad one stays up to be read.
if ($code -eq 0) {
    Start-Sleep -Seconds 5
} else {
    Write-Host ""
    Write-Host "Something went wrong - the full run is in out\morning.log." -ForegroundColor Red
    Read-Host "Press Enter to close"
}
exit $code
