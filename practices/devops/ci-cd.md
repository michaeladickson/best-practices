# CI/CD Patterns

## GitHub Actions — Automated Code Review

Don't hand-roll a review workflow — copy the maintained template at
[`reviews/workflow-template.yml`](../../reviews/workflow-template.yml)
(Claude-only, 5 scheduled review types, single `CLAUDE_CODE_OAUTH_TOKEN` secret).
Three design rules it encodes:

- **Diff-scoped weeklies** — weekly reviews cover the week's git diff in context,
  not a full-repo re-read; full-scope judgment lives in the monthly reviews.
- **Unique cron fire-times** — GitHub coalesces same-minute crons into a single
  run, silently dropping the rest; every schedule entry gets its own minute.
- **Quiet week → no issue** — no commits in the window (or no findings) files
  nothing, instead of an empty issue nobody reads.

## Cloud Build Triggers

- Push to `main` → build + deploy API service
- Manual trigger → run sync/batch jobs
- Tag push → production deploy

## Pre-Commit Hooks

Keep them fast to avoid developer friction:
- Linting (ruff for Python, ESLint for TS)
- Type checking (mypy / tsc)
- Secret detection (git-secrets or similar)

## Workflow-File Validation

GitHub silently treats an **unparseable workflow file as having no triggers** — no
error surfaces anywhere in the UI. The only tell is the API/UI showing the file
*path* as the workflow name (`gh api repos/OWNER/REPO/actions/workflows` → `name`
equals `path`). A scheduled workflow in that state simply never fires; if it's a
monitoring/dead-man's-switch workflow, the watchdog itself is dead and nothing
tells you.

- The classic trap: a multi-line shell string inside `run: |` whose continuation
  lines sit at column 0 — they terminate the YAML block scalar and invalidate the
  whole file. Assemble multi-line bodies with `printf '%s\n' ...` (every line
  stays indented) instead of bare multi-line quotes. (Bit the digest-freshness
  dead-man's switch on 2026-07-26; caught only by dispatching it.)
- Guard: a tiny CI job that `yaml.safe_load`s every file under `.github/workflows/`
  (plus any workflow *templates* the repo distributes) and fails the push — see
  `best-practices/.github/workflows/validate-workflows.yml`.
- After fixing a broken workflow, confirm GitHub reparsed it: the API `name` should
  change from the path back to the workflow's `name:` value.

## Where Used

- **crumbl-ops**: Cloud Build for API + sync jobs, GitHub Actions for weekly reviews
- **best-practices**: `validate-workflows.yml` guards its own workflows + the `reviews/` templates
