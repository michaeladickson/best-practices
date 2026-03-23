# CLAUDE.md Structure

Every project should have a root `CLAUDE.md` that gives Claude Code full context to work autonomously. Complex modules can have their own local `CLAUDE.md` files.

## Root CLAUDE.md Template

```markdown
# CLAUDE.md

> Context for Claude Code agents working on this repo.

## What This Is

[1-2 sentences: what the project does, who it's for]

## Tech Stack

- **Runtime:** [language, version, framework]
- **AI:** [model, provider, how accessed]
- **Database:** [type, hosting]
- **External:** [key integrations]

## Running Locally

\`\`\`bash
[exact copy-paste commands to start the project]
\`\`\`

## Key Conventions

- [Logging: structlog everywhere]
- [SQL: use ? placeholders, ON CONFLICT for upserts]
- [Financial: Decimal, never float]
- [Secrets: GEMINI_API_KEY preferred over Vertex AI]

## Architecture

- [Deployment target]
- [Key connections / external services]
- [Multi-tenant details if applicable]

## Deploying

\`\`\`bash
[exact deploy commands]
\`\`\`

## Common Pitfalls

- [Non-obvious gotchas that waste time]

## File Map

- `src/api/main.py` — FastAPI app, CORS, routes
- `src/ops/db.py` — DB connection pool
- [key files with brief purpose]

## Learning

Track knowledge in `knowledge/INDEX.md` → category files.
Log errors to `knowledge/ERRORS.md`.
```

## Module-Level CLAUDE.md

For complex subsystems, add a local `CLAUDE.md` in the module directory:

```markdown
# src/qbo/CLAUDE.md

## What This Module Does

[Specific subsystem description]

## Non-Obvious Details

- Token expiry: access tokens last 1 hour, refresh tokens 100 days
- Race condition: use threading lock for concurrent token refresh
- [Edge cases, gotchas specific to this module]

## Key Files

- `client.py` — API client with retry logic
- `journal_entry.py` — JE construction from sales data
```

## Knowledge System

```
knowledge/
  INDEX.md        # Links to all knowledge files
  ERRORS.md       # Recurring errors and solutions
  domain/         # What things are (accounts, tax rules, etc.)
  procedural/     # How to do things (data import, analysis, etc.)
```

Principles:
- Progressive disclosure: read top-down, load only what you need
- Separate domain knowledge (what) from procedural (how)
- Graduate resolved errors into knowledge files
- Review and merge/split files regularly

## Where Used

- **crumbl-ops**: Root + module-level CLAUDE.md files, full knowledge system
- **wealth-mgmt**: Root CLAUDE.md + knowledge system with domain/procedural split
- **healthpulse**: Root CLAUDE.md with architecture decisions section
