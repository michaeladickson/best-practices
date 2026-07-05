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
| Thursday | Data | `data-review.md` — Pipeline reliability, forecast accuracy, financial data integrity |
| Friday | QA | `qa-review.md` — Edge cases, concurrency, auth, idempotency |
| Friday PM | DevOps | `devops-review.md` — Deployment reliability, monitoring, secrets, scaling |
| Saturday | **CTO** | `cto-review.md` — Strategic layer: reads all 6 function reviews, evaluates health, suggests prompt improvements |

## Architecture

```
Mon: Code Review    ──┐
Tue: Security       ──┤
Wed: UI Review      ──┤
Thu: Data Review    ──┼── Sat: CTO Review (reads all outputs, evaluates prompts)
Fri: QA Review      ──┤
Fri: DevOps Review  ──┘
```

Each function review runs independently (Gemini + Claude → synthesis → GitHub issue). The CTO review runs after all 6, reads their issues, evaluates at a strategic level, and suggests improvements to the review prompts themselves.

## Files

| File | Purpose |
|------|---------|
| `code-review.md` | Code review prompt |
| `ui-review.md` | UI/UX review prompt |
| `qa-review.md` | QA review prompt |
| `security-review.md` | Security audit prompt (CWE references, positive findings) |
| `data-review.md` | Data integrity, pipeline reliability, forecast accuracy |
| `devops-review.md` | Deployment, monitoring, secrets, infrastructure, scaling |
| `cto-review.md` | CTO-level strategic review — reads all function outputs, evaluates health, improves prompts |
| `context-memory-review.md` | On-demand context/memory self-assessment — context assembly, memory tiers, CLAUDE.md leanness, skills, governed write-back |
| `ai-slop-review.md` | On-demand AI-slop/code-review self-assessment — spec discipline, validation loop, destructive-action gating, cleanup-tax telemetry |
| `agent-action-safety-review.md` | On-demand agent action-safety self-assessment — action tiers, least-privilege, judge layer, human-in-the-loop, audit trail |
| `llm-eval-review.md` | On-demand LLM-evaluation self-assessment — fixture datasets, regression gates, model-upgrade gating, drift monitoring |
| `model-hierarchy-review.md` | On-demand model-hierarchy delegation self-assessment — tier awareness, parent-judgment/hands split, depth cap, structured returns, delegation audit trail |
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
