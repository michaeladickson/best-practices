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

## Start with the Job — Classify Before You Route

Delegation only works if you describe the job before you open a session. Most model choice fails at the wrong step: people ask *"which AI should I use?"* before they've described the job, then get pulled into model discourse (leaderboards, benchmarks, screenshots) and pick from vibes. Nate Jones' rule (digest 2026-07-02): **Describe the job first, then pick the intelligence.**

Before opening a session, ask:

1. **Familiar or ambiguous?** Can you describe what "good" looks like before the model starts?
2. **Fast to inspect?** Can you check the result quickly, or is review expensive?
3. **Sensitive data?** Do customer records, financial data, legal drafts, code, health info, HR material, or unreleased product plans belong in this session's model?
4. **Special inputs?** Audio, screenshots, video, PDF, live web, or repo access?
5. **Actions?** Does the system need to act — edit files, run tests, move through a browser, generate media?
6. **Portable context?** Does the source material live somewhere the model can use, or are you about to spend ten minutes re-pasting yesterday's background?

The answers route the work more reliably than the model card. **The core decision rule** (Jones): *"Use the cheap model when you know the artifact and can inspect the result. Use the frontier model when the artifact itself is part of the problem."*

## The Tier Rules

Anchored in the Claude Code team's own guidance (via Willison, digest 2026-07-03) plus Paweł Huryn's tiering (digest 2026-06-11) and Nate Jones' "daily driver / workhorse / frontier" split (digest 2026-07-02, read via subscriber PDF).

| Tier | Open when… | Do this here | Concrete examples |
|---|---|---|---|
| **Frontier** (top-tier Fable / Opus) | *the artifact itself is part of the problem* | Discovering the shape of an unfamiliar problem; cross-domain synthesis; taste-heavy authoring where the cost of being directionally wrong is high | Product-strategy discovery; a "Fable-style" question where a new capability's implications aren't yet clear; high-stakes legal / customer / strategy calls |
| **Daily driver** (your trusted broad model + harness) | *the task shape isn't clean yet* | Breadth for unclear work — figuring out whether the job is writing, reasoning, planning, editing, coding, researching, or some mix. Reduces friction: reads files, edits files, shows diffs, runs commands, leaves inspectable output | Messy source-bundle synthesis; taste + judgment work; anywhere Codex / Claude Code / a strong chatbot is your primary work surface |
| **Cheap workhorse** (Sonnet, "fat-middle" models) | *you can describe good before the model starts and review is fast* | Familiar artifacts under time pressure | Slide outlines, landing pages, meeting summaries, first-pass proposals, support replies, standard code changes, well-scoped tests, CRM cleanups |
| **Mechanical** (Haiku-class subagent) | *sub-token-scale ops with no judgment content* | Trivial / mechanical edits, file-exists / line-count / list-dir, format normalization | Near-free — but delegate only when task tokens exceed spawn overhead (rule of thumb: ~10×) |
| **Specialist** (harness/model built around a sense, source, or action) | *the job needs eyes, live data, or hands more than raw reasoning* | See the next section | Transcription for calls; Grok for X-native queries; a coding harness with repo context, tests, and reviewable diffs |

## Specialists: Senses, Sources, Actions

Some jobs need a **specialist** more than a smarter general model. *"The model matters less than the harness once a job needs eyes, live data, or hands"* (Jones, digest 2026-07-02):

- **Senses** — audio transcription, video parsing, screenshot / image inspection, PDF or spreadsheet formats your default model handles badly. If your business is calls, transcription may matter before another chatbot subscription.
- **Sources** — live web, X, CRM, archive search, transcript databases, repo access. If the job depends on current information or a specific corpus, the harness with that stream wins even when the underlying model is weaker. *Treat live answers as first passes and verify current claims.*
- **Actions** — edit files, run tests, browse, generate media, produce a reviewable diff. Coding illustrates the trap: teams collapse the *model* and the *harness* into one thing. GLM 5.2 can be strong at code, but code work depends on the work surface giving the model repo context, file access, tool calls, tests, diffs, memory, and review. *"The model only becomes useful when the harness can give it the files, tools, and checks."*

