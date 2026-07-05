# Model-Hierarchy Delegation

How to route work across Fable / Opus / Sonnet / Haiku so the expensive model
does the thinking, cheaper models do the running-around, and you stop paying
frontier prices for mechanical work.

Adjacent mechanics:
- [Token Efficiency](token-efficiency.md) — session hygiene, cache, model routing. This doc sits *inside* a session; token-efficiency covers the session shell.
- [Context & Memory Management](context-memory-management.md) — subagents as a *context* budget tool. This doc names *what to delegate*, not just *that you can*.
- [Code Review & Preventing AI Slop](code-review-and-ai-slop.md) — never delegate the *review* of an agent's writes. That's the judgment layer.

For a ready-to-run audit, see [`reviews/model-hierarchy-review.md`](../../reviews/model-hierarchy-review.md).

## The Core Idea: Brain vs. Hands

The frontier model's judgment is the value — including its judgment about *what not to think through*. Jesse Vincent (Claude Code team, quoted by Simon Willison, digest 2026-07-03): *"Tell Fable to use other models for smaller tasks, applying its own judgement about which model to use."* The crisp version: *"For all coding tasks use your judgement to decide an appropriate lower power model and run that in a subagent."*

The **anti-pattern this replaces** is two-headed: (a) over-prescribing a workflow to Fable so it can't route on its own, and (b) using Fable for every read, grep, and mechanical verification just because the session is on Fable. Willison's higher-order framing: *let the frontier model use its own judgement about **how** to work, not just **what** to do.* Over-prescription removes the very judgment that makes delegation work.

## The Tier Rules

Anchored in the Claude Code team's own guidance (via Willison, digest 2026-07-03) plus Paweł Huryn's tiering (digest 2026-06-11) and Nate Jones' "daily driver / workhorse / frontier" split (digest 2026-07-02).

| Tier | Do this here | Why |
|---|---|---|
| **Fable / Opus** (parent loop) | Planning, hard trade-offs, review, synthesis, authoring judgment | Reasoning depth and cross-context judgment can't be delegated without losing fidelity |
| **Sonnet** (subagent) | Substantive implementation, scoped research, batch reads, focused verification passes | Strong reasoning at roughly one-third the cost; can produce structured returns the parent reviews |
| **Haiku** (subagent) | Trivial / mechanical edits, file-exists / line-count / list-dir, format normalization | Near-free for work with no judgment content |

## Best Practices

### 1. Delegate mechanical and scoped work; keep judgment in the parent
The parent decides *which* skills to author, *whether* a finding is real, *how* a change fits the architecture. A subagent does *"read these four files and return the DocNumber assertion location"* or *"verify each of these 12 commands runs without error and return `{command, ok, error}`."* If a subtask can be defined by a fixed input and a **structured** output, it can probably be delegated.

### 2. Give the parent a rule, not a script
Tell the parent the tier table above and let it route. Vincent's version: *"use your judgement to decide an appropriate lower power model."* Prescribing which model to spawn where kills the judgment that makes delegation win.

### 3. Depth cap: 2. Team cap: small.
One subagent tier under the parent — no nesting further. Depth-3+ orchestrations compound spawn overhead and lose reviewability. Small teams (≤ ~5 concurrent) match Anthropic's Claude Code cost docs: *"keep teams small, shut down teammates when they are done."*

### 4. Shutdown discipline
Every subagent shuts down as soon as its structured return lands in the parent. Long-lived teammates burn tokens and drift; short-lived ones are what make the economics work.

### 5. Structured returns, never free-form prose
Subagents return JSON or terse markdown against a small schema the parent can review at a glance. Free-form returns force the parent to re-read the raw material the subagent already consumed — that defeats the whole point of delegating.

### 6. Never delegate the judgment layer
The parent keeps: authoring decisions, drop / merge / route decisions, the final synthesis, and anything touching money movement, prod writes, deletes, or outbound comms. Subagents produce inputs to the parent's judgment; they never *perform* it.

