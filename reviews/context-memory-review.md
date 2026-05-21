FIRST: If review-context.md exists, read it for project context and intentional
design decisions. Follow it strictly — do NOT flag intentional decisions.
ALSO: Read existing-issues.md if present — do NOT report findings already tracked there.

---

Perform a **context & memory management self-assessment** of this repository. The
goal is to find where Claude Code and any scheduled/automated agents in this repo
waste context, re-derive known facts, or fail to persist what's worth keeping.

Inspect the actual repo — `CLAUDE.md` (root and per-module), `.mcp.json` /
`settings.json`, `knowledge/`, `decisions/`, `skills/`, `rules/`, `agents/`, any
`docs/` summary files, and the code for scheduled agents (how they gather context
each run). Assess against each area below. For each, state the current state, then
grade it **Good / Gap / Missing**, then give a concrete fix.

1. **Context assembly vs. rediscovery** — Do agents re-grep / re-read the same files
   every run, or is context assembled up front? Is there a Retrieval Contract Spec
   (explicit list of what context each recurring task needs, its format, and source)
   for the main agent workflows? Are there durable summary docs referenced with
   `@file` instead of re-derived?

2. **Memory tiers** — Is transient/session state, project knowledge, and cross-repo
   pattern correctly separated? Anything in `CLAUDE.md`/`knowledge/` that's really
   session-only (bloat), or anything session-only that should have been written down
   (knowledge loss)? Anything repo-specific that's actually a global pattern (belongs
   in best-practices)?

3. **CLAUDE.md leanness** — Is the root `CLAUDE.md` orientation + conventions + file
   map, or is it carrying procedures and domain dumps that should be skills, rules,
   or referenced docs (it loads on every turn)? Flag bloated sections with a smaller
   home.

4. **Session budget hygiene** — Is there guidance (in CLAUDE.md or docs) on `/clear`,
   `/compact`, subagents, and model/MCP locking? Do long-running or scheduled agents
   manage their window, or risk filling it?

5. **Subagent usage** — Are context-heavy subtasks (research, broad search, large
   output) pushed into subagents so only results return, or do they dump bulk into
   the main window?

6. **MCP / harness footprint** — How many MCP servers/tools are connected? Are any
   broad/kitchen-sink or unused (every tool sits in context every turn)? Recommend
   trimming to narrow, single-purpose servers.

7. **Skills library / institutional memory** — Are recurring agent workflows
   formalized as version-controlled skills with clear input/output, or retyped each
   session ("shadow skills")? What should be promoted into `skills/`?

8. **Governed write-back** — Is there a hypothesis→rule promotion path, a decision
   journal (`decisions/*.md` with `Supersedes:` links), and verification dates on
   durable facts? Or do agents/humans mutate knowledge files freely with no
   discipline (memory rot)?

9. **Provenance** — When context is assembled for an agent (especially financial /
   compliance workflows), is each fact tagged with its source so outputs are
   auditable?

Reference standard: `best-practices/practices/claude-code/context-memory-management.md`
(and its siblings `token-efficiency.md`, `claude-md-structure.md`).

Format your findings as a markdown document with:
- A one-line scorecard: count of Good / Gap / Missing across the 9 areas.
- Findings grouped by priority (High, Medium, Low).
- Each finding: area number + name, current state, grade, and a concrete fix with
  the file/path to change.
- Use markdown checkboxes so items can be tracked.

Output ONLY the findings, no title or preamble.
