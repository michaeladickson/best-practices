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

1.  **Familiar or ambiguous?** Can you describe what "good" looks like before the model starts?
2.  **Fast to inspect?** Can you check the result quickly, or is review expensive?
3.  **Sensitive data?** Do customer records, financial data, legal drafts, code, health info, HR material, or unreleased product plans belong in this session's model?
4.  **Special inputs?** Audio, screenshots, video, PDF, live web, or repo access?
5.  **Actions?** Does the system need to act — edit files, run tests, move through a browser, generate media?
6.  **Portable context?** Does the source material live somewhere the model can use, or are you about to spend ten minutes re-pasting yesterday's background?
7.  **Reasoning Complexity?** Is this a 'single-pass' task (simple pattern matching) or a 'high-reasoning' task (multi-step problem-solving, chain-of-thought, error recovery)? This informs whether a cheaper, faster model or a frontier model is required.

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

-   **Senses** — audio transcription, video parsing, screenshot / image inspection, PDF or spreadsheet formats your default model handles badly. If your business is calls, transcription may matter before another chatbot subscription.
-   **Sources** — live web, X, CRM, archive search, transcript databases, repo access. If the job depends on current information or a specific corpus, the harness with that stream wins even when the underlying model is weaker. *Treat live answers as first passes and verify current claims.*
-   **Actions** — edit files, run tests, browse, generate media, produce a reviewable diff. Coding illustrates the trap: teams collapse the *model* and the *harness* into one thing. GLM 5.2 can be strong at code, but code work depends on the work surface giving the model repo context, file access, tool calls, tests, diffs, memory, and review. *"The model only becomes useful when the harness can give it the files, tools, and checks."*

At work, **permission comes first.** Customer data, financial data, legal drafts, code, health info, HR material, and unreleased product plans stay in approved tools regardless of which tier is cheaper — routing a sensitive artifact to a random model API "because someone online said it was cheaper" is shadow IT with a benchmark attached.

## Best Practices

### 1. Architect the agent system using a 'engine and steering' paradigm.
Position cheaper, capable models as the robust 'engine' for primary execution, optimizing them rigorously, potentially with open-weights. Reserve frontier models for 'steering' functions: providing strategic planning, making high-level decisions, and orchestrating the overall workflow. This systemic architecture maximizes efficiency by leveraging cheaper models for volume work and frontier models for high-value judgment.

### 2. Leverage CPUs for the agent orchestration layer to manage state, routing, and sandbox execution.
While high-performance accelerators are optimal for model inference and training, CPUs are ideally suited for the agentic orchestration layer. This includes managing agent state, performing semantic routing, selecting tools, and efficiently spinning up secure, isolated sandboxes for code execution. Matching these specific workloads to CPU resources optimizes cost and efficiency.

### 3. Delegate mechanical and scoped work; keep judgment in the parent
The parent decides *which* skills to author, *whether* a finding is real, *how* a change fits the architecture. A subagent does *"read these four files and return the DocNumber assertion location"* or *"verify each of these 12 commands runs without error and return `{command, ok, error}`."* If a subtask can be defined by a fixed input and a **structured** output, it can probably be delegated.

### 4. Give the parent a rule, not a script
Tell the parent the tier table above and let it route. Vincent's version: *"use your judgement to decide an appropriate lower power model."* Prescribing which model to spawn where kills the judgment that makes delegation win.

### 5. Trust frontier models to execute complex subagent workflows from concise, high-level prompts rather than detailed scripts.
For the latest frontier models, minimize prompt instructions by focusing only on the high-level objective, implicitly trusting the model's inherent ability to orchestrate complex tasks via subagents. This leverages advanced model capabilities for workflow generation and avoids hobbling them with excessive detail designed for weaker models.

### 6. Orchestrate multiple subagents in parallel for complex tasks.
For highly demanding tasks, leverage the frontier model to coordinate several subagents working simultaneously on distinct workstreams. This approach, exemplified by 'ultra' effort levels, trades higher token usage for potentially stronger results and faster time-to-result, moving beyond simple sequential delegation.

