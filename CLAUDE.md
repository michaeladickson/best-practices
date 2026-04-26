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
- Creates a self-contained GitHub issue in the target repo

```bash
cd /path/to/best-practices
pip install -r digest/requirements.txt

# Crumbl-ops — engineering + operational finance combined
python -m digest --context digest/config/context-crumbl-ops.yaml --dry-run

# Command-center — agent / personal automation focused
python -m digest --context digest/config/context-command-center.yaml --dry-run

# Wealth-mgmt — investing, macro analysis, portfolio research
python -m digest --context digest/config/context-wealth-mgmt.yaml --dry-run
```

## Configuration

- `digest/config/feeds.yaml` — All RSS feed sources
- `digest/config/context-crumbl-ops.yaml` — Crumbl-ops digest (target: `michaeladickson/crumbl-ops`)
- `digest/config/context-command-center.yaml` — Command-center digest (target: `michaeladickson/command-center`)
- `digest/config/context-wealth-mgmt.yaml` — Wealth-mgmt digest (target: `michaeladickson/wealth-mgmt`)
- `.env` — GEMINI_API_KEY, SMTP_PASS, GH_TOKEN (for cross-repo issue creation)
- GitHub Action: `DIGEST_GH_TOKEN` secret = fine-grained PAT with Issues:write on the three target repos

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
