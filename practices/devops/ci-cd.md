# CI/CD Patterns

## GitHub Actions — Automated Code Review

```yaml
# .github/workflows/weekly-reviews.yml
name: Weekly Reviews
on:
  schedule:
    - cron: '0 13 * * 1'  # Monday 8am ET (code review)
    - cron: '0 13 * * 3'  # Wednesday 8am ET (UI review)
    - cron: '0 13 * * 5'  # Friday 8am ET (QA review)

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: anthropics/claude-code-action@beta
        with:
          prompt: |
            Review the following files for:
            1. Security vulnerabilities (Critical/High/Medium/Low)
            2. Performance issues
            3. Code quality
            Output as GitHub issue body with checkboxes.
```

Creates GitHub issues with findings for tracking.

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
