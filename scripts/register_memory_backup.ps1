# Register the daily Claude memory backup as a Windows Scheduled Task.
# Run from PowerShell (admin not required for user-scoped tasks).

$RepoPath   = "C:\Users\micha\best-practices"
$ScriptPath = "$RepoPath\scripts\backup_claude_memory.ps1"
$TaskName   = "CC-MemoryBackup"

$Action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptPath`""

# Daily 2:00 AM local time
$Trigger = New-ScheduledTaskTrigger -Daily -At 2:00AM
# New-ScheduledTaskTrigger writes the start with today's UTC offset, which pins the task
# to UTC: registered in daylight time, it fired an hour early once standard time
# began (measured 11/1/2026). No offset = wall clock.
$Trigger.StartBoundary = ([datetime]$Trigger.StartBoundary).ToString("yyyy-MM-ddTHH:mm:ss")

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 15)

# StartWhenAvailable: if the machine is off at 2am, runs as soon as it wakes up

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "Daily backup of Claude cross-session memory dirs + wealth-mgmt personal_tax markdown to OneDrive" `
    -Force

Write-Host "Registered scheduled task: $TaskName (daily 2:00 AM)"
Write-Host "Backup target: C:\Users\micha\OneDrive\ClaudeMemoryBackup"
Write-Host "Test manually: schtasks /Run /TN $TaskName"
