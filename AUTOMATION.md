# Automation Registry

Every standing automated job that touches this repo, in one place. The rule that
earns each row its slot: **a job must name its cadence, its freshness signal
(dead-man's tell), and its kill criteria** — a scheduled job without a tell fails
silently (the WM-WeeklyDigest lesson: exit 127 on every run for two weeks,
invisible), and a job without kill criteria outlives its usefulness (the
crumbl-ops weekly-review lesson).

`scripts/check_heartbeats.py` (run weekly by the digest wrapper, and standalone
by the `CC-Heartbeats` Task Scheduler entry) machine-checks the tells marked ✓.
When adding a job here, add its check there too.

| Job | Cadence | Runs via | Freshness signal | ✓ | Kill criteria |
|---|---|---|---|---|---|
| **CC-WeeklyDigest** (3 digests → email + issues + knowledge files) | Fri 6pm ET | Windows Task Scheduler → WSL → `scripts/run_weekly_digest.sh` | `data/feed_archive/posts.json` mtime ≤ 9d | ✓ | Digest-idea acceptance ~0 across all repos for a quarter (see feed report readout) |
| **Practice-doc auto-update** (`digest/practice_updater.py`) | inside weekly run | wrapper step | `[automated]` practice commits; blocked docs exit non-zero | — | Two consecutive months of zero incorporations, or repeated validation blocks |
| **Verdict feedback** (`digest/verdict_feedback.py`) | inside weekly run, pre-analysis | `ai_digest.py` | new issue numbers in `data/digest_feedback/*.json` | — | Dies with the digest |
| **Telemetry trio** (feed report, citation discovery, heartbeats) | inside weekly run | wrapper step | `data/feed_report.md` regenerated weekly | — | Best-effort by design; dies with the digest |
| **weekly-skills-sync** (cross-repo skill PR sync) | Mon 8am ET | Claude Code scheduled task (app storage) | `~/.claude/skills-sync/state.json` last_run ≤ 9d | ✓ | Two consecutive months where every `[skills-sync]` PR is closed unmerged |
| **monthly-backward-pass** (CLAUDE.md training proposals, 4 repos) | 1st, 8am | Claude Code scheduled task (app storage) | `~/.claude/backward-pass/*.json` last_run ≤ 40d | ✓ | Three consecutive months of zero accepted edits |
| **CC-Heartbeats** (independent dead-man's check) | Tue 9am | Windows Task Scheduler → `scripts/check_heartbeats.cmd` | files a GitHub issue when anything is stale | n/a | Only if the whole estate shrinks to the point of pointlessness |
| **monthly-voice-sync** (voice memory reconcile, command-center) | monthly | Claude Code scheduled task (app storage) | app task history | — | Voice captures dry up for a quarter |
| **monthly-thesis-check** (wealth-mgmt thesis review → PR) | 10th, 8:15am | Claude Code scheduled task (app storage) | `knowledge/thesis-checks/` files in wealth-mgmt | — | Two consecutive quarters of PRs closed unread |

Not in this repo but part of the estate: crumbl-ops self-hosts its review
workflows (rethink tracked in crumbl-ops#1920); wealth-mgmt consumes
`reviews/workflow-template.yml`; the WM weekly digest lives in wealth-mgmt.

## Rebuild on a new machine

Task Scheduler entries and Claude Code app tasks don't travel with git:

1. `powershell -ExecutionPolicy Bypass -File scripts/register_weekly_digest.ps1`
2. `powershell -ExecutionPolicy Bypass -File scripts/register_heartbeat.ps1`
3. Recreate the two Claude Code app tasks (Mon 8am skills-sync; monthly 1st 8am
   backward-pass) pointing at their SKILL.md files under `.claude/skills/`.
