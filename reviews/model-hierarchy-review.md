FIRST: If review-context.md exists, read it for project context and intentional
design decisions. Follow it strictly — do NOT flag intentional decisions.
ALSO: Read existing-issues.md if present — do NOT report findings already tracked there.

---

Perform a **model-hierarchy delegation self-assessment** of this repository. The
goal is to find places where the app pays frontier prices for work a cheaper
model would crush, or where subagents are used badly (nested, prescribed,
long-lived, free-form returns) so the delegation is losing money instead of
saving it. Judgment stays with the parent; mechanical work delegates down.

Do two things:

**Part A — Inventory the delegation surface.** Find every place the codebase, its
scheduled agents, or its Claude Code sessions actually route work across model
tiers. Look at: any `subprocess.run(["claude", ...])` / `subprocess.run(["gemini", ...])`
calls (check `--model` flags — pinned or floating?), scheduled agents that call an
LLM, `.claude/agents/*.md` if present, `.claude/skills/*/SKILL.md` frontmatter
for `model:` fields, CI workflows that invoke Claude / Gemini (weekly-review,
CFO brief, digest), and any CLAUDE.md / memory guidance about spawning
subagents. Build a short table: **site → what model runs → what task type →
whether the tier matches the work.**

**Part B — Grade the discipline.** For each area below: state the current
state, grade it **Good / Gap / Missing**, and give a concrete fix with the
file/path.

1. **Tier awareness** — Does the repo have a written rule for which tier
   (Fable/Opus / Sonnet / Haiku) handles which kind of work, or is model
   selection ad hoc / defaulted to whatever the session is on?

2. **Parent-judgment / hands-delegation split** — When sessions or agents here
   spawn subagents, do they delegate the *mechanical* parts (bulk reads,
   greps, verifications) while keeping *judgment* (which change to make, is a
   finding real, does this fit) in the parent loop? Or is the top-tier model
   doing mechanical work too?

3. **Let-the-parent-choose** — Are delegation decisions prescribed rigidly, or
   is the parent given a routing rule and left to apply its judgment? Rigid
   prescriptions remove the judgment that makes delegation work.

4. **Depth cap** — Is subagent nesting held to depth ≤ 2 (parent → one
   subagent tier)? Any depth-3+ orchestrations?

5. **Team-size + shutdown discipline** — Are concurrent subagents kept small
   (~≤ 5)? Do subagents shut down as soon as their structured return lands, or
   do long-lived teammates persist and accumulate stale context across tasks?

6. **Structured returns** — Do subagents return JSON / terse markdown against
   a small schema the parent can review at a glance, or free-form prose that
   forces the parent to re-do the mechanical work in review?

7. **Judgment stays with the parent** — Is there any place a subagent
   effectively makes an authoring / drop / merge / destructive decision?
   (HIGH weight — money movement, deletes, prod writes, outbound sends must
   never be delegated below the parent.)

8. **Spawn-overhead awareness** — Are tiny tasks (file-exists, line-count)
   inlined rather than delegated? Or is there overhead-heavy spawning for
   near-zero-token work?

9. **Delegation audit trail** — Is each spawn logged with subagent model,
   task summary, and structured return, so the tree is auditable and the
   delegation ratio can be retro'd for cost-effectiveness?

Reference standard: `best-practices/practices/claude-code/model-hierarchy-delegation.md`.
This complements — do not duplicate — `reviews/context-memory-review.md`
(subagents as a *context* budget tool) and `reviews/llm-eval-review.md`
(which model produces which quality of output). Focus here on *routing
discipline*.

Format your findings as a markdown document with:
- The Part-A delegation-surface table (site → model → task type → tier-fit).
- A one-line scorecard: count of Good / Gap / Missing across the 9 areas.
- Findings grouped by priority (High / Medium / Low) — parent-judgment
  violations and unlogged high-blast-radius spawns rank High.
- Each finding: area number + name, current state, grade, concrete fix with
  file/path, and the file/tool/commit that prompted it.
- Use markdown checkboxes so items can be tracked.

Output ONLY the findings, no title or preamble.