At work, **permission comes first.** Customer data, financial data, legal drafts, code, health info, HR material, and unreleased product plans stay in approved tools regardless of which tier is cheaper — routing a sensitive artifact to a random model API "because someone online said it was cheaper" is shadow IT with a benchmark attached.

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

### 10. The model-picker prompt — classify before executing
Nate Jones' habit-forming prompt makes classification automatic. Paste it into any chat window for a routing call *before* you start the real work:

    I need to choose the right AI tool for this task.

    Task:
    Describe the actual work here.

    Source material:
    List the files, links, notes, transcripts, screenshots, repo, customer context, and data.

    Constraints:
    Name any sensitive data, company policy, deadline, quality bar, or allowed-tool constraint.

    Please classify the task before answering:

    1. Is this work unclear, mixed, taste-heavy, risky, or hard to inspect? If yes, recommend a daily-driver/frontier route and explain why.
    2. Is this work familiar, structured, repeatable, and easy to review? If yes, recommend a cheap-workhorse route and define the review checklist.
    3. Does this work need a specific sense, source, or action: audio, screenshots, video, live web, archive search, image generation, browser action, repo access, tests, or file edits? If yes, name the specialist capability required.
    4. Is any data restricted by company policy, customer confidentiality, legal sensitivity, HR sensitivity, health information, financial data, unreleased product plans, or code security? If yes, keep the task inside approved tools or ask for a safer route.
    5. What context packet should travel with the task: personal preferences, examples, checklist, transcript, customer notes, screenshots, repo files, prior decisions, or success criteria?
    6. What would prove the output is good enough to accept?
    7. What failure mode should I watch for?

    Then recommend the simplest route for this task.

