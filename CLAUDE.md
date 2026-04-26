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
  reviews/             # Shared review prompts (used by all repos via GitHub Actions)
    code-review.md     # Weekly code review prompt
    ui-review.md       # Weekly UI review prompt
    qa-review.md       # Weekly QA review prompt
    security-review.md # On-demand security audit prompt
    workflow-template.yml  # Copy to .github/workflows/ in any repo
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

### Scheduled execution (local, Sunday 6pm ET)

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
4. Commits and pushes the new knowledge files back to `origin/main`

### Manual / dev runs

```bash
cd /path/to/best-practices
pip install -r digest/requirements.txt

# Dry-run any context
python -m digest --context digest/config/context-crumbl-ops.yaml --dry-run
python -m digest --context digest/config/context-command-center.yaml --dry-run
python -m digest --context digest/config/context-wealth-mgmt.yaml --dry-run

# Or run the full local pipeline manually
bash scripts/run_weekly_digest.sh
```

The GitHub Actions workflow (`.github/workflows/weekly-digests.yml`) remains
for manual dispatch fallback (e.g., re-running a failed digest from any
machine). It sends email + commits knowledge files but does NOT create
issues — that part requires the local `gh` auth.

## Configuration

- `digest/config/feeds.yaml` — All RSS feed sources
- `digest/config/context-crumbl-ops.yaml` — Crumbl-ops digest (target: `michaeladickson/crumbl-ops`)
- `digest/config/context-command-center.yaml` — Command-center digest (target: `michaeladickson/command-center`)
- `digest/config/context-wealth-mgmt.yaml` — Wealth-mgmt digest (target: `michaeladickson/wealth-mgmt`)
- Secrets: pulled from GCP Secret Manager at runtime; no `.env` in this public repo

## Key Conventions

- Always use GEMINI_API_KEY, not Vertex AI (avoids gcloud reauth issues)
- Practices docs should be actionable with code examples, not vague descriptions
- Each practice includes "Where Used" section linking to source repos
- Keep practices up to date as repos evolve

## Learning

Track knowledge in `knowledge/INDEX.md` → category files.
Log errors to `knowledge/ERRORS.md`.

Annotate domain knowledge with verification dates so rules don't go stale:
```
- Claude Code supports hooks for pre/post tool execution
  (verified: 2026-03-20, source: docs review)
```
- When you encounter evidence that contradicts an established rule, flag it to the user rather than silently following the old rule
- If a rule is contradicted by new data, demote it: move it out of CLAUDE.md back into the relevant knowledge file as unverified, and note the contradiction
- Periodically check `verified` dates — anything unverified for 90+ days should be re-tested when the opportunity arises
