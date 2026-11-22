# best-practices

Patterns, conventions and tools taken from my production projects, kept in one place so each new project starts from what the last one learned.

## What is here

- `practices/`: one document per pattern, covering architecture, AI integration, security, devops, Claude Code, finance and writing. Start at `practices/INDEX.md`.
- `reviews/`: scheduled and on-demand code review prompts, with GitHub Actions workflow templates. See `reviews/README.md`.
- `digest/`: a weekly digest tool. It reads RSS feeds from AI and engineering blogs, analyzes them with Gemini against a project's own context, and sends the recommendations by email and as GitHub issues.
- `AUTOMATION.md`: every scheduled job that touches this repo, with its cadence, its freshness signal and its kill criteria.
- `.claude/hooks/`: write-time hooks shared across projects.

This is a working repository, not a packaged library. `CLAUDE.md` has the setup and run instructions.
