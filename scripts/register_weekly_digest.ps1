# Register the weekly digest as a Windows Scheduled Task.
# Run from PowerShell (admin not required for user-scoped tasks).

$RepoPath = "C:\Users\micha\best-practices"
$ScriptPath = "$RepoPath\scripts\run_weekly_digest.sh"
$LogPath = "$RepoPath\logs"
$TaskName = "CC-WeeklyDigest"

if (-not (Test-Path $LogPath)) {
    New-Item -ItemType Directory -Path $LogPath | Out-Null
}

# Invoke the .cmd wrapper directly — avoids nested-quote breakage when
# powershell.exe -Command parses a wsl bash command with embedded redirects.
# Wrapper at scripts/run_weekly_digest.cmd does the wsl call.
$Action = New-ScheduledTaskAction -Execute "$RepoPath\scripts\run_weekly_digest.cmd" -WorkingDirectory $RepoPath

# Friday 6:00 PM local time (must match the live CC-WeeklyDigest trigger —
# this script is the machine-rebuild recovery path)
$Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Friday -At 6:00PM

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -WakeToRun `
    -RunOnlyIfNetworkAvailable `
    -RestartCount 2 `
    -RestartInterval (New-TimeSpan -Minutes 15) `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

# StartWhenAvailable: if the machine is off Friday 6pm, run as soon as it wakes up.
#
# WakeToRun + RestartCount/RestartInterval added 2026-08-17, after the 8/15 run died 104
# seconds in with exit 0xC000013A. The cause was not the code: the machine booted at
# 06:33:36, the missed Friday trigger fired 5 seconds later as a catch-up, and a Start-menu
# restart at 06:35:24 tore down the WSL VM mid-run. It died inside the FIRST of three
# digests, so that week produced nothing at all, and nothing retried.
#
# Both settings target that shape. WakeToRun makes the Friday trigger actually fire instead
# of deferring to the next wake — a catch-up run lands in the first minutes after a lid-open,
# which is exactly when a restart or a sleep is most likely. RestartCount gives a killed run
# two more attempts rather than costing a full week of digests.
#
# ⚠️ Still unsolved: the principal is InteractiveToken, so this cannot run logged out or
# powered off. Switching it would break the wsl call, which needs a user session to reach the
# distro and its credential stores.

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "Weekly RSS digest: 3 contexts -> emails + GH issues in crumbl-ops, command-center, wealth-mgmt" `
    -Force

Write-Host "Registered scheduled task: $TaskName"
Write-Host "Logs: $LogPath\weekly_digest.log"
Write-Host ""
Write-Host "Test manually: schtasks /Run /TN $TaskName"
Write-Host "Unregister:    Unregister-ScheduledTask -TaskName $TaskName -Confirm:`$false"
