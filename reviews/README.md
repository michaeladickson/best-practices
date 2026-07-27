# Shared Review System

Centralized review prompts + a single GitHub Actions workflow template. Claude-only
(`claude-fable-5`, `--effort max`), rebuilt 2026-07-26. `workflow-template.yml` is
ground truth — this README is just the router.

**Consumers:** wealth-mgmt runs the template as-is. crumbl-ops self-hosts its own
prompts. command-center has no review workflow. Gemini is retired from all review
pipelines.

## Scheduled Types

One workflow, five review types, each on its own cron:

| Type | When | Prompt(s) | Scope |
|------|------|-----------|-------|
| `changes` | Monday | `code-review.md` + `security-review.md` | Week's git diff |
| `data-qa` | Thursday | `data-review.md` + `qa-review.md` | Week's git diff |
| `cto` | Monthly (22nd) | `cto-review.md` | Full scope — strategic |
| `context-memory` | Monthly (1st) | `context-memory-review.md` | Full scope — self-assessment |
| `model-hierarchy` | Monthly (15th) | `model-hierarchy-review.md` | Full scope — self-assessment |

Two design rules worth knowing:

- **Diff-scoped weeklies.** The weekly types review the week's changes in context,
  not the whole repo — full-repo re-reads produced zero-net-new-finding issues nobody
  read. Quiet week (no commits, or no findings) → no issue is filed.
- **Unique cron fire-times.** GitHub coalesces same-minute crons into one run, which
  silently ate the monthly reviews in the old layout. Every schedule entry in the
  template fires at a distinct minute; keep it that way when editing.

## On-Demand Audit Prompts

Not in the scheduled rotation — paste into a Claude Code session in the target repo,
or dispatch the workflow manually where applicable.

| File | Audit |
|------|-------|
| `ai-slop-review.md` | AI-slop / code-review process — spec discipline, validation loop, destructive-action gating, cleanup-tax telemetry |
| `agent-action-safety-review.md` | Agent action safety — action tiers, least-privilege, judge layer, human-in-the-loop, audit trail |
| `llm-eval-review.md` | LLM evaluation — fixture datasets, regression gates, model-upgrade gating, drift monitoring |
| `context-memory-review.md` | Context/memory self-assessment (also scheduled monthly, 1st) |
| `model-hierarchy-review.md` | Model-hierarchy delegation self-assessment (also scheduled monthly, 15th) |
| `ui-review.md` | UI/UX audit — consistency, accessibility, responsiveness (reclassified on-demand 2026-07-26) |
| `devops-review.md` | DevOps/SRE audit — deployment, secrets, monitoring, scaling (reclassified on-demand 2026-07-26) |

## Setup for a New Repo

1. Copy `workflow-template.yml` to `.github/workflows/weekly-reviews.yml`
2. Copy `review-context-template.md` to `.github/prompts/review-context.md` and fill
   in your project's specifics (threat model, intentional decisions, what to skip)
3. Set one secret: `CLAUDE_CODE_OAUTH_TOKEN` — that's all, no GCP anything
4. Ensure `GITHUB_TOKEN` has `issues: write` permission

## Updating Prompts

Edit the `.md` files in this directory. Prompts are fetched at runtime from this
repo's `main`, so changes take effect on the next run across all consumers — no PRs
needed in target repos.

## Per-Repo Customization

Each repo's `.github/prompts/review-context.md` tells reviewers what the app is,
the threat model, intentional design decisions to NOT flag, and what makes a good
finding. This is the key to reducing false positives — keep it current.
