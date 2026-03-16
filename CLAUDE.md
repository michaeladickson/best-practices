# CLAUDE.md

> Context for Claude Code agents working on this repo.

## What This Is

Reusable AI community digest tool. Fetches RSS feeds from AI/engineering writers, analyzes relevance to configurable project contexts, scores posts, and generates project-specific recommendations. Sends formatted email digests.

Designed to be used across multiple projects by swapping `config/context.yaml`.

## Tech Stack

- **Runtime:** Python 3.12, Click CLI
- **AI:** Gemini 2.5 Flash via Vertex AI (free tier) or API key
- **Feeds:** feedparser for RSS/Atom
- **Email:** SendGrid
- **Storage:** SQLite for article/thesis persistence

## Usage

```bash
python -m src.digest --dry-run              # preview digest
python -m src.digest                        # send email
python -m src.digest --days 14              # look back 14 days
python -m src.digest --context custom.yaml  # use alternate project context
```

## Configuration

- `config/feeds.yaml` — RSS feed sources
- `config/context.yaml` — project context for relevance scoring (swap per project)
- `.env` — GCP_PROJECT_ID, SENDGRID_API_KEY, ALERT_EMAIL, GEMINI_API_KEY (optional)

## Learning

Track knowledge in `knowledge/INDEX.md` → category files.
Log errors to `knowledge/ERRORS.md`.
