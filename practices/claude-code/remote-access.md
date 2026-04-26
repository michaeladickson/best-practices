# Claude Code Remote Access

Four ways to use Claude agents remotely. They're complementary, not alternatives.

> "I code in Claude Code + several Web Sessions running in parallel." — Boris Cherny, Anthropic

## The Four Methods

### Web Sessions (Oct 2025)
Hosted in the cloud — the only method that doesn't need your laptop.

```bash
# Via browser
open https://claude.ai/code

# Via terminal
claude --remote
```

**Use when:** Fire-and-forget long tasks. Connect to any GitHub repo from any device.

**Limitations:** No local files or Desktop Commander. Sessions can be orphaned (known bug).

---

### Remote Control (Feb 2026)
Your phone becomes a window into your running terminal session.

```bash
# In your Claude Code terminal
/rc
# Scan the QR code with your phone
```

**Use when:** Quick check on a running session. Full local access — git, bash, everything.

**Limitations:** Session must already be running. Can't start new work.

---

### Dispatch (Mar 17, 2026)
A walkie-talkie for Cowork. Start new tasks from phone or any browser.

**Setup:**
1. Open Claude Desktop → Cowork → click Dispatch in left sidebar
2. Toggle "Keep awake" on (without it, Dispatch stops when your computer sleeps)
3. Open Claude mobile app → tap Dispatch in sidebar

**Use when:** Run parallel tasks remotely. Gmail, Slack, Notion connectors built in.

**Gotchas:**
- Desktop must stay awake — enable "Keep Awake" in Cowork settings
- Can't attach files or copy text from mobile — email workaround: email file to yourself, tell Dispatch to pull via Gmail connector
- No folder picker on mobile — describe path like `~/Desktop/Workspace`
- CLAUDE.md not auto-loaded — ask Dispatch to read it before delegating tasks, or subtask instructions will be imprecise ("telephone game" effect)

**Pattern:** `You (phone) → Read CLAUDE.md first → Orchestrator (context loaded) → Sharp subtasks`

---

### Channels (Mar 19, 2026)
Bidirectional bridge between Telegram/Discord and a live Claude Code session.

```bash
# Configure Telegram/Discord bot, then:
claude --channels
```

**Use when:** Automated monitoring, webhooks, event-driven workflows.

**Limitations:** Can't start new sessions. Can't approve permissions from the app.

---

## Comparison

| | Web Sessions | Remote Control | Dispatch | Channels |
|---|---|---|---|---|
| Works without laptop | ✓ | — | — | — |
| Start new sessions | ✓ | — | ✓ | — |
| Full machine access | — | ✓ | ✓ | ✓ |
| AI coding | ✓ | ✓ | knowledge work | ✓ |
| Scheduled tasks | ✓ (web-only) | — | ✓ | ✓ (active sessions only) |

## Shared Foundation: GitHub Repo as Knowledge Store

All surfaces pick up your knowledge automatically when stored in a GitHub repo.

```
your-repo/
  CLAUDE.md          # instructions file — voice, rules, workflow
  knowledge/         # research, facts, patterns
  articles/          # references
  tools/             # scripts
```

Web Sessions clone the repo. Everything else reads it from your machine.

## Power Combos

**Persistent cron + in-session monitoring:**
- Cowork `/schedule` — persistent daily cron that survives restarts
- Code `/loop` — in-session monitoring/recurring tasks (3-day expiry)
- Both use the same CLAUDE.md and connectors

**Work from anywhere:**
- `/rc` for full machine access from phone (session must be running)
- `claude.ai/code` for long cloud tasks with zero setup

## Where Used

- Applicable to any Claude Code or Cowork setup
