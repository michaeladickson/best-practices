# Register the weekly digest as a Windows Scheduled Task.
# Run from PowerShell (admin not required for user-scoped tasks).

$RepoPath = "C:\Users\micha\best-practices"
$ScriptPath = "$RepoPath\scripts\run_weekly_digest.sh"
$LogPath = "$RepoPath\logs"
$TaskName = "CC-WeeklyDigest"

if (-not (Test-Path $LogPath)) {
    New-Item -ItemType Directory -Path $LogPath | Out-Null
}

# Use WSL bash to run the shell script
$WslCommand = "wsl -- bash -c `"cd /mnt/c/Users/micha/best-practices && bash scripts/run_weekly_digest.sh >> /mnt/c/Users/micha/best-practices/logs/weekly_digest.log 2>&1`""

$Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -WindowStyle Hidden -Command `"$WslCommand`""

# Sunday 6:00 PM local time
$Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 6:00PM

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

# StartWhenAvailable: if machine is off Sunday 6pm, runs as soon as it wakes up

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
