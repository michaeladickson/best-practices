# Claude Surface Guide: Chat vs. Cowork vs. Code

Pick the surface that matches your task, not your job title.

> "Most people stay in Chat forever. That's like using Photoshop only to crop photos."

## At a Glance

| | Chat | Cowork | Code Tab | Code CLI/VS Code |
|---|---|---|---|---|
| **Platform** | Web + Desktop + Mobile | Desktop only | Desktop only | Terminal / IDE |
| **Vibe** | Texting a colleague | Assistant who reads every brief | Engineer with a clean window | Engineer co-building with you |
| **Primary use** | Thinking & content | Files & workflows | Unified experience | Code & systems |

## When to Use Each

**Chat:**
- Draft an email or rewrite a paragraph
- Roleplay as VP and challenge your proposal
- Simulate customer objections
- Summarize a 30-page report

**Cowork:**
- Research a topic → finished `.docx` in your folder
- Extract tables from 50 PDFs (sandboxed VM — can't break system)
- Prep board decks, contracts, invoices (runs in background)
- Draft replies to unreplied Slack DMs daily (`/schedule` persists across restarts)

**Code:**
- Turn a PRD into a working prototype (plans tasks, spawns subagents)
- Refactor legacy code across a whole repo (git, bash, Plan Mode)
- Start on laptop, continue from phone (`/rc`)
- Run a long task with zero local setup (`claude.ai/code`)

## Key Differences

| Capability | Chat | Cowork | Code Tab | Code CLI |
|---|---|---|---|---|
| Sub-agents (parallel) | — | Parallel sub-agents | Task tool (up to 10) | Task tool + custom agents |
| Scheduled tasks | — | `/schedule` (persistent) | `/schedule` (persistent) | `/loop` (3-day, in-session) |
| Cross-session memory | Built-in | Via instructions/tools | Auto `MEMORY.md` | Auto `MEMORY.md` |
| Custom skills (filesystem) | — | — | `~/.claude/skills/` | `~/.claude/skills/` + `.claude/skills/` |
| Project-scoped MCPs | Global only | Global only | Global only | Per-project via `.mcp.json` |
| Source control | — | Separately | Separately | Integrated |
| File output | Downloadable artifacts | Delivered to folder | Direct filesystem | Direct filesystem |
| Bash / shell access | Desktop Commander MCP | Native in VM | Native | Native |

## Shared DNA

All surfaces share:
- Same models (Opus, Sonnet, Haiku)
- Extended thinking
- Skills (in Cowork + Code)
- MCP — Gmail, Slack, Notion, Figma, Pipedream (1,000+ APIs)
- CLAUDE.md carries over between surfaces

**Config file note:** Chat/Cowork use `claude_desktop_config.json`. Code Tab shares that file plus `~/.claude.json`. Code CLI uses `~/.claude.json` (global) or `.mcp.json` (project). Adding an MCP to one doesn't make it available in others.

## Common Mistakes

- **Putting everything in CLAUDE.md** — keep it lean. Refer to other files or use rules/ for scoped context
- **Using Opus for everything** — route model by task complexity (see [token-efficiency.md](token-efficiency.md))
- **Staying in Chat** — Cowork and Code unlock parallel work, real file output, persistent schedules

## The Learning Curve

```
Chat → Cowork → Code
 33%    66%     100%
```

Not everyone needs Code. If you've used Cowork, you're already 70% of the way there.

## Power Combos

**Cowork `/schedule` + Code `/loop`:** Cowork handles persistent daily crons (survives restarts). Code `/loop` handles in-session monitoring. Same connectors, same CLAUDE.md.

**Remote Control + Web Sessions:** `/rc` gives phone access to your local session. `claude.ai/code` runs long tasks in the cloud with zero setup.

## Free Resources

**Skill repos:**
- `anthropics/knowledge-work-plugins`
- `travisvn/awesome-claude-skills`
- `phuryn/pm-skills`

**Free courses (anthropic.skilljar.com):**
- Claude 101
- Claude Code in Action
- Introduction to MCP
- Introduction to Agent Skills

## Where Used

- Applicable to all Claude-based workflows