### 7. Implement complex, multi-stage workflows using a sequence of specialized subagents, with progress tracked by an explicit state machine for transparency.
For tasks requiring distinct, sequential steps (e.g., bug triage: reproduce, diagnose, verify, fix), delegate each stage to a specialized subagent. Orchestrate these stages via an explicit state machine (e.g., using GitHub labels) to provide transparent progress tracking and coordination across the workflow, enabling a structured hand-off between subagents.

### 8. Enable natural language delegation for complex, multi-tool tasks by leveraging agentic interfaces capable of direct computer operation via voice and screen context.
To streamline user interaction and maximize agent autonomy, allow users to delegate multi-step, multi-tool tasks through a single, continuous natural language conversation. This requires agent interfaces that can interpret voice commands, understand screen context, and directly operate the computer to execute actions across various applications without manual intervention.

### 9. Maintain continuous user interaction by delegating long-running tasks to background subagents.
When a task requires deeper reasoning or web search, delegate it to a subagent to execute in the background. The parent model should simultaneously maintain an active, continuous conversation with the user, only bringing the subagent's results into the foreground when ready. This prevents user idle time and improves conversational flow.

### 10. Utilize persistent, cloud-hosted execution environments for long-running or unsupervised subagent tasks.
To support subagents that need to operate continuously or without direct human supervision, deploy them in secure, persistent cloud development environments. This ensures tasks can progress even when the initiating local machine is offline and provides a reliable, scalable foundation for persistent agent work that transcends local sessions.

### 11. Depth cap: 2. Team cap: small.
One subagent tier under the parent — no nesting further. Depth-3+ orchestrations compound spawn overhead and lose reviewability. Small teams (≤ ~5 concurrent) match Anthropic's Claude Code cost docs: *"keep teams small, shut down teammates when they are done."*

### 12. Shutdown discipline
Every subagent shuts down as soon as its structured return lands in the parent. Long-lived teammates burn tokens and drift; short-lived ones are what make the economics work.

### 13. Structured returns, never free-form prose
Subagents return JSON or terse markdown against a small schema the parent can review at a glance. Free-form returns force the parent to re-read the raw material the subagent already consumed — that defeats the whole point of delegating.

### 14. Never delegate the judgment layer
The parent keeps: authoring decisions, drop / merge / route decisions, the final synthesis, and anything touching money movement, prod writes, deletes, or outbound comms. Subagents produce inputs to the parent's judgment; they never *perform* it.

### 15. Log the delegation trail
Record each spawn: subagent model, task summary, structured return. That's what makes the tree auditable, and what lets you retro whether the delegation ratio is actually cost-effective for this repo instead of a comforting story.

### 16. Execute delegated agent tasks within ephemeral, isolated sandboxes.
Implement isolated, agent-native compute environments, such as microVMs or perpetual sandboxes, for all delegated tasks. This ensures security by preventing sandbox escapes and provides a resilient environment for agents to investigate and fix issues without compromising internal systems, even for long-running or exploratory work.

### 17. Implement a dedicated, isolated execution environment, including a git worktree and associated full stack resources, for each parallel subagent session.
When orchestrating multiple subagents in parallel, ensure each agent operates within its own deeply isolated environment. This extends beyond a simple code sandbox to include a unique git worktree and dedicated runtime infrastructure (e.g., staging environments, databases), preventing resource contention and enabling true parallel development.

### 18. Provision isolated, serverless database instances that scale to zero for each subagent's ephemeral or stateful data needs.
To prevent database sprawl and manage costs when running fleets of AI agents, each agent requiring state or storage should be allocated its own serverless, multitenant database instance. These instances should scale to zero when idle, ensuring efficient resource utilization and isolated data layers for each agent.

### 19. Watch for spawn-overhead-dominates
Every subagent spawn has fixed cost (context load, prompt, roundtrip). For very small tasks — *does this file exist* — inline is cheaper than delegating. Rule of thumb: if the task's own tokens are less than about 10× the spawn overhead, do it inline in the parent.

