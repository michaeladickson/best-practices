FIRST: If review-context.md exists, read it for project context and intentional
design decisions. Follow it strictly — do NOT flag intentional decisions.
ALSO: Read existing-issues.md if present — do NOT report findings already tracked there.

---

Perform an **agent action-safety self-assessment** of this repository. The goal is to
find places where an AI agent (Claude Code, a scheduled Python agent, a Gemini/LLM call,
or an MCP tool) can take a real-world action — move money, write to the database or
QuickBooks, delete data, send an outbound message, deploy — without an adequate control
layer between the inference and the effect. The failure mode to hunt: an action that
executes on *implied* approval rather than an *explicit*, gated decision.

Do two things:

**Part A — Inventory the actions.** Find every place an agent/LLM can cause a side
effect. Look at: MCP servers (`.mcp.json` + their tool definitions — which expose
*writes*?), scheduled/cron agents and their permissions, any `subprocess`/API client
that writes (QBO, DB, Slack/email/SMS, GitHub, deploy scripts), tool/allow-lists in
`settings.json`, and agent prompts that grant capabilities. Build a short table:
action → tier (read-only / reversible-write / irreversible-or-high-blast) → what gates
it today.

**Part B — Grade the gating.** For each area below: state the current state, grade it
**Good / Gap / Missing**, and give a concrete fix with the file/path.

1. **Action classification** — Is there an explicit notion of which actions are
   irreversible / high-blast-radius (money, deletes, prod/GL writes, outbound messages,
   deploys) vs. safe? Or are all tools treated alike?

2. **Least privilege / read-only by default** — Do agents hold only the capability they
   need? Are writes a separate, explicitly-granted path — ideally enforced in code (e.g.
   the agent-facing MCP exposes no write tools) rather than only asked for in a prompt?

3. **Judge layer / gate before execution** — Is there a check (policy rules or a
   dedicated reviewer) between "agent proposes action" and "action executes" that returns
   an explicit approve/reject/escalate? Or can a single inference reach execution?

4. **Human-in-the-loop for irreversible actions** — Do money movement, deletes,
   prod/GL writes, outbound sends, and deploys require explicit human approval? Is the
   approval surface designed to avoid rubber-stamping (gate only what matters)?
   (HIGH weight — money/data-loss/outbound gaps rank High.)

5. **Authorization spec & limits** — For high-stakes actions, is there a defined
   who/what-may-do-this, with limits (amount thresholds, allow-lists, rate limits)?

6. **Fail-safe on uncertainty** — If an agent can't confirm a precondition, does it
   halt and escalate, or proceed on a guess? Is destructive/operational context
   externalized (CLAUDE.md / rules) so the agent knows what's load-bearing?

7. **Independent verification of effect** — After an action, is its effect verified from
   an independent source (re-query, returned status, row count) rather than trusting the
   agent's self-report? Any sign the system believes "I did it" without proof?

8. **Audit trail & provenance** — Is every agent action logged with inputs, the gate's
   decision + reason, approver, and result? Can you reconstruct what an agent did and why?
   Are AI-proposed vs. human-approved actions distinguishable?

Reference standard: `best-practices/practices/ai-safety/agent-action-safety.md`.
This complements `reviews/ai-slop-review.md` (which covers the *code* an agent writes);
focus here on *runtime actions*, and don't duplicate its findings.

Format your findings as a markdown document with:
- The Part-A action inventory table (action → tier → current gate).
- A one-line scorecard: count of Good / Gap / Missing across the 8 areas.
- Findings grouped by priority (High / Medium / Low) — irreversible-action and
  human-in-the-loop gaps rank High.
- Each finding: area number + name, current state, grade, concrete fix with file/path,
  and the file/tool/commit that prompted it.
- Use markdown checkboxes so items can be tracked.

Output ONLY the findings, no title or preamble.