Quoted with attribution from Nate Jones, *"Stop paying frontier prices…"* (paid), [natesnewsletter.substack.com/p/which-ai-model-to-use](https://natesnewsletter.substack.com/p/which-ai-model-to-use). **Why it works:** it forces classification *before* execution — the habit that closes the money leak.

### 11. Test the cheap route on your own work
Benchmarks tell you a model deserves attention; only *your* work tells you whether it should run your proposal workflow, codebase, or research process. Jones' protocol:

- **30-minute version.** Pick one recurring artifact. Run it through your daily driver *and* one cheaper route. Time the review. Mark the output usable / repairable / rejected. Write down the failure mode (missed facts, flattened voice, lost structure, hallucination, or basically-right-but-slow-to-clean).
- **One-week version.** Choose five recurring artifacts. Test each twice. Track model, source material, review minutes, accepted output, sensitive-data constraint, and failure mode. Promote the cheap route only where **review stays cheap** — *"a cheap model that saves money and doubles review time is expensive."*

### 12. Keep context portable; separate personal memory from job context
Every model has its own private history with you (Claude remembers one thing, ChatGPT another, your coding agent knows the repo for a while, your image tool knows the prompt but not the project). If all of that stays separated by product, you become the router by hand — which is exhausting. Jones' split:

- **Personal memory** — preferences, taste, standards, recurring projects.
- **Job context** — source material for the task (transcript, file, examples, requirements, customer notes, repo, prior decision, checklist).

The more job context lives in files, folders, search, embeddings, project notes, and harnesses — not in one product's memory — the less any single model's memory dictates routing. *"Give a bounded worker the right packet of context."* Rent the intelligence you need; keep the context that makes the work yours.

## Anti-Patterns

- **Fable-does-everything** — using the frontier model for greps, reads, and verifications because the session is on it.
- **Prescribing the delegation** — a rigid "always spawn N Sonnets for X" removes the parent's judgment.
- **Nested subagent trees** — depth-3+ orchestrations that lose reviewability and compound overhead.
- **Long-lived teammates** — subagents kept alive across tasks, accumulating stale context.
- **Free-form returns** — subagent output that forces the parent to re-read the raw material.
- **Delegating judgment** — pushing "should I write this skill" or "is this finding real" down the tree.
- **Delegating money/writes** — a subagent never gets destructive-action authority; the parent stays in the loop.
- **Tiny-task delegation** — spawning for `test -f`. The spawn overhead is the whole cost.
- **Opening the wrong tier by default** — reaching for the same model out of habit before describing the job. That's where the money leaks.
- **Cheap-route without review economics** — moving to a cheaper model without measuring whether review time inflates faster than token cost falls.
- **Collapsing model and harness** — thinking *"use GLM for code"* when what wins/loses is whether the harness gives the model repo context, tool calls, tests, and a reviewable diff.
- **Frontier by default for repeat work** — using the frontier model on every recurring artifact when the shape is legible enough to delegate.
- **Ignoring the permission filter at work** — routing customer / financial / legal / HR / code / unreleased-product data to an unsanctioned model because it's cheaper. Shadow IT with a benchmark attached.

## Self-Assessment

Use [`reviews/model-hierarchy-review.md`](../../reviews/model-hierarchy-review.md) to have a repo grade its delegation discipline against this rubric and emit a tracked checklist. Paste it into a Claude Code session in the target repo, or wire it into the shared review workflow.

## Sources

Saved articles synthesized here (full summaries in `data/digest_knowledge/`), and the Claude Code team's own guidance:

- **Simon Willison — "Fable's judgement"** (2026-07-03) — the anchor; direct quotes from Jesse Vincent (Claude Code team) plus Cat Wu and Thariq Shihipar on Sonnet-for-implementation / Haiku-for-mechanical / Fable-keeps-judgment. [simonwillison.net/2026/Jul/3/judgement/](https://simonwillison.net/2026/Jul/3/judgement/)
- **Paweł Huryn — "Claude Fable 5: The Ultimate Guide for PMs v2"** (2026-06-11, The Product Compass) — depth-limit experiments, "swap on purpose for cost" pattern, delegation-and-escalation `CLAUDE.md` snippet. Free preview + paid deep-dive.
- **Nate Jones — "Stop paying frontier prices for work a cheaper AI would crush. Grab the model-picker prompt that routes the deck, the repo, and the call."** (2026-07-02, Nate's Newsletter, paid — read via subscriber PDF) — primary source for the "start with the job" framing, the frontier / daily-driver / workhorse / specialist split, the model-picker prompt (quoted verbatim in practice #10), the 30-minute / 1-week testing protocol, the personal-memory / job-context split, and the "permission comes first" rule for company work. Uses Coinbase (Business Insider: Armstrong on GLM 5.2 / Kimi 2.7 defaults, complexity-based routing) and Cursor Composer 2 on Kimi K2.5 as real-world routing evidence. [natesnewsletter.substack.com/p/which-ai-model-to-use](https://natesnewsletter.substack.com/p/which-ai-model-to-use)
- **Nate Jones — "Executive Briefing: Cheap Intelligence Won't Matter If Your Context Is Trapped"** (2026-06-28, Nate's Newsletter) — the flip side of the tier argument: routing to a cheap model only pays off if your context isn't imprisoned in the frontier vendor's memory, policies, or proprietary integrations. Frames context lock-in as a specific risk of a tier system and reinforces practice #12 (keep context portable). [natesnewsletter.substack.com/p/glm-5-2-context-lock-in](https://natesnewsletter.substack.com/p/glm-5-2-context-lock-in)
- **Anthropic — Claude Code cost docs** (cited by Willison): keep teams small, shut down teammates when done.

## Where Used

- **best-practices** — the crumbl-ops Fable skill-distillation prompt at [`prompts/fable-skill-distillation-crumbl-ops.md`](../../prompts/fable-skill-distillation-crumbl-ops.md) applies this rule set to the specific case of authoring skills.
- **crumbl-ops** — heaviest immediate impact. Fast wins: delegate the code-time reads/greps a Fable or Opus session does; downshift the tail of long sessions to Sonnet once the judgment stretch is done. The dual-model weekly review is already a delegation network — the tier rules formalize which model does which review.
- **command-center** — the agent fleet is already a delegation network; this formalizes what's currently ad-hoc.
- **wealth-mgmt** — research and investment-thesis work benefit from the parent-judgment / subagent-reading split; ground-truth verification passes can go to Sonnet.
