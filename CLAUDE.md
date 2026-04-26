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

Three digests, each with its own context:

```bash
cd /path/to/best-practices
pip install -r digest/requirements.txt

# Engineering (default) — AI tooling, architecture, dev practices
python -m digest --dry-run
python -m digest

# Operational Finance — CFO workflows, accounting automation, payroll, forecasting
python -m digest --context digest/config/context-finance.yaml --dry-run

# Investing — portfolio analysis, macro trends, wealth management, fintech
python -m digest --context digest/config/context-investing.yaml --dry-run
```

## Configuration

- `digest/config/feeds.yaml` — All RSS feed sources (engineering + finance + investing)
- `digest/config/context-engineering.yaml` — Engineering/AI digest (default)
- `digest/config/context-finance.yaml` — Operational finance / CFO digest
- `digest/config/context-investing.yaml` — Investing / wealth management digest
- `.env` — GEMINI_API_KEY, SENDGRID_API_KEY, ALERT_EMAIL

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
