# setup_scheduler_windows.ps1
#
# Registers data_collector/scheduler.py as a Windows Task Scheduler task that
# runs at 12:00 and 21:00 every day.
#
# Requirements:
#   - Run as Administrator (the script requests elevation automatically)
#   - Python must be on PATH or the path below must be adjusted
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\setup_scheduler_windows.ps1

#Requires -Version 5.1

# ---------------------------------------------------------------------------
# Self-elevate to Administrator if not already running elevated
# ---------------------------------------------------------------------------
if (-not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "Restarting as Administrator..." -ForegroundColor Yellow
    Start-Process -FilePath "powershell.exe" `
        -ArgumentList "-ExecutionPolicy Bypass -File `"$PSCommandPath`"" `
        -Verb RunAs
    exit
}

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
$TaskName     = "SocialMediaAnalysis_Scheduler"
$ProjectRoot  = Split-Path -Parent $PSScriptRoot           # parent of scripts/
$SchedulerScript = Join-Path $ProjectRoot "data_collector\scheduler.py"

# Locate Python executable
$PythonExe = $null
try {
    $PythonExe = (Get-Command python -ErrorAction Stop).Source
    Write-Host "Found Python: $PythonExe" -ForegroundColor Cyan
} catch {
    # Fallback: common install locations
    $candidates = @(
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python39\python.exe",
        "C:\Python311\python.exe",
        "C:\Python310\python.exe",
        "C:\Python39\python.exe"
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) {
            $PythonExe = $c
            Write-Host "Found Python (fallback): $PythonExe" -ForegroundColor Cyan
            break
        }
    }
}

if (-not $PythonExe) {
    Write-Host "ERROR: Could not find python.exe. Please install Python or set it on PATH." -ForegroundColor Red
    exit 1
}

# Validate scheduler script
if (-not (Test-Path $SchedulerScript)) {
    Write-Host "ERROR: Scheduler script not found at: $SchedulerScript" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Task name    : $TaskName"         -ForegroundColor Cyan
Write-Host "Python       : $PythonExe"        -ForegroundColor Cyan
Write-Host "Script       : $SchedulerScript"  -ForegroundColor Cyan
Write-Host "Working dir  : $ProjectRoot"      -ForegroundColor Cyan
Write-Host ""

# ---------------------------------------------------------------------------
# Remove existing task if present
# ---------------------------------------------------------------------------
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Removing existing task '$TaskName'..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# ---------------------------------------------------------------------------
# Build task components
# ---------------------------------------------------------------------------
$action = New-ScheduledTaskAction `
    -Execute $PythonExe `
    -Argument "`"$SchedulerScript`"" `
    -WorkingDirectory $ProjectRoot

# 12:00 daily
$trigger1 = New-ScheduledTaskTrigger -Daily -At "12:00PM"

# 21:00 daily
$trigger2 = New-ScheduledTaskTrigger -Daily -At "9:00PM"

$settings = New-ScheduledTaskSettingsSet `
    -WakeToRun `
    -RunOnlyIfNetworkAvailable:$false `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 6) `
    -MultipleInstances IgnoreNew

# Run as SYSTEM with highest privileges so it works even when no user is
# logged in and the screen is off.
$principal = New-ScheduledTaskPrincipal `
    -UserId "SYSTEM" `
    -RunLevel Highest

# ---------------------------------------------------------------------------
# Register the task
# ---------------------------------------------------------------------------
try {
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $action `
        -Trigger @($trigger1, $trigger2) `
        -Settings $settings `
        -Principal $principal `
        -Description "Social Media Analysis Platform: run scheduler.py at 12:00 and 21:00 daily." `
        -Force | Out-Null

    Write-Host ""
    Write-Host "SUCCESS: Task '$TaskName' registered." -ForegroundColor Green
    Write-Host "  Runs at: 12:00 and 21:00 every day"
    Write-Host "  Wakes computer from sleep: Yes"
    Write-Host "  Runs even when not logged in: Yes (SYSTEM account)"
    Write-Host ""
    Write-Host "To verify:" -ForegroundColor Cyan
    Write-Host "  Get-ScheduledTask -TaskName '$TaskName' | Select-Object TaskName, State"
    Write-Host ""
    Write-Host "To remove:"  -ForegroundColor Cyan
    Write-Host "  Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false"

} catch {
    Write-Host ""
    Write-Host "ERROR: Failed to register task." -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
