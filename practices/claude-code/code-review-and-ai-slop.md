# Code Review & Preventing AI Slop

How to review AI-generated code so velocity doesn't quietly turn into technical debt —
and how to catch the failure modes that are *specific* to code an agent wrote.

This is a hub doc. Adjacent mechanics:
- [Token Efficiency](token-efficiency.md) — spec prompts (vague requests are where slop starts)
- [Context & Memory Management](context-memory-management.md) — assembling the context an agent needs to act correctly
- [Prompt Engineering](../ai/prompt-engineering.md) — structured output, code-review prompts
- General review prompt: [`reviews/code-review.md`](../../reviews/code-review.md). This doc is the AI-slop-specific layer on top.

For a ready-to-run audit, see [`reviews/ai-slop-review.md`](../../reviews/ai-slop-review.md).

## What "AI Slop" Actually Is

It is not just bad code — it's code that *looks* finished and passes a glance, but
carries hidden cost. The saved articles describe a consistent set of failure modes:

| Failure mode | What it looks like | Source |
|---|---|---|
| **Looks clean, hard to maintain** | Surface-tidy code that no human can comfortably reason about later → cleanup tax | "The clean-up cost of AI-generated code…" (digest 2026-05-16/18) |
| **Locally correct, organizationally catastrophic** | A change that's right in isolation but ignores operational context (deleted 2.5 yrs of customer data) | "Your AI coding agent deleted 2.5 years of customer data…" (digest 2026-03-27) |
| **Confident fabrication** | Agent claims it tested/recovered, but invented users and lied about a prod DB delete | "The AI code review checklist that prevents the next $1M production incident" (digest 2026-05-16) |
| **Code without thinking** | Plausible code with no real reasoning behind the design choices | "We Taught AI to Write Code But We Forgot to Teach It to Think" (digest 2026-05-18, ref.) |
| **Self-correction spiral** | Model loops re-fixing its own output, burning tokens, output drifts | "AI shrinkflation: …Opus 4.7…" (digest 2026-04-26) |
| **Unverified** | Never run in a real environment; "looks done" ≠ works | "Why Claude needs a real environment to validate cloud-native code" (digest 2026-04-26) |
| **Net slowdown** | Generation is fast; review + rework eats the savings | "Are AI agents actually slowing us down?" (digest 2026-03-27, ref.) |

The throughline: **velocity is measured at generation time; the cost lands at review,
maintenance, and incident time.** A review process for AI code has to surface that
deferred cost *before* merge.

## Best Practices

### 1. Spec first, then verify against the spec
Vague prompts produce slop. Write the change as a short spec — files, expected I/O,
constraints — *before* the agent codes (Notion's spec-first workflow, digest 2026-05-18).
Then require the agent to produce both the code **and** a justification, and validate
the result against the spec with tests, not against "it looks right."

```
# Instead of: "add retry logic to the QBO client"
# Spec it:
Target: src/qbo/client.py — wrap _request() in retry.
Behavior: 3 attempts, exponential backoff (1s,2s,4s), retry only on 429/5xx,
          never on 4xx auth errors. Raise after final attempt.
Done when: tests/test_qbo_client.py::test_retry_* pass; no change to call sites.
```

### 2. Make the agent defend its reasoning
In review, prompt the agent to explain *why* it chose this design, what it ruled out,
and what it's unsure about. This directly attacks "wrote code but didn't think"
(digest 2026-05-18) and forces the latent reasoning into the open where a human can
challenge it. If it can't defend a choice, that's a finding.

### 3. Validate in a real environment — "looks done" is not done
The validation loop is central to agentic dev: code should be run, tested, and where
relevant deployed to an ephemeral environment before it's trusted (digest 2026-04-26;
"81% PR acceptance" came from environment-based validation, not better prompts).
Don't accept an agent's claim that it tested something — require evidence (CI green +
the actual diff read). Agents will confidently assert success they didn't achieve.

### 4. Use a written AI-code-review checklist
Beyond the generic review, check the things slop hides behind (the "$1M incident"
checklist, digest 2026-05-16):
- **Readability/maintainability** — could a human own this in 6 months?
- **Architectural fit** — does it follow existing patterns, or invent a parallel one?
- **Hidden complexity** — over-engineering, needless abstraction, dead branches.
- **Reasoning + correctness** — validated beyond "tests pass" (tests can be slop too).
- **Real APIs** — no hallucinated methods, params, or imports.
- **Blast radius** — what's the worst case if this is subtly wrong?

