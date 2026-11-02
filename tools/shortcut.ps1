# Make the "Morning receipt" shortcut on the Desktop and in the Start menu.
#
# Both run tools/morning.ps1, which prints today's receipt. Re-run this after
# moving the repo; delete the two .lnk files to get rid of them.

$root = Split-Path -Parent $PSScriptRoot
$script = Join-Path $root "tools\morning.ps1"
$shell = New-Object -ComObject WScript.Shell

$places = @(
    [Environment]::GetFolderPath("Desktop"),
    (Join-Path ([Environment]::GetFolderPath("StartMenu")) "Programs")
)
foreach ($dir in $places) {
    $path = Join-Path $dir "Morning receipt.lnk"
    $lnk = $shell.CreateShortcut($path)
    $lnk.TargetPath = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
    $lnk.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$script`""
    $lnk.WorkingDirectory = $root
    $lnk.IconLocation = "$env:SystemRoot\System32\shell32.dll,16"   # the printer
    $lnk.Description = "Print this morning's receipt (quick-guthe)"
    $lnk.Save()
    Write-Host "made $path"
}
