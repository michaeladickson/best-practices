# Context & Memory Management

How an agent decides *what to remember, where to put it, and when to read it back*. The goal: reconstruct the right context by **retrieval** (reading a known home) rather than **rediscovery** (re-deriving facts from code or scattered notes) — without paying for that context on every session. Agents that skip this re-derive the same facts run after run; one analysis put it at ~85% of context rediscovered per session — slow, costly, and inconsistent.

Sibling docs: [Token Efficiency](token-efficiency.md) (cache, `/clear`, `/compact`, model routing) and [CLAUDE.md Structure](claude-md-structure.md) (knowledge system, layered architecture). For a ready-to-run audit, see [`reviews/context-memory-review.md`](../../reviews/context-memory-review.md).

> **Note on structure (consolidated 2026-08-01).** This doc had reached 56.5KB — 81% of the
> updater's 70KB cap — carrying 70 auto-appended bullets, each a bold sentence followed by a
> paragraph restating it. Two problems, both fixed here. **Bulk:** those bullets are now
> one line each, folded into the section they belong to. **Drift:** six sections
> (Governance & Control, Agent Orchestration, Advanced Reasoning, Observability, Security &
> Isolation, Rich Context) had accreted 17KB of material that is not context-or-memory and
> duplicates sibling docs; they are collapsed into *Adjacent Concerns* below, one line each,
> pointing at the doc that actually owns the topic. **Nothing was deleted outright** — every
> practice survives as a line, because the dedup ledger already marks these articles
> incorporated and dropping one would make it unrecoverable.

**Scope check before adding here:** does this change what an agent *remembers, stores, or
reads back*? If it's about what the agent is allowed to *do*, it belongs in
`../ai-safety/agent-action-safety.md`. If it's about reviewing what the agent *produced*,
it belongs in `code-review-and-ai-slop.md`. That test is what the drift above failed.

- **Scope the task before deploying an agent at all.** Judge size, independence, separation and checkability to decide between a chat, one agent, a team, or no AI. Not every task earns an agent.

## Memory Tiers

Three places a fact can live, by scope:

| Tier | Home | Scope | Examples |
|---|---|---|---|
| **1 — Session** | the conversation | this session only | what you're mid-way through, a value you just computed |
| **2 — Project** | the repo: `CLAUDE.md`, per-module `CLAUDE.md`, `knowledge/`, `decisions/` | true for *this* repo | agent I/O contracts, domain rules, architectural decisions |
| **3 — Global** | `~/best-practices/practices/` and cross-session memory | true across repos / about the user | build conventions, the user's preferences and profile |

**The tier test** — before storing a fact, ask: *would this be true in another repo?* → Tier 3. *Only here?* → Tier 2. *Only this session?* → don't store it.

-   **A local/on-device tier is now viable** as small models get good enough to run offline — worth treating as a distinct tier where privacy, data residency or offline operation matter.
-   **Maintain memory locally, not globally.** Optimize the segments actual usage touches rather than periodically reorganizing the whole store; no single memory architecture dominates, and global reshuffles cost more than they return.
-   **Architect agents for durable session context by using event logs for resumability, enabling persistent background processes, and leveraging secure cloud environments for detached, long-running tasks.** For agents performing complex, long-horizon tasks, ensure their operational state and context are robustly maintained, logging intermediate steps for resumability, designing for persistent background execution, and deploying to cloud environments that support detached operations.

## Retrieval Contracts (Sources of Truth)

Every recurring fact gets **one canonical home**. Read that home; don't re-derive the fact from code or copy it into a second file.

-   **Name the winner.** When two files describe the same fact, one is authoritative and the other points to it. Maintain a "sources of truth" table (one per repo) so the canonical home for each fact-scope is unambiguous.
-   **A per-module `CLAUDE.md` is a retrieval contract.** Read it instead of re-reading the module's code to learn what the module does. Because it stands in for the code, it **must mirror the code** — and when they disagree, *the code is authoritative and the doc is the bug.* A silently drifted doc is worse than no doc, because it is trusted.
-   **Point, don't restate.** A non-canonical mention of a fact should link to the home, not duplicate the content. Duplication is what drifts.

