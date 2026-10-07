# Runner script to capture screenshots of all Ketrika web routes for T7.2 documentation
param (
    [string]$BaseUrl = "http://localhost:3005"
)

$ScriptPath = Join-Path $PSScriptRoot "capture_all_screenshots.mjs"
if (Test-Path $ScriptPath) {
    node $ScriptPath
} else {
    Write-Error "capture_all_screenshots.mjs not found."
}
