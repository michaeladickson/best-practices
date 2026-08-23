# Register the independent heartbeat check as a Windows Scheduled Task.
# Tuesday 9am — deliberately a different day from everything it watches, so the
# watcher does not share a fate with the watched (the digest wrapper also runs
# the same check Fridays; this entry exists for when the digest task itself dies).
# Run from PowerShell (admin not required for user-scoped tasks).

$RepoPath = "C:\Users\micha\best-practices"
$TaskName = "CC-Heartbeats"

if (-not (Test-Path "$RepoPath\logs")) {
    New-Item -ItemType Directory -Path "$RepoPath\logs" | Out-Null
}

$Action = New-ScheduledTaskAction -Execute "$RepoPath\scripts\check_heartbeats.cmd" -WorkingDirectory $RepoPath

$Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Tuesday -At 9:00AM

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "Independent dead-man's check for scheduled jobs (see AUTOMATION.md); files a GitHub issue on staleness" `
    -Force

Write-Host "Registered scheduled task: $TaskName"
Write-Host "Test manually: schtasks /Run /TN $TaskName"
Write-Host "Unregister:    Unregister-ScheduledTask -TaskName $TaskName -Confirm:`$false"
