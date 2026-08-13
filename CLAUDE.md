# CLAUDE.md

> Context for Claude Code agents working on this repo.

## What This Is

Best practices repository — a living catalog of patterns, conventions, and tools extracted from production projects (crumbl-ops, wealth-mgmt, healthpulse). Reference this repo when starting new projects or making architectural decisions.

Also includes the RSS digest tool for ingesting new ideas from AI/engineering blogs.

## Structure

```
best-practices/
  practices/           # Categorized best practice documents
    INDEX.md           # Start here — links to all practices
    architecture/      # FastAPI, DB, Pydantic, resilience, logging, config, testing, mobile
    ai/                # Gemini integration, prompt engineering
    finance/           # AI for finance, investing patterns, payroll
    security/          # Secrets management, auth, rate limiting
    devops/            # Cloud Run, CI/CD
    claude-code/       # CLAUDE.md templates, CLI patterns
  reviews/             # Claude-only, diff-scoped review system — see reviews/README.md
    workflow-template.yml  # 5 scheduled types: changes (Mon), data-qa (Thu),
                       #   cto (22nd), context-memory (1st), model-hierarchy (15th).
                       #   Consumed by wealth-mgmt; crumbl-ops self-hosts its own
                       #   prompts; command-center has no review workflow.
    *-review.md        # Scheduled prompts + on-demand audits (ui, devops, ai-slop, ...)
  digest/              # RSS digest tool (module)
    ai_digest.py       # Main logic
    config/            # feeds.yaml, 3 context files
    requirements.txt   # Python dependencies
  knowledge/           # Learning log
```

## Using Practices

When starting a new project or making a decision, check `practices/INDEX.md` for relevant patterns. Each practice doc includes:
- The pattern with code examples
- Key conventions and gotchas
- Which repos use it (for real-world reference)

## Running the Digest

Three digests, each targeted at a specific repo. Every digest:
- Sends an email to `michael.a.dickson@gmail.com`
- Saves a knowledge file under `data/digest_knowledge/`
- Creates a self-contained GitHub issue in the target repo (local execution only — see below)

### Scheduled execution (local, Friday 6pm ET)

The full pipeline runs locally as Windows Task Scheduler task `CC-WeeklyDigest`,
not in GitHub Actions. Reasons: avoids storing a cross-repo PAT in this public
repo, and uses local `gh` auth to file issues across crumbl-ops, command-center,
wealth-mgmt.

```powershell
# One-time registration:
powershell -ExecutionPolicy Bypass -File scripts/register_weekly_digest.ps1
```

The wrapper at `scripts/run_weekly_digest.sh`:
1. Pulls `gemini-api-key` and `smtp-password` from GCP Secret Manager (project `hybrid-elysium-471814-p2`)
2. Runs all three digests via WSL bash
3. Creates GitHub issues in target repos using local `gh` auth
4. Auto-updates the living practice docs from the same week's articles (`python -m digest.practice_updater`) — see below
5. Commits and pushes the new knowledge files + any practice-doc updates back to `origin/main` (two separate `[automated]` commits)

### Auto-updating the living practice docs

Each weekly run also feeds the week's archived articles to `digest/practice_updater.py`,
which **auto-edits** the living practice docs in place:
- `practices/claude-code/context-memory-management.md`
- `practices/claude-code/code-review-and-ai-slop.md`

Config is `digest/config/practice-docs.yaml` (topic, scope, keyword prefilter, required
anchors). Guardrails, since this also edits the anti-slop doc itself:
- **Dedup ledger** `data/practice_updates/incorporated.json` — a source article is never
  integrated into the same doc twice.
- **Two-stage LLM** — extract genuinely-new candidates, then integrate into the full doc.
- **Structural validation before write** — H1 + required anchors (`## Sources`,
  `## Where Used`) must survive and length must stay in bounds, else the write is
  rejected and the doc is left untouched (retries next week). Git history is the backstop.
- Most weeks change nothing. Review the `[automated]` practice commits like any other diff.

