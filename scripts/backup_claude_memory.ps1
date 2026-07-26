# Backs up every Claude Code cross-session memory directory, plus wealth-mgmt's
# gitignored personal-tax markdown analyses, to OneDrive (off-machine via cloud
# sync). Before this existed, the memory tier — months of behavioral corrections
# and deal/financial state across command-center, crumbl-ops, wealth-mgmt — had
# zero copies anywhere (2026-07-26 memory/context audit).
#
# Additive copy, deliberately NOT /MIR: corruption or deletion in the source
# does not propagate to the backup. Newer files overwrite older backups; files
# deleted from the source linger in the backup (acceptable — it's a backup,
# not a mirror).
#
# Secrets are excluded by construction: only memory dirs (markdown) and
# personal_tax *.md are copied — never token files or databases.
#
# Registered as daily scheduled task CC-MemoryBackup by
# scripts/register_memory_backup.ps1.

$BackupRoot   = "C:\Users\micha\OneDrive\ClaudeMemoryBackup"
$ProjectsRoot = "C:\Users\micha\.claude\projects"

New-Item -ItemType Directory -Force -Path $BackupRoot | Out-Null
$LogFile = Join-Path $BackupRoot "backup.log"
"=== Backup run $(Get-Date -Format o) ===" | Add-Content -Encoding utf8 $LogFile

$failed = 0

function Copy-Tree($src, $dest, $filter) {
    # robocopy exit codes: 0-7 = success variants, >=8 = failure
    if ($filter) {
        robocopy $src $dest $filter /E /XO /R:2 /W:5 /NP /NDL /NJH /NJS | Out-Null
    } else {
        robocopy $src $dest /E /XO /R:2 /W:5 /NP /NDL /NJH /NJS | Out-Null
    }
    if ($LASTEXITCODE -ge 8) {
        $script:failed++
        "FAIL (rc=$LASTEXITCODE): $src" | Add-Content -Encoding utf8 $LogFile
    } else {
        "OK   (rc=$LASTEXITCODE): $src" | Add-Content -Encoding utf8 $LogFile
    }
}

# 1. Every project's cross-session memory dir (covers future projects automatically)
Get-ChildItem $ProjectsRoot -Directory -ErrorAction SilentlyContinue | ForEach-Object {
    $mem = Join-Path $_.FullName "memory"
    if (Test-Path $mem) {
        Copy-Tree $mem (Join-Path $BackupRoot "memory\$($_.Name)") $null
    }
}

# 2. wealth-mgmt personal-tax analyses: gitignored by design (sensitive), markdown
#    only — the .db files and plaid_tokens.json are intentionally NOT backed up here.
$taxSrc = "C:\Users\micha\wealth-mgmt\data\personal_tax"
if (Test-Path $taxSrc) {
    Copy-Tree $taxSrc (Join-Path $BackupRoot "wealth-mgmt-personal_tax") "*.md"
}

if ($failed -gt 0) {
    "RESULT: $failed copy set(s) FAILED" | Add-Content -Encoding utf8 $LogFile
    exit 1
}
"RESULT: all copy sets OK" | Add-Content -Encoding utf8 $LogFile
exit 0
