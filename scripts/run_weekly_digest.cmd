@echo off
REM Wrapper invoked by Windows Task Scheduler (CC-WeeklyDigest).
REM Avoids the nested-quote bug from invoking a wsl bash command through
REM powershell.exe -Command. Calls WSL directly, appends to log file.
wsl -- bash -c "cd /mnt/c/Users/micha/best-practices && bash scripts/run_weekly_digest.sh >> /mnt/c/Users/micha/best-practices/logs/weekly_digest.log 2>&1"
