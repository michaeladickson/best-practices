# Shared Review System

Centralized review prompts + a single GitHub Actions workflow template. Claude-only
(`claude-opus-5-5`, `--effort high`; was `claude-fable-5` at `max` until 2026-09-25), rebuilt 2026-07-26. `workflow-template.yml` is
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
| `ai-slop-review.md` | AI-slop / code-review process — spec discipline, validation loop, destructive-action gating, cleanup-tax telemetry (also scheduled monthly, 8th) |
| `agent-action-safety-review.md` | Agent action safety — action tiers, least-privilege, judge layer, human-in-the-loop, audit trail |
| `llm-eval-review.md` | LLM evaluation — fixture datasets, regression gates, model-upgrade gating, drift monitoring |
| `database-review.md` | Database structure and performance — live read-only stats (seq scans, index hygiene, cache, timeouts) plus schema types, keys, migrations, pooling, query patterns |
| `tenant-isolation-review.md` | Tenant boundary — isolation model, live DB grants / secret IAM / bucket layout, tenant resolution, shared caches, outbound channels, inherited config, lifecycle |
| `module-boundaries-review.md` | Structure and dependencies — measured import graph, cycles, lazy imports, size, dependency direction, SQL spread, git co-change hotspots; domain decomposition, layering, extension points, enforcement |
| `failure-modes-review.md` | Failure behavior — live job history, step-failure records, alert policies and channels, error volume, backup config; timeouts, retries, partial and silent failure, wrong data, alert quality, blast radius; incident replay against post-mortems |
| `context-memory-review.md` | Context/memory self-assessment (also scheduled monthly, 1st) |
| `model-hierarchy-review.md` | Model-hierarchy delegation self-assessment (also scheduled monthly, 15th) |
| `ui-review.md` | UI/UX audit — consistency, accessibility, responsiveness (reclassified on-demand 2026-07-26) |
| `devops-review.md` | DevOps/SRE audit — deployment, secrets, monitoring, scaling (reclassified on-demand 2026-07-26) |

**Depth reviews vs. weekly diff checks.** `database-review.md`,
`tenant-isolation-review.md`, `module-boundaries-review.md` and `failure-modes-review.md`
are *depth reviews*:
full scope, a specialist's view, graded from live evidence (the database's own
statistics, real grants, the measured import graph and git history), each ending in a
Good / Gap / Missing scorecard. The weekly prompts do not repeat their questions. They
keep a narrow check on the same failure classes, scoped to the week's diff, so a
regression is caught in the week it is written (`data-review.md` §7 and §9,
`qa-review.md` §4). A whole-repo question in a diff-scoped prompt cannot be answered
from the diff, so it belongs in a depth review.

Depth reviews need live access (the Cloud SQL proxy, `gcloud`), which this workflow
deliberately does not hold, so they run as local scheduled tasks, quarterly and
staggered (see `AUTOMATION.md`). Each files one issue labeled `depth-review` with a
`Scorecard: Good N / Gap N / Missing N` line, and `cto-review.md` §1b tracks the trend.

## Setup for a New Repo

1. Copy `workflow-template.yml` to `.github/workflows/weekly-reviews.yml`
2. Copy `review-context-template.md` to `.github/prompts/review-context.md` and fill
   in your project's specifics (threat model, intentional decisions, what to skip)
3. Set one secret: `CLAUDE_CODE_OAUTH_TOKEN` — that's all, no GCP anything
4. Ensure `GITHUB_TOKEN` has `issues: write` permission

## Per-PR Review Gate (optional)

`pr-review-template.yml` runs one bounded Claude review on each pull request and posts it
as a single comment. It reviews when a PR opens or leaves draft, and again whenever the
`re-review` label is added. A clean review posts nothing. Findings carry `[Important]`,
`[Nit]` or `[Pre-existing]` and open with a count line (format in
`review-context-template.md`). It complements the weekly diff review: a cheap tripwire at
merge time, a deeper audit on cadence.

**Where it runs:** command-center (this template's source, merged 2026-10-21). crumbl-ops
runs a heavier variant with a merge hook that holds on `[Important]` Medium-or-above
findings, a two-review cap, a per-commit `review-freshness` status and a usage gate.

**Setup:**

1. Copy `pr-review-template.yml` to `.github/workflows/pr-review.yml`, keeping that exact
   name (the workflow detects PRs that edit it by path). Edit the `CUSTOMIZE` lines: the
   repo's prose-only directories, and model and effort.
2. Fill `.github/prompts/review-context.md` from `review-context-template.md`, including
   Severity, Finding Tags and Output Format. The review reads it from the base branch, so a
   PR cannot loosen its own rules.
3. Add the scratch files to `.gitignore`: `/pr-diff.md`, `/pr-review-rules.md`,
   `/pr-review-output.md`, `/pr-comment-body.md`.
4. Confirm the Claude GitHub App covers the repo: github.com/settings/installations →
   Claude → Configure. The action exchanges an OIDC token for the app's token.
5. Add the `CLAUDE_CODE_OAUTH_TOKEN` Actions secret, from `claude setup-token`. Without it,
   every PR gets a green skip and a "Not reviewed" comment.
6. Require your CI in branch protection, not this review: it is advisory, and a required
   AI check blocks every merge whenever the model pool is busy.
7. The PR that adds the workflow gets no AI review: claude-code-action validates the
   workflow against the default branch and skips. Run `/code-review` locally on it.

**Gotchas the template already handles:**
- **No re-review on push (`synchronize`):** re-reviews of mid-PR fix-up pushes were about
  40% of crumbl-ops' review runs in August 2026 (934 runs for 546 PRs).
- **Nothing is passed through `${{ }}` into the prompt:** a value over ~19.7k chars makes
  the whole workflow invalid with no lint warning, so the diff is written to a file the
  reviewer reads.
- **`--tools`, not just `--allowedTools`:** the reviewer reads untrusted content, so it
  gets Read/Glob/Grep/Write and nothing else.
- **Label events get their own concurrency group:** otherwise adding any other label
  cancels the real review.

Like `workflow-template.yml`, each consumer holds its own copy: a change here needs a PR in
each repo that adopted it.

## Updating Prompts

Edit the `.md` files in this directory. Prompts are fetched at runtime from this
repo's `main`, so changes take effect on the next run across all consumers — no PRs
needed in target repos. The workflow file is different: each consumer holds a copy,
so a change to `workflow-template.yml` (model, effort, schedule) needs a PR in each
consumer repo too.

## Per-Repo Customization

Each repo's `.github/prompts/review-context.md` tells reviewers what the app is,
the threat model, intentional design decisions to NOT flag, and what makes a good
finding. This is the key to reducing false positives — keep it current.