Worked example (from a production hub repo): a `Sources of Truth` table maps *people* → a contacts file, *deal participants* → a domain knowledge file, *agent I/O* → that agent's `CLAUDE.md` (code-authoritative), *layout & conventions* → a file-map doc, *past choices* → the decision journal, *cross-session user facts* → memory.

**Assembly, not just retrieval.** A retrieval contract is more than vector search / RAG over text. RAG alone returns "probably relevant text"; a reliable contract names the *whole* set the task needs — records, permissions, policies, prior decisions, and provenance — and assembles it up front instead of letting the agent rediscover it mid-run. A lightweight spec for a recurring task:

```
# Retrieval contract: weekly-review agent
Needs:
  - last 7 days of structlog events     (source: GCP logging, JSON)
  - open GitHub issues w/ label:ops     (source: gh api, provenance = issue URL)
  - prior week's review                 (source: knowledge/reviews/, most recent)
  - active rules for this domain         (source: knowledge/<domain>/rules.md)
Format: pre-assembled markdown brief, newest-first, each fact tagged with its source.
```

**What the contract has to get right:**

- **Rationale over implementation.** Rank decisions and trade-offs above code snippets when the task needs to know *why*. Retrieving the *how* and answering the *why* is how agents produce confident wrong answers.
- **Validate retrieval at runtime, not just at design time.** Monitor relevance and completeness live; retrieval degrades at scale and the failure is fluent, not loud.
- **Embedding proximity does not scale cleanly.** Pure vector/RAG memory is provably prone to hallucination and forgetting as the store grows — plan hybrid approaches and guardrails rather than assuming more embeddings fix it.
- **Validate agent-*written* memory.** Probabilistic extraction feeding a shared store poisons it silently; capture confidence or validate before ingest.
- **Structured handoff records between agents.** When work moves tool-to-tool, the output should carry state, original sources and limits — otherwise a human is the integration layer.
- **Keep it portable.** Don't couple storage, access or semantics to one vendor's proprietary format, or the accumulated memory can't follow you to another model.
- **Codify voice/style as a reusable context file.** A dedicated tone/persona file injected into the prompt keeps register consistent instead of re-described each time.
- **Live data needs a streaming foundation.** Fragmented sources plus legacy access control is the usual blocker for agents reasoning over current business state.
- **Cache hot context on fast storage** when retrieval latency starts to matter.
- **Declarative orchestration over ad-hoc chaining.** Blueprint languages and named patterns (supervisor, delegation, fan-out) make multi-agent context flow reviewable.

### Context Lake Architecture

- **A Context Lake** centralizes agent-retrievable knowledge (codebase, APIs, services, team) into one governed store, with access control at the data layer rather than per tool, pre-chunked to support progressive disclosure.
- **A context *warehouse* adds active components:** a miner that continuously crawls heterogeneous sources for deltas, and a composer that assembles a purpose-built brief for the task at hand instead of serving static retrieval.
- **Compile knowledge, don't just store it.** An LLM pass that turns raw sources into wikis, summaries and linked concept articles gives agents something queryable, with outputs feeding back in.
- **Scale to zero.** Agent retrieval load is bursty; serverless components avoid paying for idle.

## Context Budget

Context splits into **always-loaded** (paid every session) and **load-on-demand** (paid only when needed):

-   **Always-loaded** — root `CLAUDE.md`, the memory *index*. Keep these a **names-and-pointers index**: orientation, not detail.
-   **Load-on-demand** — file maps, domain knowledge, decision records, per-module docs. Detail lives here; a pointer from the always-loaded layer makes it discoverable.

The asymmetry drives the rule: a paragraph in root `CLAUDE.md` is paid in every future session whether or not it's relevant; the same paragraph in a load-on-demand file costs nothing until something needs it. **Push detail down; keep the top layer lean.**

