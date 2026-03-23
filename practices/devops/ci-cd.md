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

## Where Used

- **crumbl-ops**: Cloud Build for API + sync jobs, GitHub Actions for weekly reviews
