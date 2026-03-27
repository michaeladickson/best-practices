# Shared Review System

Centralized review prompts and workflow for all repos. Dual-model (Gemini + Claude) review with synthesis and issue deduplication.

## How It Works

1. **Issue Dedup** — Fetches all open issues before reviewing to avoid duplicates
2. **Gemini Review** — Full source snapshot sent to Gemini 2.5 Flash via Vertex AI
3. **Claude Review** — Claude Code Action with full repo access (browse, search, read configs)
4. **Synthesis** — Claude merges both reviews: confirms agreements, validates single-model findings, dismisses false positives
5. **Issue Creation** — Synthesized findings posted as a GitHub issue with checkboxes

## Review Schedule

| Day | Type | Prompt |
|-----|------|--------|
| Monday | Code | `code-review.md` — Security, data integrity, error handling, performance |
| Tuesday | Security | `security-review.md` — OWASP-aligned penetration test review |
| Wednesday | UI | `ui-review.md` — Consistency, accessibility, responsiveness, UX |
| Friday | QA | `qa-review.md` — Edge cases, concurrency, auth, idempotency |
| Saturday | **CTO** | `cto-review.md` — Strategic layer: reads all 4 function reviews, evaluates architecture, velocity, cross-function gaps, and overall health |

## Architecture

```
Mon: Code Review  ──┐
Tue: Security     ──┤
Wed: UI Review    ──┼── Sat: CTO Review (reads all 4 outputs)
Fri: QA Review    ──┘
```

Each function review runs independently (Gemini + Claude → synthesis → GitHub issue). The CTO review runs after all 4, reads the issues, and evaluates at a strategic level.

## Files

| File | Purpose |
|------|---------|
| `code-review.md` | Code review prompt |
| `ui-review.md` | UI/UX review prompt |
| `qa-review.md` | QA review prompt |
| `security-review.md` | Security audit prompt (CWE references, positive findings) |
| `cto-review.md` | CTO-level strategic review — reads all function outputs, evaluates health |
| `synthesize.md` | Instructions for merging Gemini + Claude findings |
| `review-context-template.md` | Template for per-repo context (threat model, intentional decisions) |
| `workflow-template.yml` | Full GitHub Actions workflow — copy to each repo |

## Setup for a New Repo

1. Copy `workflow-template.yml` to `.github/workflows/weekly-reviews.yml`
2. Copy `review-context-template.md` to `.github/prompts/review-context.md` and fill in your project's specifics (threat model, intentional decisions, what to skip)
3. Set GitHub Secrets:
   - `CLAUDE_CODE_OAUTH_TOKEN` — for Claude Code Action
   - `GCP_SA_KEY` — for Gemini via Vertex AI
4. Optionally set GitHub Variables:
   - `GCP_PROJECT_ID` — defaults to `hybrid-elysium-471814-p2` if not set

## Updating Prompts

Edit the `.md` files in this directory. Changes take effect on the next run across all repos — no PRs needed in target repos.

## Per-Repo Customization

Each repo has its own `.github/prompts/review-context.md` that tells reviewers:
- What the app is and who uses it (scale context)
- Threat model (what data matters most)
- Intentional design decisions to NOT flag
- What makes a good vs bad finding

This is the key to reducing false positives. Keep it up to date as your project evolves.