**Manage the live session, not just the always-loaded layer.** Baseline (system prompt + tools + MCP) is ~34K tokens before you type, and quality slips well before the 200K mark — so don't let a session silently fill:

| Move | When |
|---|---|
| `/clear` | switching to an unrelated task |
| `/compact <what to keep>` | at ~50%, or after finishing each task |
| spawn a subagent | a context-heavy subtask (research, broad search) — it runs in its own window and only the result returns |
| `Esc Esc` / `/rewind` | after a bad turn (don't argue in-context — that keeps the failure) |

-   **Protect the cache.** Lock `--model` and the MCP set at session start; adding an MCP or swapping models mid-session rebuilds the prefix (~10× per miss). See [Token Efficiency](token-efficiency.md).
-   **Curate the harness footprint.** Every tool from every connected MCP sits in context *every* turn — the same always-loaded tax as a fat `CLAUDE.md`. Prefer narrow, single-purpose MCP servers; disable unused ones.
-   **Prune the session deliberately.** Named categories worth dropping: superseded standing instructions, unused tool definitions, transient files, stale screenshots, dead browser results, repeated command output, rejected answers. Reported to cut reused input by up to 90%.
-   **Structure prompts for prefix caching.** Most spend is resending the same system prompt, tool list and static docs every call; ordering for cache hits is the single biggest lever.
-   **Use effort controls.** Raise depth for work that needs reasoning, lower it for routine work, rather than paying one rate for everything.
-   **Let the orchestrator pick subagent models** by task type and cost — and write the routing decision back as a memory rule so it persists. Parent reviews before committing the subagent's output.
-   **Fan out for genuinely large work.** Codebase-scale migrations suit dynamic planning plus many parallel subagents, with a verification step before integrating.
-   **Rules files beat hoping.** Agents default to internal training knowledge even when tools and knowledge bases exist; an explicit rules file forcing external-context-first is what makes retrieval reliable.
-   **Enterprise tasks want holistic context.** Real workflows need broader assembly than benchmarks imply — interconnected decisions, not isolated snippets.
-   **Don't tokenmaxx.** Token volume is not productivity. Tie consumption to delivered outcomes, or the budget grows without the value.

## Cross-Boundary Duplication Is Allowed

The anti-duplication rule applies *within* a load context, not across. Cross-session memory may legitimately restate a repo fact, because memory loads when a *different* repo is active and this repo's docs are not in context. The test isn't "does this string appear twice?" — it's "can these two copies be in context at the same time and disagree?" If they can never co-occur, the duplication is safe and often necessary.

## Avoiding Fragmentation

The failure mode a retrieval contract prevents is *two homes for one fact that drift apart*. So:

-   **Don't create a second "where things live" doc.** Extend the canonical one. A new `SOURCES.md` beside an existing file-map doc just adds a surface that can disagree.
-   **Corrections already have homes** — behavioral feedback → cross-session memory; architectural choices → the decision journal; a domain hypothesis that failed → demote it in `hypotheses.md`. A dedicated `ERRORS.md` fragments these.
-   **Staleness** — let time-sensitive entries carry an inline date so freshness is visible; don't add a manual "last verified" header to every file (upkeep burden, and git history already records change time). Status *snapshots* (a `PROJECT_STATUS.md`) can be staleness-checked by mtime; stable reference facts can't — age ≠ wrong.

## Skills as Institutional Memory

Version-controlled skills are how recurring workflows become durable, discoverable memory instead of prose re-explained each session. Move a recurring agent workflow into a `skills/` file with a clear trigger and an input/output contract: it loads only when invoked (unlike root `CLAUDE.md`), so it is institutional memory *and* lean context. This also kills "shadow skills" — the same instructions retyped every session — keeping behavior consistent across runs and across repos.

- **Make skills granular and composable.** Small, semantically precise commands an agent applies iteratively beat one-shot instructions — more control, more predictable results.
- **Agents can extract skills from their own successful trajectories**, turning past runs into reusable procedure — the self-improvement end of governed write-back.
- **Implement systematic feedback loops to capture human corrections of agent mistakes, using this structured data to refine agent models and their understanding of context.** Establish a process where human interventions, especially corrections to agent-generated outputs (e.g., code), are meticulously recorded alongside the original task and the agent's incorrect attempt, using this structured correction data to improve future context interpretation.

## Decision Journal

Choices that outlive today's task go in `decisions/YYYY-MM-DD-{topic}.md` (see [CLAUDE.md Structure](claude-md-structure.md)). Each record: Decision / Context / Alternatives Considered / Reasoning / Trade-offs. `Supersedes:` / `Superseded-by:` headers chain related records into a grep-able audit trail. **Grep the journal before making a similar choice** — it's the institutional memory that keeps you from re-litigating settled questions.

## Provenance

When surfaced context is **AI-generated** (a model-written summary, a classification), mark it where it's shown, so a reader can tell synthesis from ground truth and knows to verify before acting. Raw data and AI synthesis should stay visually distinguishable. The same applies to *assembled* context: tag each fact with its source (especially for financial or compliance work), so a reviewer can trust or challenge a specific claim instead of the whole answer.

- **Tag context by trust boundary — operator vs. external.** An agent cannot otherwise tell your instructions from instructions embedded in a web page or a GitHub issue it read. This is the context-layer half of prompt-injection defense; the action-layer half is in `../ai-safety/agent-action-safety.md`.
- **Require an evidence packet with consequential decisions:** the queries run, completeness of the data, approximations made, and alternatives tested — not just the records retrieved.

## Enforcement (the frontier)

None of the above is self-enforcing — docs drift from code silently. The maturity endpoint is an audit/maintenance agent that detects drift: *deterministically* for status snapshots (issues referenced in a status file that are now closed; file mtime), and via an *AI pass* for semantic drift (a per-module `CLAUDE.md` whose described inputs no longer match its code). Until that exists, drift is caught only when a human or agent happens to read both sides.

- **Probabilistic release gates** — baseline evals, drift detection, shadow validation, cost/latency guardrails — are the CI-side equivalent for pipelines whose regressions are gradual rather than binary.

## Adjacent Concerns

These arrived via the weekly digest and were filed here, but they are not context-or-memory
practices — they are agent *safety*, *architecture*, or *review* practices. Kept as one-line
pointers so nothing is lost, with the doc that owns each topic named. **Add new material of
this kind to the owning doc, not here.**

**Agent action safety, permissions, isolation** → `../ai-safety/agent-action-safety.md`

- Self-hosted sandboxes isolate tool execution, protecting internal networks and giving explicit control over data residency.
- Choose the deployment substrate by who must own context, credentials and retention terms.
- Agent IAM: distinct identity per agent, least privilege, audited tool calls — never ambient inherited permissions.
- Encode fine-grained permissions in the harness itself, not only in policy documents.
- Inspect and policy-check every package/plugin an agent proposes to install, *before* install.
- Secure the agentic toolchain (IDE extensions, MCP servers, developer tools) as a first-class attack surface.
- Use synthetic data in every non-production environment agents touch.
- Platform-native MCP servers (browser, IDE) give sandboxed access without bespoke integration.
- Multi-layer kill switches — application, platform, network, identity, cloud.
- Explicit human approval and "send boundaries" before any outward-facing action.
- Data portability and ownership policies for agent-generated memory, especially on vendor-managed runtimes.

**Agent architecture and harness** → `model-hierarchy-delegation.md` and `code-review-and-ai-slop.md`

- Managed runtimes and configuration-first harnesses over bespoke orchestration code.
- Persistent cloud/desktop runtimes; treat mobile as a companion client for approval and monitoring.
- Virtual desktops (plus filesystem MCP) let agents drive legacy GUI applications.
- Agentic CI/CD steps replacing fixed scripts — inside existing governance and audit controls.
- Harnesses as a platform-engineering layer, for standardization and guardrail enforcement.
- Design tool schemas defensively against model-specific tool-use bias.
- Cross-vendor governance layer for shared context and reusable agentic processes.

**Reasoning and planning** → `code-review-and-ai-slop.md`

- Tree-of-thought with cognitive-frame branching for divergent ideation, then prune.
- An explicit reasoning/verification step — retrieval does not guarantee comprehension.
- Structured intermediate "blueprints" between intent and execution as verifiable context.
- Dynamic grounding: infer world state from self-generated interaction when a request is underspecified.
- Named loop types (turn / goal / time / proactive) with explicit stop conditions.
- Interactive HTML artifacts as a richer collaboration medium than plain markdown.

**Observability and verification** → `code-review-and-ai-slop.md`

- Tracing, per-step logging and token estimation, since agent failure is silent rather than loud.
- Debugging "gradients of wrong" — confident incorrect output with no error to catch.
- Observability platforms double as a retrieval source for agent context about past system state.
- Hostile/fuzzing environments for agent-generated code.
- A language-agnostic conformance suite as the prerequisite for large-scale agentic refactors.
- Judge agent contribution by production outcomes, not usage volume.

## Self-Assessment

Use [`reviews/context-memory-review.md`](../../reviews/context-memory-review.md) to have a repo grade itself against these practices and emit a tracked checklist of fixes — paste it into a Claude Code session in the target repo, or wire it into the shared review workflow.

## Sources

Synthesized from saved digest articles (`data/digest_knowledge/`) plus production use:

-   **Your AI agent is rediscovering 85% of its context every run** (Nate Jones) — assembly vs. rediscovery, the knowledge layer. Digests: 2026-05-16, 2026-05-18.
-   **Why agent harnesses fail inside cloud-native systems** (The New Stack) — harness footprint, feedback loops. Digest: 2026-05-18.
-   **How to build a skills library** (The New Stack) / **Red Hat's skill packs give AI agents institutional memory** — skills as durable memory. Digests: 2026-05-16/18.
-   **Spec-driven development at Notion** (Lenny's Newsletter) — context assembly via specs, subagents. Digest: 2026-05-18.
-   **Why production RAG systems give confident, wrong answers at scale** (The New Stack) — runtime validation of retrieved context quality. Digest: 2026-05-19.
-   **Kore counts down to Artemis, its moonshot for governable AI agents** (The New Stack) — declarative blueprint languages and orchestration patterns. Digest: 2026-05-21.
-   **Seven questions decide whether your AI agent ships. Most teams can answer two.** (Nate Jones) — comprehensive control layer with multi-layered kill switches. Digest: 2026-05-20.
-   **Anthropic debuts MCP tunnels and self-hosted sandboxes to lock down AI agent infrastructure** (The New Stack) — self-hosted sandboxes for agent runtime isolation. Digest: 2026-05-19.
-   **HTML is the new Markdown: How Anthropic engineers are building with Claude Code | Thariq Shihipar** (Lenny's Newsletter) — interactive HTML artifacts for human-agent collaboration. Digest: 2026-05-18.
-   **Why enterprise AI keeps stalling — and how data streaming could unlock it** (The New Stack) — real-time data streaming for live business context. Digest: 2026-05-22.
-   **JFrog report recaps a tumultuous year in supply chain security** (The New Stack) — securing the agentic toolchain against weaponization. Digest: 2026-05-22.
-   **How MCP and synthetic data are reshaping compliance in the agentic era** (The New Stack) — synthetic data in non-production environments. Digest: 2026-05-23.
-   **OpenClaw passed 300,000 GitHub stars. Then Google launched Spark.** (The New Stack) — agent deployment substrate for security. Digest: 2026-05-23.
-   **When $8 Becomes $240** (AI Engineering) — trust boundary for context elements. Digest: 2026-05-24.
-   **Why AWS scrapped OpenSearch’s architecture to chase agent workloads** (The New Stack [devops]) — Architect retrieval systems to scale to zero for cost efficiency and bursty agent workloads. Digest: 2026-05-28.
-   **Claude Opus 4.8 is here: effort controls, dynamic workflows, cheaper fast mode, better honesty, less deception** (The New Stack [devops]) — Utilize agent 'effort controls' to balance response quality, speed, and token cost. Digest: 2026-05-28.
-   **Claude Opus 4.8 is here: effort controls, dynamic workflows, cheaper fast mode, better honesty, less deception** (The New Stack [devops]) — Implement dynamic workflows with parallel subagents for tackling large-scale, complex coding tasks. Digest: 2026-05-28.
-   **The agentic identity crisis: Why your security isn’t ready for the AI revolution** (The New Stack [devops]) — Implement an Agent Identity and Access Management (IAM) framework to secure agent actions and mitigate RAG attack surfaces. Digest: 2026-05-28.
-   **Debugging the undebuggable: building observability into probabilistic AI systems** (The New Stack [devops]) — Implement comprehensive observability (tracing, logging, token estimation) for AI agent systems to debug non-deterministic behaviors and context-related failures. Digest: 2026-05-28.
-   **[AINews] New AI Infra decacorns: Fireworks, Baseten (with OpenRouter on the way)** (Latent Space [ai_engineering]) — Integrate continuous evaluation loops and runtime feedback with agent harnesses to refine context and memory management strategies. Digest: 2026-05-27.
-   **Building OpenCode with Dax Raad** (The Pragmatic Engineer [engineering]) — Optimize context retrieval performance using smart caching strategies on high-speed storage. Digest: 2026-05-27.
-   **Researcher “gave Claude Code ‘ADHD’… and it thinks 2x better now.” Outside experts want more proof.** (The New Stack [devops]) — Employ advanced reasoning and planning layers like 'tree-of-thought with cognitive-frame branching' for divergent ideation and pruning. Digest: 2026-05-27.
-   **“There is no accountability”: AI coding agents are installing packages no one owns** (The New Stack [devops]) — Implement pre-installation inspection and policy enforcement for all packages, plugins, and dependencies introduced by autonomous AI agents. Digest: 2026-05-27.
-   **“Tokenmaxxing is real, expensive & it’s spreading”: AI budgets are exploding** (The New Stack [devops]) — Shift focus from maximizing token usage ('tokenmaxxing') to optimizing token consumption for desired outcomes. Digest: 2026-05-27.
-   **With Google’s debut, the most important AI agent feature is now the most boring one** (The New Stack [devops]) — Adopt managed agent runtimes and configuration-first harnesses to streamline agent orchestration and infrastructure. Digest: 2026-05-27.
-   **Why AI agents need a Context Lake** (The New Stack [devops]) — Establish a 'Context Lake' as a centralized, governed, and optimized database for all agent-retrievable context. Digest: 2026-05-27.
-   **AI Agents of the Week: Papers You Should Know About** (Pascal Biese (LLM Watch)) — structured intermediate representations ('blueprints') as explicit context artifacts. Digest: 2026-06-01.
-   **Your AI agent is going to hallucinate at scale** (Ruben Dominguez (The AI Corner)) — mitigate inherent scaling limitations of embedding-proximity-based retrieval systems. Digest: 2026-06-04.
-   **Google Gemma 4 12B nearly matches 26B benchmarks — and runs on your laptop** (The New Stack) — local/on-device memory tiers for agents. Digest: 2026-06-05.
-   **Inference engineering is the 80% cost cut most teams miss** (Ruben Dominguez (The AI Corner)) — optimize agent token usage and latency through inference engineering techniques including prefix caching. Digest: 2026-06-16.
-   **Your AI pipeline is broken, and your dashboards don’t know it** (The New Stack [devops]) — debugging probabilistic AI systems and 'gradients of wrong'. Digest: 2026-06-18.
-   **Grab the Open Engine guide: the copy-paste task record that makes one AI's work the next AI's job, with receipts** (Nate Jones) — Define and implement structured 'agent handoff records'. Digest: 2026-06-26.
-   **Agent Toolkit for AWS includes 20+ agent skills, but your agent might not load them without this one file** (The New Stack) — Utilize explicit 'rules files' or policies within agent harnesses. Digest: 2026-06-25.
-   **Executive Briefing: Cheap Intelligence Won’t Matter If Your Context Is Trapped** (Nate Jones [ai_strategy]) — Architect agent systems to avoid vendor lock-in by ensuring core context and permissions are portable. Digest: 2026-06-28.
-   **AI Agents of the Week: Papers You Should Know About** (Pascal Biese (LLM Watch) [ai_engineering]) — Implement dynamic context grounding and adaptation frameworks that integrate planning, search, reasoning, and memory. Digest: 2026-06-29.
-   **AI Agents of the Week: Papers You Should Know About** (Pascal Biese (LLM Watch) [ai_engineering]) — Enable agents to meta-optimize synthetic data creation and extract hierarchical skills from their own trajectories. Digest: 2026-06-29.
-   **AI Agents of the Week: Papers You Should Know About** (Pascal Biese (LLM Watch) [ai_engineering]) — Prioritize localized memory maintenance over global reorganization in agent-native memory systems. Digest: 2026-06-29.
-   **“The harness is where the hard work is”: Harness bets on agents that enterprises can trust in production** (The New Stack [devops]) — Replace fixed scripts in CI/CD pipelines with autonomous worker agents that reason through tasks. Digest: 2026-06-30.
-   **AWS launches a desktop for agents** (The New Stack [devops]) — Provision dedicated virtual desktop environments (e.g., AWS WorkSpaces for Agents) for agents to interact with legacy applications. Digest: 2026-06-30.
-   **How Kent Beck shapes the software engineering industry** (The Pragmatic Engineer [engineering]) — Integrate specialized testing and verification tools (e.g., hostile environment testing) for agent-generated code. Digest: 2026-07-01.
-   **You can build 80% of your own AI memory by talking to the agent already on your computer** (Nate Jones [ai_strategy]) — Implement explicit human approval workflows and clear 'send boundaries' for agents. Digest: 2026-07-01.
-   **OpenClaw’s new app doesn’t run AI on your phone. That’s the whole point.** (The New Stack [devops]) — Design agents to run on persistent, independent runtimes (e.g., cloud, desktop). Digest: 2026-07-02.
-   **Why traditional CI/CD fails for LLMs (and the release gates we built to fix it)** (The New Stack [devops]) — Implement probabilistic release gates for LLM pipelines using baseline evaluations, drift detection, shadow validation, and cost/latency guardrails. Digest: 2026-07-02.
-   **Skill engineering and the case against one-shot AI design** (Latent Space [ai_engineering]) — Engineer granular, composable 'design skills' with a specialized vocabulary. Digest: 2026-07-02.
-   **Apple just turned Safari into something AI agents can control** (The New Stack [devops]) — Utilize native Model Context Protocol (MCP) servers provided by platform vendors for secure, direct agent interaction. Digest: 2026-07-03.
-   **Fable's judgement** (Simon Willison [ai_engineering]) — Empower orchestrating agents to dynamically select appropriate lower-power models for subagents. Digest: 2026-07-03.
-   **Better Models: Worse Tools** (Simon Willison [ai_engineering]) — design agent tools and schemas for robustness against model-specific tool-use biases. Digest: 2026-07-05.
-   **Stop prompting. Start writing loops** (Ruben Dominguez (The AI Corner) [ai_strategy]) — structure agent workflows using defined loop types. Digest: 2026-07-07.
-   **JetBrains’ next move isn’t a better IDE — it’s a governance layer over Claude Code, Codex, and Gemini CLI** (The New Stack [devops]) — implement a cross-vendor AI governance layer for shared context and reusable agentic processes. Digest: 2026-07-08.
-   **Watch AWS engineers troubleshoot agentic AI with OpenTelemetry and OpenSearch** (The New Stack [devops]) — leverage observability systems as a primary retrieval interface for agent context. Digest: 2026-07-08.
-   **What a harness is and how to build one with Claude Agent SDK** (Lenny's Newsletter [product]) — explicitly encode specific permissions and access controls within agent harnesses. Digest: 2026-07-08.
-   **The “silent hallucination” loop: how our autonomous data pipeline poisoned its own vector store** (The New Stack [devops]) — implement validation and uncertainty handling for agent-generated data ingested into memory systems. Digest: 2026-07-09.
-   **Develop like you deploy: closing the Kubernetes local-to-cluster gap** (The New Stack [devops]) — integrate agent harnesses as a foundational layer within platform engineering. Digest: 2026-07-09.
-   **Enterprise AI benchmarks are broken** (The New Stack [devops]) — design context management for holistic, large context windows critical for enterprise workflows. Digest: 2026-07-09.
-   **Rewriting Bun in Rust** (Simon Willison [ai_engineering]) — establish a comprehensive, language-agnostic conformance test suite for large-scale agentic code changes. Digest: 2026-07-09.
-   **OpenAI, Microsoft & Anthropic agree on who runs the agent. They disagree on what you can take back.** (The New Stack [devops]) — define clear data portability and ownership policies for agent-generated memory across different deployment archetypes. Digest: 2026-07-10.
-   **Anthropic wants you to use AI to decide whether or not you should use AI.** (The New Stack [devops]) — evaluate AI agent contributions based on production outcomes, not just usage metrics. Digest: 2026-07-10.
-   **Why retrieval quality is becoming the defining challenge in AI agent architecture** (The New Stack [devops]) — prioritize contextual nuance in retrieval, distinguishing rationale from implementation details. Digest: 2026-07-10.
-   **Grab the One-Minute Test That Tells You If Your Task Needs a Chat, One Agent, a Team, or Nothing at All** (Nate Jones [ai_strategy]) — task-scoping framework for agent deployment decisions. Digest: 2026-07-10.
-   **Why every AI agent decision needs a receipt** (The New Stack) — comprehensive 'evidence packets' for decisions. Digest: 2026-07-17.
-   **The bottleneck for AI agents isn’t the model anymore. It’s the context layer.** (The New Stack) — knowledge compilation for structured artifacts. Digest: 2026-07-18.
-   **Your Agent Doesn’t Have a Memory Problem** (Pascal Biese (LLM Watch)) — explicit reasoning and verification layer for retrieved context. Digest: 2026-07-20.
-   **How the founder of Morning Brew built a Claude content machine that never runs out of ideas and never sounds like slop | Alex Lieberman** (Lenny's Newsletter) — codify agent voice and style guidelines in context files. Digest: 2026-07-20.
-   **I Built The Token Saver Skill To Cut My Token Use By 90%. Here Is What It Can And Cannot Do For You.** (Nate Jones) — actively prune context to reduce token usage. Digest: 2026-07-29.
-   **Modus’s operandi: To give AI agents just the right amount of context** (The New Stack) — implement a dynamic 'context warehouse' architecture with continuous learning and real-time assembly. Digest: 2026-07-29.
-   **Introducing Muse Code and Muse Spark 1.2** (Simon Willison) — Architect agents for durable session context using event logs and persistent cloud environments. Digest: 2026-08-06.
-   **The 800 mistakes that could reshape Meta’s AI coding strategy** (The New Stack) — Implement systematic feedback loops for human correction of agent mistakes. Digest: 2026-08-05.

## Where Used

-   **command-center** — `knowledge/FILE_MAP.md` "Sources of Truth" table; per-agent `CLAUDE.md` retrieval contracts (code-authoritative); `decisions/` journal; three-tier memory (session / repo `knowledge/` / global practices + cross-session memory); maintenance agent does deterministic status-drift detection (semantic doc/code drift detection is roadmapped).
-   **crumbl-ops** — root + per-module `CLAUDE.md` and `knowledge/`; path-scoped `.claude/rules/*.md` auto-load destructive-action context (surfaced in the #470 context/memory audit).
-   **best-practices** — `practices/` is the global tier; this doc plus the `reviews/` self-assessment prompt.
-   The memory-tier model and "tier test" apply to any repo with a root `CLAUDE.md` and a shared global practices catalog.