### 20. Swap on purpose, for cost
Anthropic's safety mechanism swaps a Fable session to a lower tier when it detects unsafe content. Paweł Huryn's inversion (digest 2026-06-11): *"we can swap on purpose, for cost."* Explicitly drop the session tier when the remaining work is mechanical; explicitly raise it before the next judgment-heavy stretch.

### 21. The model-picker prompt — classify before executing
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

### 22. Test the cheap route on your own work
Benchmarks tell you a model deserves attention; only *your* work tells you whether it should run your proposal workflow, codebase, or research process. Jones' protocol:

-   **30-minute version.** Pick one recurring artifact. Run it through your daily driver *and* one cheaper route. Time the review. Mark the output usable / repairable / rejected. Write down the failure mode (missed facts, flattened voice, lost structure, hallucination, or basically-right-but-slow-to-clean).
-   **One-week version.** Choose five recurring artifacts. Test each twice. Track model, source material, review minutes, accepted output, sensitive-data constraint, and failure mode. Promote the cheap route only where **review stays cheap** — *"a cheap model that saves money and doubles review time is expensive."*

### 23. Keep context portable; separate personal memory from job context
Every model has its own private history with you (Claude remembers one thing, ChatGPT another, your coding agent knows the repo for a while, your image tool knows the prompt but not the project). If all of that stays separated by product, you become the router by hand — which is exhausting. Jones' split:

-   **Personal memory** — preferences, taste, standards, recurring projects.
-   **Job context** — source material for the task (transcript, file, examples, requirements, customer notes, repo, prior decision, checklist).

The more job context lives in files, folders, search, embeddings, project notes, and harnesses — not in one product's memory — the less any single model's memory dictates routing. *"Give a bounded worker the right packet of context."* Rent the intelligence you need; keep the context that makes the work yours.

### 24. Pre-compile raw context data into a structured knowledge base for agents.
Before agents operate on raw information, implement a pre-processing step using an LLM to compile it into a structured, queryable knowledge representation (e.g., a wiki with summaries and backlinks). This 'context compilation' improves agent reliability by ensuring they reason over organized, precise context, not unstructured raw data, which is critical for overcoming agent reliability bottlenecks.

### 25. Avoid using negative constraints and excessive examples in prompts for the latest frontier models.
Modern frontier models often perform better with concise, clear instructions rather than long lists of 'don't do X' or numerous examples. Such negative constraints and over-specification can sometimes reduce the quality of results from the latest models. Focus on conveying the desired outcome directly.

### 26. Dynamically filter context for subagents based on the current task objective.
Avoid context bloat by ensuring tools, skills, and plugins are only passed to the subagent when directly relevant to its immediate, bounded objective within a multi-step workflow, optimizing for efficiency.

### 27. Implement robust access controls and permissions for data retrieved by agents.
Ensure agents only access and reason over data for which the requesting user is explicitly authorized, integrating role-based access controls (RBAC) into the agent's data retrieval mechanisms to maintain security and compliance.

### 28. Delegate the verification of task completion to a separate, typically cheaper, subagent.
After a working subagent completes its assigned work, route the output and the defined completion condition to a smaller, faster model (e.g., Haiku) that acts as an independent verifier, preventing the working agent from 'grading its own homework'.

## Anti-Patterns

-   **Fable-does-everything** — using the frontier model for greps, reads, and verifications because the session is on it.
-   **Prescribing the delegation** — a rigid "always spawn N Sonnets for X" removes the parent's judgment.
-   **Nested subagent trees** — depth-3+ orchestrations that lose reviewability and compound overhead.
-   **Long-lived teammates** — subagents kept alive across tasks, accumulating stale context.
-   **Free-form returns** — subagent output that forces the parent to re-read the raw material.
-   **Delegating judgment** — pushing "should I write this skill" or "is this finding real" down the tree.
-   **Delegating money/writes** — a subagent never gets destructive-action authority; the parent stays in the loop.
-   **Tiny-task delegation** — spawning for `test -f`. The spawn overhead is the whole cost.
-   **Opening the wrong tier by default** — reaching for the same model out of habit before describing the job. That's where the money leaks.
-   **Cheap-route without review economics** — moving to a cheaper model without measuring whether review time inflates faster than token cost falls.
-   **Collapsing model and harness** — thinking *"use GLM for code"* when what wins/loses is whether the harness gives the model repo context, tool calls, tests, and a reviewable diff.
-   **Frontier by default for repeat work** — using the frontier model on every recurring artifact when the shape is legible enough to delegate.
-   **Ignoring the permission filter at work** — routing customer / financial / legal / HR / code / unreleased-product data to an unsanctioned model because it's cheaper. Shadow IT with a benchmark attached.

