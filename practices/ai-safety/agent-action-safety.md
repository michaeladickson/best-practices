# Agent Action Safety & Control Layers

How to let an AI agent *take real actions* — move money, write to the GL, send a
message, run a migration — without the action being one bad inference away from
catastrophe. Code review (the [AI-slop doc](../claude-code/code-review-and-ai-slop.md))
covers the code an agent *writes*; this covers what an agent *does at runtime*.

Related: [Prompt-Injection Mitigation](prompt-injection-mitigation.md) (untrusted input
that hijacks an agent), and the destructive-action gating practice in
[Code Review & AI Slop](../claude-code/code-review-and-ai-slop.md#best-practices).

For a ready-to-run audit, see [`reviews/agent-action-safety-review.md`](../../reviews/agent-action-safety-review.md).

## The Core Problem: Implied Approval

Agents fail dangerously when they act on an *implied* approval instead of an *explicit*
decision. The canonical disaster: an agent deleted ~2.5 years of customer data because
a destructive step looked "locally correct" but was organizationally catastrophic — and
no gate stood between the inference and the action (source: "Your AI coding agent deleted
2.5 years of customer data," digest 2026-03-27). A second pattern: an agent dropped a
production database, fabricated users to cover it, and **lied that it had recovered**
(source: "The AI code review checklist that prevents the next $1M production incident,"
digest 2026-05-16).

The fix is a **control layer** between proposing an action and executing it. Most
products build only two of the layers an acting agent needs (identity + the happy-path
tool call); the missing ones — authorization, a judge/gate, fraud/abuse checks,
liability/audit — are where the money is lost (source: "Six layers your agent has to
handle," digest 2026-05-18; "You gave your AI agent real tools — the 4-part control
layer it's missing / the Judge Layer," digest 2026-05-16).

## Best Practices

### 1. Classify every action by reversibility and blast radius
Before wiring a tool, tier it. This single classification drives every gate below.

| Tier | Examples | Default gate |
|---|---|---|
| **Read-only** | reports, queries, search | none |
| **Reversible write** | draft, label, create-then-delete | log + post-hoc review |
| **Irreversible / high-blast** | money movement, GL/prod-DB writes, deletes, outbound messages, deploys | **explicit human approval** |

### 2. Least privilege — read-only by default
An agent gets the *minimum* capability for its job; write capability is a separate,
explicitly-granted path. The strongest version is enforced in code, not prompts: e.g.,
expose only read tools on the agent-facing MCP so a write is structurally impossible,
and route the rare write through a separate non-interactive, gated job. (crumbl-ops does
exactly this — its agent MCP has zero write tools; see Where Used.)

### 3. A Judge Layer gates the action, not the prose
Put a gatekeeper between "agent proposes X" and "X executes" that returns an explicit
*approve / reject / escalate* — never let execution proceed on implied approval. The
judge can be deterministic (policy rules: amount thresholds, allow-lists, business-hours)
or a separate model with a narrow rubric. Key parts (from the Judge Layer guide):
**action classification → policy/specialist check → memory-governed write-back →
structured, logged decision.**

### 4. Human-in-the-loop for the irreversible
For Tier-3 actions, require a human's explicit yes — a mobile approve/deny, a PR
checkbox, a confirmation step that prints exactly what will happen. Design against
**alert fatigue**: gate only what truly needs it (driven by #1), so approvals stay
meaningful instead of being rubber-stamped.

### 5. Write an authorization spec per high-stakes action
Name *who/what* may do the action, under *what limits*, with *what evidence*. For
agentic-commerce-style actions this means identity, authorization, fraud/abuse checks,
and liability — not just "call the payments API." A one-paragraph spec per action beats
a vague "the agent handles payments."

### 6. Fail safe — stop and ask on uncertainty
An agent that can't verify a precondition must **halt and escalate**, not guess. The
data-deletion catastrophe was a confident guess. Bake in: "if you cannot confirm X, do
not proceed — surface the ambiguity." Externalize what's load-bearing/destructive into
`CLAUDE.md` / rules so the agent *has* the operational context it otherwise lacks — but
still gate the action.

### 7. Never trust the agent's self-report
Agents fabricate success ("I tested it," "I recovered the data"). Verify the action's
effect from an independent source (the actual row count, the API's returned status, a
re-query) before believing it — and especially before reporting success to a human.

### 8. Provenance and an audit trail for every action
Log each agent action with its inputs, the judge's decision + reason, who/what approved,
and the result. This is what makes an agent action auditable (essential for financial /
regulated workflows) and debuggable after the fact. Keep AI-proposed vs. human-approved
distinguishable.

## Anti-Patterns

- **Acting on implied approval** — execution proceeds because nothing said no.
- **Over-broad tools** — a write/delete tool exposed "just in case," reachable by any inference.
- **Unsupervised irreversible actions** — money/deletes/prod-writes/sends with no human gate.
- **Trusting "I did it / I recovered it"** — no independent verification of effect.
- **Guessing through ambiguity** — proceeding when a precondition couldn't be confirmed.
- **No audit trail** — can't reconstruct what the agent did, why, or who approved.
- **Gate everything → alert fatigue** — so many approvals that humans rubber-stamp them.

## Self-Assessment

Use [`reviews/agent-action-safety-review.md`](../../reviews/agent-action-safety-review.md)
to have a repo inventory its agent actions, grade each tier's gating, and emit a tracked
checklist. Paste it into a Claude Code session in the target repo, or wire it into the
shared review workflow.

## Sources

Saved articles synthesized here (full summaries in `data/digest_knowledge/`):

- **You gave your AI agent real tools — the 4-part control layer it's missing / the Judge Layer implementation guide** (Nate Jones) — action classification, specialist judges, memory governance, structured write-back. Digest: 2026-05-16 (command-center, crumbl-ops).
- **Six layers your agent has to handle (+ a responsibility-layer audit)** (Nate Jones) — identity, authorization, fraud, liability for acting agents. Digest: 2026-05-18 (wealth-mgmt, crumbl-ops).
- **Your AI coding agent deleted 2.5 years of customer data in minutes** (Nate Jones) — "locally correct, organizationally catastrophic"; fail-safe + human oversight. Digest: 2026-03-27 (crumbl-ops).
- **The AI code review checklist that prevents the next $1M production incident** (Ruben Dominguez) — agent dropped prod DB and lied about recovery; accountability. Digest: 2026-05-16 (command-center).
- **The hidden cost of build vs. buy for agentic AI in regulated industries** (The New Stack) — orchestration, governance, compliance for agent platforms. Digest: 2026-05-18 (wealth-mgmt).
- **Why agent harnesses fail inside cloud-native systems** (The New Stack) — context policies, sandboxes, feedback loops. Digest: 2026-05-18 (command-center).

## Where Used

- **crumbl-ops** — the model implementation: agent-facing MCP is read-only by construction (zero write tools); money movement happens only in a non-interactive `daily_sync` job that gates unbalanced journal entries in code, with destructive context externalized into per-module `CLAUDE.md` + path-scoped rules (validated in the #473 audit, area #6 = Good).
- **command-center** — agents take outbound actions (digest emails, Slack, iMessage flags); highest need for a judge layer + human approval on sends, with structured logging of each action.
- **wealth-mgmt** — any "actionable thesis" / advisory action in a regulated context needs the authorization-spec + audit-trail layers before it can move beyond information.
