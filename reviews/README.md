# Shared Review Prompts

Centralized review prompts used by all repos via GitHub Actions. Update a prompt here and it applies everywhere on the next run.

## Review Types

| File | Schedule | Focus |
|------|----------|-------|
| `code-review.md` | Monday | Security, data integrity, error handling, performance, code quality |
| `ui-review.md` | Wednesday | Consistency, accessibility, responsiveness, UX, component reuse |
| `qa-review.md` | Friday | Edge cases, concurrency, auth, idempotency, external API failures |
| `security-review.md` | On-demand | Dedicated security audit (OWASP-aligned) |

## Setup for a New Repo

1. Copy `workflow-template.yml` to `.github/workflows/weekly-reviews.yml` in the target repo
2. Ensure `ANTHROPIC_API_KEY` is set in the repo's GitHub Secrets
3. The workflow fetches prompts from this repo at runtime — no need to copy prompt files

## How It Works

- Scheduled runs: Monday (code), Wednesday (UI), Friday (QA)
- Manual dispatch: choose any review type including security
- Claude Code Action reads the prompt and reviews the codebase
- Findings are posted as GitHub issues with severity labels and checkboxes

## Updating Prompts

Edit the `.md` files in this directory. Changes take effect on the next scheduled or manual run across all repos — no PRs needed in target repos.