## Self-Assessment

Use [`reviews/model-hierarchy-review.md`](../../reviews/model-hierarchy-review.md) to have a repo grade its delegation discipline against this rubric and emit a tracked checklist. Paste it into a Claude Code session in the target repo, or wire it into the shared review workflow.

## Sources

Saved articles synthesized here (full summaries in `data/digest_knowledge/`), and the Claude Code team's own guidance:

-   **Anthropic Deleted 80% of Claude Code's Prompt. It Got Smarter** (Ruben Dominguez (The AI Corner)) — Trust frontier models with concise, high-level prompts for complex subagent workflows. Digest: 2026-08-07.
-   **Anthropic recommends a git worktree per agent. Your runtime infra makes that a problem.** (The New Stack) — Implement dedicated, full-stack isolated execution environments (including git worktrees) for parallel subagent sessions. Digest: 2026-08-06.
-   **Today’s Codex will feel “primitive” by fall — and its own team’s roadmap backs it up** (The New Stack) — Utilize persistent, cloud-hosted execution environments for long-running or unsupervised subagent tasks. Digest: 2026-08-04.
-   **AI agents can create database sprawl issues. YugabyteDB’s solution is more agents!** (The New Stack) — Provision isolated, serverless database instances that scale to zero for each subagent's data needs. Digest: 2026-08-04.
-   **Astro’s GitHub issue backlog is heading to zero for the first time in 5 years. Now Cloudflare is open-sourcing the tool that did it.** (The New Stack) — Implement complex, multi-stage workflows using a sequence of specialized subagents with state machine tracking. Digest: 2026-08-04.
-   **ChatGPT Codex Voice + browser + Sites: an expert’s AI workflow | Nick Baumann (OpenAI)** (Lenny's Newsletter) — Enable natural language delegation for complex, multi-tool tasks via voice and screen context. Digest: 2026-08-03.
-   **[AINews] GPT 5.6 price cut by 20%-80%: Cost of GPT 5.4 Intelligence dropped 13x in 4 months due to GPT 5.6 recursive self-optimization** (Latent Space [ai_engineering]) — Dynamically filter context for subagents based on the current task objective. Digest: 2026-07-31.
-   **OpenAI and Elastic are tackling the AI problem enterprises can’t ignore** (The New Stack [devops]) — Implement robust access controls and permissions for data retrieved by agents. Digest: 2026-07-30.
-   **Goal Engineering, or: Are We There Yet?** (Pascal Biese (LLM Watch) [ai_engineering]) — Delegate the verification of task completion to a separate, typically cheaper, subagent. Digest: 2026-07-29.
-   **Stop guessing whether a cheaper model can do the job. Grab the bakeoff guide: the validator, the manifest, the score sheet, and the fixtures.** (Nate Jones [ai_strategy]) — Include the cost of human review and correction when evaluating model efficiency and choosing a routing path. Digest: 2026-07-27.
-   **[AINews] OpenAI launches GPT 5.6 Sol/Terra/Luna, Codex becomes ChatGPT superapp** (Latent Space) — Complex tasks: coordinate multiple subagents in parallel. Digest: 2026-07-10.
-   **Introducing GPT\u2011Live** (Simon Willison) — Long-running tasks: delegate to background subagents, maintain user interaction. Digest: 2026-07-09.
-   **Executive Briefing: Run the $40 question on your org this week. If nobody can answer it, you've found your real AI bottleneck.** (Nate Jones) — Architect agent system using 'engine and steering' paradigm. Digest: 2026-07-05.
-   **Arm and Google offer a smarter option to run agentic AI workloads** (The New Stack) — Orchestration layer on CPUs. Digest: 2026-07-17.
-   **The bottleneck for AI agents isn’t the model anymore. It’s the context layer.** (The New Stack) — Pre-compile raw context data into structured knowledge. Digest: 2026-07-18.
-   **Single-pass AI code isn’t dead, but “high-reasoning” is the next frontier** (The New Stack) — Classify tasks by reasoning complexity. Digest: 2026-07-21.
-   **A Fireside Chat with Cat and Thariq from the Claude Code team** (Simon Willison) — Avoid negative constraints and excessive examples. Digest: 2026-07-21.
-   **Opus 5 costs a third of the price — and that’s actually the problem** (The New Stack) — Execute delegated agent tasks in sandboxes. Digest: 2026-07-25.
-   **Simon Willison — "Fable's judgement"** (2026-07-03) — the anchor; direct quotes from Jesse Vincent (Claude Code team) plus Cat Wu and Thariq Shihipar on Sonnet-for-implementation / Haiku-for-mechanical / Fable-keeps-judgment. [simonwillison.net/2026/Jul/3/judgement/](https://simonwillison.net/2026/Jul/3/judgement/)
-   **Paweł Huryn — "Claude Fable 5: The Ultimate Guide for PMs v2"** (2026-06-11, The Product Compass) — depth-limit experiments, "swap on purpose for cost" pattern, delegation-and-escalation `CLAUDE.md` snippet. Free preview + paid deep-dive.
-   **Nate Jones — "Stop paying frontier prices for work a cheaper AI would crush. Grab the model-picker prompt that routes the deck, the repo, and the call."** (2026-07-02, Nate's Newsletter, paid — read via subscriber PDF) — primary source for the "start with the job" framing, the frontier / daily-driver / workhorse / specialist split, the model-picker prompt (quoted verbatim in *The model-picker prompt — classify before executing*), the 30-minute / 1-week testing protocol, the personal-memory / job-context split, and the "permission comes first" rule for company work. Uses Coinbase (Business Insider: Armstrong on GLM 5.2 / Kimi 2.7 defaults, complexity-based routing) and Cursor Composer 2 on Kimi K2.5 as real-world routing evidence. [natesnewsletter.substack.com/p/which-ai-model-to-use](https://natesnewsletter.substack.com/p/which-ai-model-to-use)
-   **Nate Jones — "Executive Briefing: Cheap Intelligence Won't Matter If Your Context Is Trapped"** (2026-06-28, Nate's Newsletter) — the flip side of the tier argument: routing to a cheap model only pays off if your context isn't imprisoned in the frontier vendor's memory, policies, or proprietary integrations. Frames context lock-in as a specific risk of a tier system and reinforces *Keep context portable; separate personal memory from job context*. [natesnewsletter.substack.com/p/glm-5-2-context-lock-in](https://natesnewsletter.substack.com/p/glm-5-2-context-lock-in)
-   **Anthropic — Claude Code cost docs** (cited by Willison): keep teams small, shut down teammates when done.

## Where Used

-   **best-practices** — the crumbl-ops Fable skill-distillation prompt at [`prompts/fable-skill-distillation-crumbl-ops.md`](../../prompts/fable-skill-distillation-crumbl-ops.md) applies this rule set to the specific case of authoring skills.
-   **crumbl-ops** — heaviest immediate impact. Fast wins: delegate the code-time reads/greps a Fable or Opus session does; downshift the tail of long sessions to Sonnet once the judgment stretch is done. The scheduled review workflow is already a delegation network — independent Claude reviewer agents (weekly diff-scoped reviews, monthly self-assessments) running apart from the authoring sessions — and the tier rules formalize which model tier each review deserves.
-   **command-center** — the agent fleet is already a delegation network; this formalizes what's currently ad-hoc.
-   **wealth-mgmt** — research and investment-thesis work benefit from the parent-judgment / subagent-reading split; ground-truth verification passes can go to Sonnet.