### Manual / dev runs

```bash
cd /path/to/best-practices
pip install -r digest/requirements.txt

# Dry-run any context
python -m digest --context digest/config/context-crumbl-ops.yaml --dry-run
python -m digest --context digest/config/context-command-center.yaml --dry-run
python -m digest --context digest/config/context-wealth-mgmt.yaml --dry-run

# Preview the practice-doc auto-update (shows diffs, writes nothing, touches no ledger)
python -m digest.practice_updater --dry-run

# Or run the full local pipeline manually
bash scripts/run_weekly_digest.sh
```

The GitHub Actions workflow (`.github/workflows/weekly-digests.yml`) remains
for manual dispatch fallback (e.g., re-running a failed digest from any
machine). It sends email + commits knowledge files and practice-doc updates,
but does NOT create issues — that part requires the local `gh` auth.

## Weekly Skills Sync

Skills evolve inside individual repos and the improvements never used to travel.
The `weekly-skills-sync` Claude Code scheduled task (Mondays 8am ET, runs
locally while the app is open — deferred to next launch otherwise) executes
[`.claude/skills/skills-sync/SKILL.md`](.claude/skills/skills-sync/SKILL.md):

- Scans `.claude/skills/**` commits on `origin/main` of best-practices,
  crumbl-ops, command-center, wealth-mgmt since the last run
  (state: `~/.claude/skills-sync/state.json`, local only — not in this repo).
- Judges portable mechanism vs repo-specific content, then opens at most one
  adapted `[skills-sync]` PR per target repo (never pushes to main; never
  touches local working trees — all edits happen in throwaway worktrees).
- `[skills-sync]` commits are excluded from future scans (ping-pong guard),
  and private-repo detail is never generalized into this public repo's skills.

Run `/skills-sync` in a session for an on-demand pass, or ask for a
"full reconcile" to compare current skills across all four repos ignoring state.

## Configuration

- `digest/config/feeds.yaml` — All RSS feed sources
- `digest/config/context-crumbl-ops.yaml` — Crumbl-ops digest (target: `michaeladickson/crumbl-ops`)
- `digest/config/context-command-center.yaml` — Command-center digest (target: `michaeladickson/command-center`)
- `digest/config/context-wealth-mgmt.yaml` — Wealth-mgmt digest (target: `michaeladickson/wealth-mgmt`)
- `digest/config/practice-docs.yaml` — Living docs the weekly run auto-edits (topic, scope, keyword prefilter, required anchors)
- Secrets: pulled from GCP Secret Manager at runtime; no `.env` in this public repo

## Key Conventions

- Always use GEMINI_API_KEY, not Vertex AI (avoids gcloud reauth issues)
- Practices docs should be actionable with code examples, not vague descriptions
- Each practice includes "Where Used" section linking to source repos
- Keep practices up to date as repos evolve

## Learning

Track knowledge in `knowledge/INDEX.md` → category files. The full memory model —
tiers, retrieval contracts, anti-fragmentation, and staleness — lives in
[`practices/claude-code/context-memory-management.md`](practices/claude-code/context-memory-management.md).
Key rules:

- **Corrections route to their home, not a catch-all log.** Behavioral feedback →
  cross-session memory; architectural choices → the `decisions/` journal; a failed
  domain hypothesis → demote it in the relevant `hypotheses.md`. A catch-all
  *corrections* log fragments these. This does not condemn a scoped error log:
  crumbl-ops `knowledge/ERRORS.md` holds only deterministic infra/code failures and
  carries a graduation rule in its header, which is a different artifact and fine.
- **Don't date-stamp everything.** Let genuinely time-sensitive entries carry an inline
  date; rely on git history for change time. Status *snapshots* can be staleness-checked
  by mtime, but stable reference facts can't — age ≠ wrong.
- **Flag contradictions.** When new evidence contradicts an established rule, surface it
  to the user rather than silently following the old rule; if confirmed, demote the rule
  where it lives.