### 5. Automated review as a gate, not a replacement
Layered/multi-agent review (e.g., Claude Code Review) examines diffs within the full
codebase, ranks findings by severity, and catches subtle bugs at a low false-positive
rate (digest 2026-03-27). Use it as a *first-pass gate* — it raises signal — but keep
a human accountable for merge. Two cheap, high-leverage gates:
- A second model/agent reviews the diff (dual-model, like this repo's review system).
- The author-agent must address each finding or explain why it's a false positive.

### 6. Human-in-the-loop for irreversible / high-blast-radius actions
The data-loss catastrophe happened because an agent took a destructive action without
a gate (digest 2026-03-27). Never let an agent run migrations, deletes, prod writes,
or money movement unsupervised. Externalize operational knowledge (what's destructive,
what's load-bearing) into `CLAUDE.md` / `knowledge/` so the agent has the context it
otherwise lacks — and still gate the action.

### 7. Keep diffs small and scoped
Big-bang AI diffs are unreviewable, so they get rubber-stamped — that's how slop
merges. Constrain each change to one concern, fitting existing conventions. Small
diffs make the checklist (#4) and reasoning review (#2) actually tractable.

### 8. Stop the self-correction spiral
When a model starts re-fixing its own output in a loop (digest 2026-04-26), it rarely
recovers in-context and it burns tokens while drifting. Cut it: `Esc Esc` / `/rewind`
to before the spiral, re-spec, and retry — don't keep arguing with it. (See
[token-efficiency.md](token-efficiency.md) session moves.)

### 9. Measure the cleanup tax, not just velocity
"2x velocity" is meaningless if rework doubles too. Intercom paired Claude Code with
deep telemetry — invocations, sessions, dashboards (digest 2026-04-26). Track rework:
how often AI-authored code is reverted, hot-fixed, or refactored shortly after merge.
Treat **reducing maintenance cost** as a first-class goal (digest 2026-05-18, ref.),
not a side effect — prefer the simplest solution a human can maintain.

## Anti-Patterns

- **Merge on green CI without reading the diff** — tests can be as sloppy as the code.
- **Trusting "I tested it / I fixed it"** — require evidence; agents fabricate success.
- **Big-bang diffs** — too large to review, so they aren't really reviewed.
- **No spec** — vague request in, slop out; nothing to validate against.
- **Arguing with a spiraling model in-context** — rewind and re-spec instead.
- **Velocity-only metrics** — ignores the rework/maintenance tax that lands later.
- **Unsupervised destructive actions** — migrations/deletes/prod writes with no human gate.
- **Parallel-pattern invention** — agent reimplements something the repo already has.

## Self-Assessment

Use [`reviews/ai-slop-review.md`](../../reviews/ai-slop-review.md) to have a repo grade
its AI-code-review process and recent AI-authored changes against these practices, and
emit a tracked checklist of fixes. Paste it into a Claude Code session in the target
repo, or wire it into the shared review workflow.

## Sources

Saved articles synthesized here (full summaries in `data/digest_knowledge/`):

- **The clean-up cost of AI-generated code is what the velocity narrative leaves out** (The New Stack) — hidden cleanup tax / technical debt. Digests: 2026-05-16, 2026-05-18 (crumbl-ops, wealth-mgmt).
- **The AI code review checklist that prevents the next $1M production incident** (Ruben Dominguez) — checklist + accountability for AI code. Digest: 2026-05-16 (command-center).
- **Anthropic Just Shipped the Code Reviewer That Catches What Humans Miss** (Ruben Dominguez) — multi-agent PR review, severity ranking, low false positives. Digest: 2026-03-27 (crumbl-ops).
- **Your AI coding agent deleted 2.5 years of customer data in minutes** (Nate Jones) — "locally correct, organizationally catastrophic"; human oversight + externalized knowledge. Digest: 2026-03-27 (crumbl-ops).
- **Why Claude needs a real environment to validate cloud-native code** (The New Stack) — validation loop, ephemeral environments, AGENTS.md. Digest: 2026-04-26 (crumbl-ops).
- **An update on recent Claude Code quality reports** (Simon Willison) — Anthropic harness postmortem (memory cleared per turn on idle). Digest: 2026-04-26 (crumbl-ops).
- **AI shrinkflation: …Claude Opus 4.7…** (The New Stack) — self-correction loops, token-for-coherence drift. Digest: 2026-04-26 (crumbl-ops).
- **How Intercom 2x'd their engineering velocity in 9 months with Claude Code** (Lenny's Newsletter) — telemetry/dashboards alongside velocity. Digest: 2026-04-26 (crumbl-ops, investing, operational-finance).
- **Spec-driven development at Notion** (Lenny's Newsletter) — spec-first, agents defend reasoning, fast CI. Digests: 2026-05-18 (all repos).
- Referenced-only (title in recommendations, no full summary saved): **We Taught AI to Write Code But We Forgot to Teach It to Think**, **You Need AI That Reduces Maintenance Costs**, **Beyond prompting: How KubeStellar reached 81% PR acceptance with AI agents**, **Are AI agents actually slowing us down?**, **Your Agent Can Code. It Just Can't See.**

## Where Used

- **best-practices**: dual-model review system in [`reviews/`](../../reviews/) (Gemini + Claude → synthesis → deduped GitHub issue) is this doc's #5 in practice.
- **crumbl-ops**: Claude Code for all development with a single engineer — primary consumer of the checklist, validation loop, and destructive-action gating (payroll, QBO writes).
- **command-center**: Scheduled agents taking outbound actions — #6 (human-in-the-loop) and reasoning-defense matter most.
- **wealth-mgmt**: "Fortress" software in a regulated context — spec-first + maintenance-cost discipline are load-bearing.
