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
  pricing/        # Example domain folder
    knowledge.md  # facts and patterns
    hypotheses.md # need more data
    rules.md      # confirmed — apply by default
```

Principles:
- Progressive disclosure: read top-down, load only what you need
- Separate domain knowledge (what) from procedural (how)
- Graduate resolved errors into knowledge files
- Review and merge/split files regularly

**Hypothesis → Rule promotion** (paste into CLAUDE.md):
```
Before starting a new task, review existing rules and hypotheses for this domain.
Apply rules by default. Check if any hypothesis can be tested with today's work.
At the end of each task, extract insights and store in domain folders.
When a hypothesis is confirmed 5+ times, promote it to a rule.
When a rule is contradicted by new data, demote it back to a hypothesis.
```

## Decision Journal

Log architectural decisions so "why did we build it this way?" always has an answer.

**File:** `/decisions/YYYY-MM-DD-{topic}.md`

**Format:**
```markdown
**Supersedes:** [link to prior decision file] (omit if none)

## Decision
{what you decided}

## Context
{why this came up}

## Alternatives Considered
{what else was on the table}

## Reasoning
{why this option won}

## Trade-offs Accepted
{what you gave up}
```

**Supersedes edges:** when a new decision invalidates an old one, declare it explicitly via `Supersedes:`. The chain becomes the audit trail — `grep -r "Supersedes:" decisions/` walks the whole graph. Optionally, when superseding, edit the old file to add `**Superseded-by:** [link]` at the top so the back-edge is also queryable.

When about to make a similar decision, grep `decisions/` for prior choices. Follow them unless new information invalidates the reasoning — and if it does, that's a new decision file with a `Supersedes:` link.

## Memory Tiers

Three tiers of context, from ephemeral to durable. Each has a distinct purpose. Storing the wrong thing in the wrong tier creates context bloat or knowledge loss.

| Tier | Scope | Lives In | Belongs Here |
|---|---|---|---|
| **1. Session** | Current task | Active conversation, `MEMORY.md` | Transient state, what we're doing right now |
| **2. Project** | This repo | `knowledge/`, `decisions/`, `CLAUDE.md`, per-module `CLAUDE.md` | Domain facts, rules, decisions specific to this codebase |
| **3. Global** | Cross-repo | `~/best-practices/practices/` | Patterns and conventions reused across multiple projects |

**The test for where to store something:** would this still be true in a different repo? If yes → Tier 3. If only here → Tier 2. If only this session → don't store it.

**Promotion path:** when a Tier 2 pattern shows up in a second project, promote it to Tier 3 (extract into `practices/`). When a Tier 3 practice gets refined by real-world use, the source repos update via the reference link, not duplication.

## Layered Architecture

Instructions stack — they don't override. All CLAUDE.md files load together.
Arrays (like permissions) combine. Scalars (like model) use the most specific value.
`settings.local.json` always wins.

```
01 Admin          /etc/claude-code/      # org policy, LOCKED
02 Global (you)   ~/
   .claude/
     CLAUDE.md                           # voice, style, personal rules
     settings.json                       # default permissions & model
     keybindings.json
     skills/                             # available in every project
     agents/                             # available in every project
03 Project (team) your-project/
   CLAUDE.md                             # main team instructions [GIT]
   CLAUDE.local.md                       # private overrides [LOCAL]
   .mcp.json                             # team MCP servers [GIT]
   .claude/
     settings.json                       # permissions, hooks, model [GIT]
     settings.local.json                 # your overrides, highest priority [LOCAL]
     rules/                              # load when Claude reads matching files
       testing.md    paths: [**/*.test.ts]
       api-conventions.md paths: [src/api/**]
     skills/                             # invoke with /name [GIT]
       deploy/
         SKILL.md                        # trigger, model, tools
     agents/                             # spawn with Task or @mention [GIT]
       researcher.md                     # model, tools, isolation mode
     worktrees/                          # isolated repo copies [LOCAL]
```

## Four Building Blocks

**Rules** — `rules/testing.md`
```yaml
---
paths: ["**/*.test.ts"]
---
Use Jest. Mock at module boundaries only. Test one behavior per test case.
```
Loads only when matching files enter context. Unlike root CLAUDE.md, it's path-scoped.

**Hooks** — `settings.json`
```json
"hooks": {
  "PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "lint"}]}]
}
```
Events: `PreToolUse`, `PostToolUse`, `Stop`, `SessionStart`. Shell commands, not AI.

**Skills** — `skills/deploy/SKILL.md`
```yaml
---
description: deploy to prod
model: claude-sonnet-4-6
tools: [Bash, Read, Write]
---
Run pre-flight checks. Deploy. Verify health.
```
Invoke with `/deploy` or auto-matched by description.

**Agents** — `agents/researcher.md`
```yaml
---
model: claude-haiku-4-5
tools: [WebSearch, Read]
isolation: full
---
Given a topic, return a structured research brief.
```
Spawn with Task tool or `@mention`. Runs with own model, tools, optional worktree isolation.

## Where Used

- **crumbl-ops**: Root + module-level CLAUDE.md files, full knowledge system
- **wealth-mgmt**: Root CLAUDE.md + knowledge system with domain/procedural split
- **healthpulse**: Root CLAUDE.md with architecture decisions section
