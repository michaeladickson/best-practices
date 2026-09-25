# Agent Action Safety & Control Layers

How to let an AI agent *take real actions* — move money, write to the GL, send a
message, run a migration — without the action being one bad inference away from
catastrophe. Code review (the [AI-slop doc](../claude-code/code-review-and-ai-slop.md))
covers the code an agent *writes*; this covers what an agent *does at runtime*.

Related: [Prompt-Injection Mitigation](prompt-injection-mitigation.md) (untrusted input
that hijacks an agent), and the destructive-action gating practice in
[Code Review & AI Slop](../claude-code/code-review-and-ai-slop.md#best-practices).

For a ready-to-run audit, see [`reviews/agent-action-safety-review.md`](../../reviews/agent-action-safety-review.md).

> **Note on structure (consolidated 2026-09-24).** The weekly updater grew *Best
> Practices* to 67 numbered entries, one heading per article, up from 37 on
> 2026-08-01. This pass folded them into 15 across five themes: overlapping entries
> merged, restatement paragraphs cut to a bullet, and entries another doc owns collapsed
> into *Adjacent Concerns*, one line each. Nothing was deleted outright; the dedup ledger
> marks these articles incorporated, so a dropped practice could not come back.

**Scope check before adding here:** is it about what an agent is allowed to *do* at
runtime, and how that is gated, isolated and audited? Reviewing what it *wrote* belongs in
[Code Review & AI Slop](../claude-code/code-review-and-ai-slop.md); what it *remembers or
reads back* in [Context & Memory Management](../claude-code/context-memory-management.md).

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

### Theme A — Classify and authorize

### 1. Classify every action by reversibility and blast radius
Before wiring a tool, tier it. This single classification drives every gate below.

| Tier | Examples | Default gate |
|---|---|---|
| **Read-only** | reports, queries, search | none |
| **Reversible write** | draft, label, create-then-delete | log + post-hoc review |
| **Irreversible / high-blast** | money movement, GL/prod-DB writes, deletes, outbound messages, deploys | **explicit human approval** |

- **Classify review actions by blast radius.** When an agent reviews or approves code, add data-security impact, operational impact, verification gaps and change surface to the tiering, so low-risk changes can auto-approve and high-stakes ones escalate.

### 2. Least privilege — read-only by default
An agent gets the *minimum* capability for its job; write capability is a separate,
explicitly-granted path. The strongest version is enforced in code, not prompts: e.g.,
expose only read tools on the agent-facing MCP so a write is structurally impossible,
and route the rare write through a separate non-interactive, gated job. (crumbl-ops does
exactly this — its agent MCP has zero write tools; see Where Used.)

- **Embed authorization rules in the harness.** Each structured workflow the harness runs declares the exact permissions it needs, and the harness refuses anything outside them.
- **Reuse existing RBAC for agent retrieval.** An agent reads only what the requesting user (or the agent's own identity) is already authorized to see; the enterprise's access controls apply, not a parallel set.

### 3. Keep authorization in deterministic code
The component that evaluates policy, authorizes an action and executes the approved
tool call is ordinary deterministic software. The model proposes; code decides. That
keeps the non-determinism of the reasoning out of the safety decision, and makes the
decision auditable.

- **Decouple tool selection from action authorization.** A tool description informs which tool the model picks; it never grants the right to run it. A separate policy engine checks explicit rules against the proposed action.
- **Authorize action sequences, not single calls.** A run of individually valid actions can still be the dangerous one. A trajectory-aware policy engine enforces prerequisites, rate limits and ordering across the workflow.
- **Encode domain constraints as an ontology.** An explicit model of the entities, relationships and limits in the domain gives the policy layer logical guardrails the model's reasoning cannot argue past.

### 4. Write an authorization spec per high-stakes action
Name *who/what* may do the action, under *what limits*, with *what evidence*. For
agentic-commerce-style actions this means identity, authorization, fraud/abuse checks,
and liability — not just "call the payments API." A one-paragraph spec per action beats
a vague "the agent handles payments."

- **Set explicit spending limits for agents.** Permission to act is not a budget. An agent that moves money or consumes paid services (API calls, compute credits) needs a hard cap on outflow.
- **Give financially-acting agents their own identity layer.** Authentication, tokenization and wallet management per agent, so every financial action traces to a verified principal and its limits.

### Theme B — Gate and approve

### 5. A Judge Layer gates the action, not the prose
Put a gatekeeper between "agent proposes X" and "X executes" that returns an explicit
*approve / reject / escalate* — never let execution proceed on implied approval. The
judge can be deterministic (policy rules: amount thresholds, allow-lists, business-hours)
or a separate model with a narrow rubric. Key parts (from the Judge Layer guide):
**action classification → policy/specialist check → memory-governed write-back →
structured, logged decision.**

- **Pre-screen routine actions, escalate the rest.** A classifier auto-approves the low-risk majority and routes only the dangerous or genuinely uncertain actions to a human, which is what keeps human review meaningful.
- **Calibrate agent confidence scores.** A judge or a human acting on "95% confident" needs that number to mean 95%. Uncalibrated confidence quietly bypasses fail-safe-on-uncertainty.

### 6. Human-in-the-loop for the irreversible
For Tier-3 actions, require a human's explicit yes — a mobile approve/deny, a PR
checkbox, a confirmation step that prints exactly what will happen. Design against
**alert fatigue**: gate only what truly needs it (driven by *Classify every action by reversibility and blast radius*), so approvals stay
meaningful instead of being rubber-stamped.

- **Support remote and asynchronous human approval.** For long-running work, mobile alerts and remote review of diffs and steering input let a human approve without being at a workstation — oversight without blocking.
- **Give every high-blast-radius action an undo.** Where an action can be reversed, a time-boxed human-initiated rollback adds safety after execution without requiring approval before it.
- **Keep operators able to intervene.** As agents take over routine operations and incident response, humans lose the system knowledge an escalation needs (comprehension debt). Human review of agent incident analyses and drills that require human intervention keep it.

### 7. Fail safe — stop and ask on uncertainty
An agent that can't verify a precondition must **halt and escalate**, not guess. The
data-deletion catastrophe was a confident guess. Bake in: "if you cannot confirm X, do
not proceed — surface the ambiguity." Externalize what's load-bearing/destructive into
`CLAUDE.md` / rules so the agent *has* the operational context it otherwise lacks — but
still gate the action.

- **Distinguish safety stops from ordinary errors.** When consuming an agent API, a task halted by a safety mechanism must be distinguishable from a timeout, with enough detail to decide whether to retry, resume or change the request.

### Theme C — Verify, monitor and audit

### 8. Never trust the agent's self-report
Agents fabricate success ("I tested it," "I recovered the data"). Verify the action's
effect from an independent source (the actual row count, the API's returned status, a
re-query) before believing it — and especially before reporting success to a human.

- **Evaluate the trajectory, not just the answer.** An outcome reached by fabricated evidence or a dataset shortcut passes an end-state check; only the execution path shows it.

### 9. Gate every agent update on evals
A release is blocked unless a repeatable evaluation shows the agent still preserves its
required behaviors across the full execution path: context assembly, tool calls and
permissions, against explicitly defined limits.

- **Shadow-validate probabilistic updates before release.** Run the new version beside production and compare outputs and interactions to catch silent regressions.
- **Detect drift continuously.** Watch performance, outputs and embedding distributions for slow degradation that never crosses a hard failure threshold.
- **Correlate logs, metrics, traces and tool calls.** Some failure modes appear only when signals are read together.
- **Test every surface for prompt injection.** Adversarial tests on each place the agent reads external content (see [Prompt-Injection Mitigation](prompt-injection-mitigation.md)).
- **Probe for covert behavior adversarially.** Environments such as SHADE-Arena and LinuxArena look for agents pursuing hidden objectives while appearing compliant.

### 10. Provenance and an audit trail for every action
Log each agent action with its inputs, the judge's decision + reason, who/what approved,
and the result. This is what makes an agent action auditable (essential for financial /
regulated workflows) and debuggable after the fact. Keep AI-proposed vs. human-approved
distinguishable.

- **Make auto-approvals auditable and queryable.** An action the agent approved itself needs a record detailed enough to reconstruct the decision, queryable, and tied to the risk policy it was approved under.

### 11. Checkpoint agent executions as durable workflows
Checkpoint after each significant step so a session can pause, survive a crash and
resume from the last validated state, rather than leaving a multi-step action half done.

- **Map dependencies before you need a kill switch.** An agent's blast radius runs through every API, cloud resource and identity service it touches; a current map is what makes a complete, controlled shutdown possible during an incident.

### Theme D — Isolation and egress

### 12. Isolate agent-generated code execution within hardened sandboxes
Code an agent generates and runs executes in a process sandbox, VM or WebAssembly
runtime with tight filesystem boundaries and egress controls, so buggy or malicious code
cannot reach the host, exfiltrate data or open the network.

- **Cap CPU, memory and runtime in sandboxes.** Resource limits stop runaway loops and exhaustion from spreading beyond the sandbox.
- **Allowlist filesystem access in agent environments.** Read and write only the named files and directories the task needs.
- **Harden the whole runtime, not just the sandbox.** The tools, browsers and libraries inside the sandbox are attack surface too.
- **Close OS-level bypasses of egress policy.** Built-in firewalls and NAT can silently override the agent's egress rules; verify that only allowed traffic is possible at the OS level.

### 13. Control every path out of the environment
Isolation fails at the exits. Every outbound channel an agent can reach is a way to
leak data or coordinate out of sight.

- **Verify isolation and egress of eval environments.** An environment labeled a simulation must actually be cut off from the internet and production; telling the agent it is a simulation does not make it one.
- **Isolate model development and testing environments** with the same network and tool limits as production sandboxes.
- **Ban public unauthenticated execution services.** Third-party sandboxes and code runners are staging grounds for attacks and a way around internal controls.
- **Monitor agent calls to external web services.** Wikis, URL shorteners, forums and JSON shares work as covert channels and exfiltration points; network blocking alone does not see intent.
- **Govern inter-agent communication explicitly.** Log and police the channels agents use to talk to each other, including notes left for future runs of themselves.

### 14. Keep sensitive data on trusted infrastructure
Bring the model to the data, not the data to the model provider.

- **Run sensitive-data models locally** or on private infrastructure when inputs are confidential.
- **Reason in the cloud, execute on-premises.** Cloud models can plan, while every tool call touching proprietary code, secrets or internal services runs inside the controlled environment.
- **Require consent for local file and desktop access.** A desktop agent asks at runtime before touching local files, other applications or system resources.

### Theme E — Identity and credentials

### 15. Give every agent a verifiable identity
Every agent runs as a unique, authenticated principal. That is what makes least
privilege enforceable, accountability possible and the audit trail attributable. Log
how an agent acquires new tools or roles mid-run, and authorize each change.

- **Keep credentials out of the model.** Task-scoped frameworks decrypt and inject credentials directly into the target system, so the model never sees a password or one-time code.
- **Inject credentials just in time, out of band.** No long-lived keys or broad service accounts sitting in the agent's environment; an agent that escapes its sandbox finds nothing to use.
- **Validate issuers and bind MCP client credentials.** The protocol checks who issued a client credential, so a spoofed agent or replayed token is refused.

## Adjacent Concerns

Added here by the weekly updater, owned by a sibling doc. One line each so the source
stays traceable; the practice itself lives at the link.

- **Treat agent capabilities as inspectable software artifacts** → [Code Review & AI Slop](../claude-code/code-review-and-ai-slop.md), *Make skills portable and inspectable*.
- **Scan agent skills for vulnerabilities before deployment** and **restrict package pre-execution hooks** → [Code Review & AI Slop](../claude-code/code-review-and-ai-slop.md), *Secure the toolchain and everything the agent installs*.
- **Integrate agent development into existing SDLC processes** → [Code Review & AI Slop](../claude-code/code-review-and-ai-slop.md), *Extend existing governance to agent-run pipeline steps*.
- **Define the agent harness explicitly** and **architect recurring tasks as interconnected loops** → [Code Review & AI Slop](../claude-code/code-review-and-ai-slop.md), *Treat the harness as the engineering problem*.
- **Have agents audit project goals and metrics** → [Code Review & AI Slop](../claude-code/code-review-and-ai-slop.md), *Spec first, then verify against the spec*.
- **Verify AI artifacts with deterministic checks** and **analyze agent code statically and dynamically** → [Code Review & AI Slop](../claude-code/code-review-and-ai-slop.md), *Build the review pipeline out of independent verifiers*.
- **Ship the reasoning trace with the artifact** → [Code Review & AI Slop](../claude-code/code-review-and-ai-slop.md), *Make the agent defend its reasoning*.
- **Let agents test their output in a sandbox** → [Code Review & AI Slop](../claude-code/code-review-and-ai-slop.md), *Validate in a real environment*.
- **Codify design boundaries as executable tests** → [Code Review & AI Slop](../claude-code/code-review-and-ai-slop.md), *Enforce architectural boundaries in CI*.
- **Use context-blind subagents for independent review** → [Model-Hierarchy Delegation](../claude-code/model-hierarchy-delegation.md), *Verify with a different, cheaper agent*.
- **Tell agents when to invoke each tool** → [Context & Memory Management](../claude-code/context-memory-management.md), *Rules files beat hoping*.
- **Test new skills against your own definition of done** → [Context & Memory Management](../claude-code/context-memory-management.md), *Skills as Institutional Memory*.
- **Set retention policy for captured interaction data** and **lifecycle agent persistent memory deliberately** → [Context & Memory Management](../claude-code/context-memory-management.md), what an agent stores and for how long.

## Anti-Patterns

-   **Acting on implied approval** — execution proceeds because nothing said no.
-   **Over-broad tools** — a write/delete tool exposed "just in case," reachable by any inference.
-   **Unsupervised irreversible actions** — money/deletes/prod-writes/sends with no human gate.
-   **Trusting "I did it / I recovered it"** — no independent verification of effect.
-   **Guessing through ambiguity** — proceeding when a precondition couldn't be confirmed.
-   **No audit trail** — can't reconstruct what the agent did, why, or who approved.
-   **Gate everything → alert fatigue** — so many approvals that humans rubber-stamp them.

## Self-Assessment

Use [`reviews/agent-action-safety-review.md`](../../reviews/agent-action-safety-review.md)
to have a repo inventory its agent actions, grade each tier's gating, and emit a tracked
checklist. Paste it into a Claude Code session in the target repo, or wire it into the
shared review workflow.

## Sources

Saved articles synthesized here (full summaries in `data/digest_knowledge/`):

-   **Trying the Software factory pattern.** (Will Larson (Irrational Exuberance)) — Design agents to proactively audit project goals and measurement systems, stopping to refine them with human operators if unclear. Digest: 2026-09-20.
-   **[AINews] Here are 6 Clones of Jev in 2 days** (Latent Space) — Implement mechanisms to ensure agent-reported confidence scores are accurately calibrated to reflect true probability of correctness. Digest: 2026-09-19.
-   **Can agents buy from your product? Three questions that tell you. Plus: Nate's Library MCP.** (Nate Jones) — Implement explicit financial spending limits for agents to constrain monetary outflows or resource consumption beyond compute resources. Digest: 2026-09-17.
-   **“Be transparent only if asked”: OpenAI’s models learned to leave notes for their future selves** (The New Stack) — Implement explicit policy and technical controls to govern and monitor all inter-agent communication, preventing unsanctioned coordination or information sharing. Digest: 2026-09-17.
-   **“Everyone’s in a race to replace GitHub”: Zed launches Delta because agents made pull requests obsolete** (The New Stack) — Integrate the agent's complete reasoning trace and decision-making context directly with agent-generated artifacts submitted for human review (e.g., code changes), making it readily accessible alongside the artifact itself. Digest: 2026-09-17.
-   **Muse review: The personal AI agent that gets consumer UX right** (Lenny's Newsletter) — Implement immediate human-initiated rollback or "undo" mechanisms for agent actions, especially those with high blast radius or potential for unintended consequences. Digest: 2026-09-16.
-   **Devin Got a Mac. Here’s the Handoff System for Shipping iOS Apps While You Sleep** (Ruben Dominguez (The AI Corner)) — Actively mitigate operating system-level behaviors or conflicts that could undermine or bypass an agent's network egress and access control policies. Digest: 2026-09-15.
-   **SRE Weekly Issue #534** (SRE Weekly) — Establish mechanisms to counteract "comprehension debt" and maintain human operators' deep understanding of systems managed or operated by AI agents. Digest: 2026-09-14.
-   **Researchers found that 1 in 5 MCP access policies came back broken or missing** (The New Stack) — Implement issuer validation and issuer-bound client credentials for agents interacting via protocols like the Model Context Protocol (MCP). Digest: 2026-09-10.
-   **Stop AI code sprawl before it destroys your software design** (The New Stack) — Enforce architectural integrity by implementing 'Executable Architecture' principles, using automated tests to codify and validate adherence to design boundaries. Digest: 2026-09-10.
-   **[AINews] Collusion.wiki: A second undisclosed OpenAI agent swarm incident...** (Latent Space) — Implement granular controls and monitoring over agents' interactions with external web services to prevent their abuse for covert communication, data exfiltration, or unauthorized state changes, even if the services themselves are not execution environments. Digest: 2026-09-05.
-   **AI agent evaluations are part of the product** (The New Stack) — integrate comprehensive, repeatable evaluation systems into release gates for all agent updates. Digest: 2026-09-04.
-   **“1% of my engineers are responsible for 40% of token spend”: Why Coder and SpaceXAI want to give developers nice things** (The New Stack) — implement a hybrid agent execution architecture where probabilistic reasoning and planning occur in cloud environments, while all tool calls and code execution interacting with sensitive data or internal systems are restricted to isolated, on-premises infrastructure. Digest: 2026-09-04.
-   **Your next OpenAI API timeout might not be a timeout at all** (The New Stack) — require API providers to clearly distinguish between standard errors and agent tasks stopped due to safety policy violations. Digest: 2026-09-03.
-   **This week in Claude Code (2026-08-28): /resume on desktop, phone-started sessions, subagent memory, cost tooling** (Claude Code weekly newsletter (email)) — securely manage and lifecycle agent-specific persistent memory. Digest: 2026-08-28.
-   **This week in Claude Code (2026-08-28): /resume on desktop, phone-started sessions, subagent memory, cost tooling** (Claude Code weekly newsletter (email)) — utilize 'context-blind' subagents for adversarial pre-review of agent-generated artifacts. Digest: 2026-08-28.
-   **Perplexity just separated reasoning from authority. Here’s why it matters for enterprises.** (The New Stack) — implement agent action authorization and execution as deterministic code separate from probabilistic reasoning models. Digest: 2026-08-26.
-   **How to build smarter OpenSearch alerts: Join our live conversation** (The New Stack) — establish an advanced, multi-signal correlation system for AI agent operational monitoring. Digest: 2026-08-20.
-   **“The opening stages of OpenAI’s unraveling”: OpenAI slows model training — not everyone is buying the explanation** (The New Stack) — implement stringent isolation and security controls for AI model development and internal testing environments. Digest: 2026-08-20.
-   **smolmachines / smolvm as a sandbox for untrusted Python & JavaScript** (Simon Willison) — enforce explicit allowlists for filesystem access within agent execution environments. Digest: 2026-08-20.
-   **smolmachines / smolvm as a sandbox for untrusted Python & JavaScript** (Simon Willison) — implement granular resource limits (CPU, RAM, execution time) for agent-generated code execution within sandboxes. Digest: 2026-08-20.
-   **ChatGPT can now remember what you did on your Mac — without screenshots** (The New Stack) — establish clear policies and technical controls for the lifecycle, retention, and security of user interaction data. Digest: 2026-08-14.
-   **Auto Mode will soon be the default in Claude Code — because humans can’t be trusted** (The New Stack) — implement an AI-driven pre-screening layer to filter routine agent actions. Digest: 2026-08-08.
-   **The npm attack that turned provenance attestations into camouflage** (The New Stack) — scrutinize and restrict the use of pre-execution hooks in software packages. Digest: 2026-08-07.
-   **The “AI kill switch” assumes you know what you are trying to shut down** (The New Stack) — develop a comprehensive, up-to-date dependency map for emergency shutdown. Digest: 2026-08-07.
-   **Your AI agent’s next tool call may be valid but wrong. AWS’s Dogwood promises to fix that.** (The New Stack) — implement policy engines capable of evaluating and authorizing entire sequences of agent actions. Digest: 2026-08-07.
-   **Build an AI code review bot in 30 minutes with Vercel Eve** (Lenny's Newsletter) — extend action classification for agent-driven code review processes. Digest: 2026-08-05.
-   **Build an AI code review bot in 30 minutes with Vercel Eve** (Lenny's Newsletter) — ensure agent-driven automatic approval processes generate comprehensive, auditable, and queryable records adhering to compliance standards. Digest: 2026-08-05.
-   **datasette-apps 0.2a0** (Simon Willison) — enable agents to perform independent functional and integration testing in sandboxed browser environments. Digest: 2026-08-02.
-   **Somebody else decided what good looks like, and it shipped with the skill you installed. Here's the guide to fix it.** (Nate Jones) — implement a systematic functional validation process for newly acquired or developed agent skills. Digest: 2026-08-01.
-   **Investigating three real-world incidents in our cybersecurity evaluations** (Simon Willison [security]) — Rigorously verify the isolation and network egress configurations of all agent evaluation environments. Digest: 2026-07-31.
-   **Ontologies Are So Back: Why AI Agents Are Reviving the Semantic Web** (Latent Space [ai_engineering]) — Implement ontologies to provide logical guardrails for agentic systems. Digest: 2026-07-30.
-   **OpenAI and Elastic are tackling the AI problem enterprises can’t ignore** (The New Stack [security]) — Integrate AI agent data retrieval with existing enterprise Role-Based Access Control (RBAC) systems. Digest: 2026-07-30.
-   **Why linting alone can’t govern agentic development** (The New Stack [devops]) — Employ advanced static and dynamic analysis methods to verify agent-generated code behavior across the entire system. Digest: 2026-07-30.
-   **When do AI agents need permission boundaries?** (The New Stack [security]) — Decouple AI agent tool selection from action authorization, using a robust policy engine for enforcement. Digest: 2026-07-30.
-   **Anatomy of a Frontier Lab Agent Intrusion: A Technical Timeline of the July 2026 Incident** (Simon Willison [security]) — Prohibit AI agents from utilizing public, unauthenticated external code execution or evaluation services. Digest: 2026-07-29.
-   **The AI “vibe shift”: Why NanoClaw and Echo have teamed up to stop the next Hugging Face Breach** (The New Stack [security]) — Harden the entire AI agent runtime environment, extending protection beyond isolation to included tools, browsers, and libraries. Digest: 2026-07-29.
-   **Sam Altman on model distillation: “This is not in my top ten list of worries”** (The New Stack [security]) — Implement just-in-time credential injection and out-of-band authentication for AI agents. Digest: 2026-07-28.
-   **Agents keep changing their answers. Harness just built delivery pipelines that don’t care.** (The New Stack [devops]) — integrate agent development into existing, robust SDLC processes. Digest: 2026-07-22.
-   **Executive Briefing: How Microsoft, Bayer, and Discovery Use AI on the Data You Can't Upload** (Nate Jones [ai_strategy]) — deploy models and agents to operate on sensitive data locally or within controlled, isolated environments. Digest: 2026-07-19.
-   **1Password’s new browser integration for Claude changes how AI uses your credentials** (The New Stack [security]) — implement secure, zero-exposure credential management mechanisms for agents. Digest: 2026-07-17.
-   **Your skills are leaving your hands. Don't let a rent-a-brain keep them.** (Nate Jones [ai_strategy]) — export and manage agent skills as inspectable assets. Digest: 2026-06-19.
-   **Chainguard Agent Skills matures** (The New Stack [devops]) — implement automated scanning for common attack patterns in agent skills. Digest: 2026-06-17.
-   **Agent Toolkit for AWS includes 20+ agent skills, but your agent might not load them without this one file** (The New Stack) — prescriptive guidance. Digest: 2026-06-25.
-   **Executive Briefing: Your company is about to get cheap intelligence. That is not the same as being able to use it.** (Nate Jones [ai_strategy]) — define operational context, governance, and boundaries with a structural layer. Digest: 2026-06-14.
-   **What a harness is and how to build one with Claude Agent SDK** (Lenny's Newsletter [product]) — embed specific, granular authorization rules directly within agent harnesses. Digest: 2026-07-08.
-   **You gave your AI agent real tools — the 4-part control layer it's missing / the Judge Layer implementation guide** (Nate Jones) — action classification, specialist judges, memory governance, structured write-back. Digest: 2026-05-16 (command-center, crumbl-ops).
-   **Six layers your agent has to handle (+ a responsibility-layer audit)** (Nate Jones) — identity, authorization, fraud, liability for acting agents. Digest: 2026-05-18 (wealth-mgmt, crumbl-ops).
-   **Your AI coding agent deleted 2.5 years of customer data in minutes** (Nate Jones) — "locally correct, organizationally catastrophic"; fail-safe + human oversight. Digest: 2026-03-27 (crumbl-ops).
-   **The AI code review checklist that prevents the next $1M production incident** (Ruben Dominguez) — agent dropped prod DB and lied about recovery; accountability. Digest: 2026-05-16 (command-center).
-   **Kiro goes mobile: AWS brings agentic coding supervision to the iPhone** (The New Stack [devops]) — integrate notification systems and remote interfaces for asynchronous oversight. Digest: 2026-06-17.
-   **The hidden cost of build vs. buy for agentic AI in regulated industries** (The New Stack) — orchestration, governance, compliance for agent platforms. Digest: 2026-05-18 (wealth-mgmt).
-   **Why agent harnesses fail inside cloud-native systems** (The New Stack) — context policies, sandboxes, feedback loops. Digest: 2026-05-18 (command-center).
-   **AI Agents of the Week: Papers You Should Know About** (Pascal Biese (LLM Watch) [ai_engineering]) — assess the agent's entire execution trajectory, not just the final outcome. Digest: 2026-06-14.
-   **Your engineering org needs an AI slop registry** (The New Stack) — independent, deterministic verification. Digest: 2026-06-26.
-   **Anthropic’s Claude Sonnet 5 system card says more about the future of AI than its benchmarks do** (The New Stack) — robustness testing for prompt injection across all agent interaction surfaces, especially when interacting with untrusted external content. Digest: 2026-07-01.
-   **Anthropic’s Claude Sonnet 5 system card says more about the future of AI than its benchmarks do** (The New Stack) — employ adversarial evaluation methods to detect covert agent behavior and the pursuit of hidden objectives. Digest: 2026-07-01.
-   **Why traditional CI/CD fails for LLMs (and the release gates we built to fix it)** (The New Stack) — utilize shadow validation as a release gate for probabilistic agent updates to detect silent regressions. Digest: 2026-07-02.
-   **Why traditional CI/CD fails for LLMs (and the release gates we built to fix it)** (The New Stack) — implement continuous drift detection for agent behavior and underlying models. Digest: 2026-07-02.
-   **Vercel launches eve, an open-source framework that treats agents as directories** (The New Stack [devops]) — design agent tasks to create checkpoints after each significant step. Digest: 2026-06-17.
-   **The Five Questions That Turn a Messy Task Into an AI Loop (+ the prompts to map yours)** (Nate Jones) — interconnected loops architecture. Digest: 2026-06-24.
-   **How we contain Claude across products** (Simon Willison) — isolate agent-generated code execution in hardened sandboxes. Digest: 2026-05-31.
-   **The AI agent identity problem nobody’s talking about** (The New Stack) — distinct, verifiable identity and dynamic permission management. Digest: 2026-06-26.
-   **AWS, Microsoft, and Google agree the session is the new unit of compute. They disagree on how to isolate it.** (The New Stack) — session-aware runtimes. Digest: 2026-06-26.
-   **Quoting OpenAI** (Simon Willison [ai_engineering]) — explicit user consent and granular access controls for local file/desktop interactions. Digest: 2026-07-10.
-   **Replit’s vibe coding platform just got a Visa-backed identity layer for AI agents — and it changes how agents spend money** (The New Stack) — distinct, authenticated identity layer for financial transactions. Digest: 2026-05-30.

## Where Used

-   **crumbl-ops** — the model implementation: agent-facing MCP is read-only by construction (zero write tools); money movement happens only in a non-interactive `daily_sync` job that gates unbalanced journal entries in code, with destructive context externalized into per-module `CLAUDE.md` + path-scoped rules (validated in the #473 audit, area #6 = Good).
-   **command-center** — agents take outbound actions (digest emails, Slack, iMessage flags); highest need for a judge layer + human approval on sends, with structured logging of each action.
-   **wealth-mgmt** — any "actionable thesis" / advisory action in a regulated context needs the authorization-spec + audit-trail layers before it can move beyond information.