### 7. Log the delegation trail
Record each spawn: subagent model, task summary, structured return. That's what makes the tree auditable, and what lets you retro whether the delegation ratio is actually cost-effective for this repo instead of a comforting story.

### 8. Watch for spawn-overhead-dominates
Every subagent spawn has fixed cost (context load, prompt, roundtrip). For very small tasks — *does this file exist* — inline is cheaper than delegating. Rule of thumb: if the task's own tokens are less than about 10× the spawn overhead, do it inline in the parent.

### 9. Swap on purpose, for cost
Anthropic's safety mechanism swaps a Fable session to a lower tier when it detects unsafe content. Paweł Huryn's inversion (digest 2026-06-11): *"we can swap on purpose, for cost."* Explicitly drop the session tier when the remaining work is mechanical; explicitly raise it before the next judgment-heavy stretch.

## Anti-Patterns

- **Fable-does-everything** — using the frontier model for greps, reads, and verifications because the session is on it.
- **Prescribing the delegation** — a rigid "always spawn N Sonnets for X" removes the parent's judgment.
- **Nested subagent trees** — depth-3+ orchestrations that lose reviewability and compound overhead.
- **Long-lived teammates** — subagents kept alive across tasks, accumulating stale context.
- **Free-form returns** — subagent output that forces the parent to re-read the raw material.
- **Delegating judgment** — pushing "should I write this skill" or "is this finding real" down the tree.
- **Delegating money/writes** — a subagent never gets destructive-action authority; the parent stays in the loop.
- **Tiny-task delegation** — spawning for `test -f`. The spawn overhead is the whole cost.

## Self-Assessment

Use [`reviews/model-hierarchy-review.md`](../../reviews/model-hierarchy-review.md) to have a repo grade its delegation discipline against this rubric and emit a tracked checklist. Paste it into a Claude Code session in the target repo, or wire it into the shared review workflow.

## Sources

Saved articles synthesized here (full summaries in `data/digest_knowledge/`), and the Claude Code team's own guidance:

- **Simon Willison — "Fable's judgement"** (2026-07-03) — the anchor; direct quotes from Jesse Vincent (Claude Code team) plus Cat Wu and Thariq Shihipar on Sonnet-for-implementation / Haiku-for-mechanical / Fable-keeps-judgment. [simonwillison.net/2026/Jul/3/judgement/](https://simonwillison.net/2026/Jul/3/judgement/)
- **Paweł Huryn — "Claude Fable 5: The Ultimate Guide for PMs v2"** (2026-06-11, The Product Compass) — depth-limit experiments, "swap on purpose for cost" pattern, delegation-and-escalation `CLAUDE.md` snippet. Free preview + paid deep-dive.
- **Nate Jones — "Stop paying frontier prices for work a cheaper AI would crush"** (2026-07-02, Nate's Newsletter) — "daily driver / workhorse / frontier" tier framing and a model-picker prompt.
- **Anthropic — Claude Code cost docs** (cited by Willison): keep teams small, shut down teammates when done.

## Where Used

- **best-practices** — the crumbl-ops Fable skill-distillation prompt at [`prompts/fable-skill-distillation-crumbl-ops.md`](../../prompts/fable-skill-distillation-crumbl-ops.md) applies this rule set to the specific case of authoring skills.
- **crumbl-ops** — heaviest immediate impact. Fast wins: delegate the code-time reads/greps a Fable or Opus session does; downshift the tail of long sessions to Sonnet once the judgment stretch is done. The dual-model weekly review is already a delegation network — the tier rules formalize which model does which review.
- **command-center** — the agent fleet is already a delegation network; this formalizes what's currently ad-hoc.
- **wealth-mgmt** — research and investment-thesis work benefit from the parent-judgment / subagent-reading split; ground-truth verification passes can go to Sonnet.
