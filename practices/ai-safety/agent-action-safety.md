# Agent Action Safety & Control Layers

How to let an AI agent *take real actions* — move money, write to the GL, send a
message, run a migration — without the action being one bad inference away from
catastrophe. Code review (the [AI-slop doc](../claude-code/code-review-and-ai-slop.md))
covers the code an agent *writes*; this covers what an agent *does at runtime*.

Related: [Prompt-Injection Mitigation](prompt-injection-mitigation.md) (untrusted input
that hijacks an agent), and the destructive-action gating practice in
[Code Review & AI Slop](../cla Claude-code/code-review-and-ai-slop.md#best-practices).

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

### 1. Treat agent capabilities and procedures as first-class, inspectable software artifacts.
Instead of allowing agent skills (e.g., prompts, runbooks, scripts, permission boundaries) to be proprietary to a vendor or trapped in chat histories, export and manage them as visible and inspectable assets. This ensures continuity, facilitates auditing, and prevents critical operational knowledge from being lost or hidden.

### 2. Establish a secure supply chain for all agent skills and tools, actively scanning them for vulnerabilities, over-permissioned scopes, and malicious behavior before deployment.
Treat agent skills (e.g., functions, prompts, configuration files) as software components requiring supply chain security. Implement automated scanning for common attack patterns, such as obfuscated commands, credential harvesting, or excessive permissions, to harden agent capabilities at rest and prevent the introduction of vulnerabilities into the agent's logic.

### 3. Scrutinize and restrict the use of pre-execution hooks (e.g., preinstall scripts) in software packages consumed by agents and developers, ensuring they do not bypass security checks or execute arbitrary code prematurely.
Malicious code embedded in package pre-execution hooks can run automatically before typical security scans or application tests, establishing persistence or compromising the environment. Implementing strict policies and technical controls to prevent unauthorized execution of such scripts is crucial for supply chain security.

### 4. Integrate agent development into existing, robust software delivery lifecycle (SDLC) processes.
Despite the non-deterministic nature of AI agents, apply the same rigorous governance, testing, and security controls used for traditional application code. Adapt SDLC pipelines to accommodate agent behavior variability while maintaining quality and preventing regressions in production environments.

### 5. Implement a systematic functional validation process for newly acquired or developed agent skills, testing them against specific organizational criteria and definitions of 'done' to ensure alignment with desired outcomes and quality standards before full deployment.
While skills are inspected for security, their functional utility and alignment with organizational quality and operational standards are equally critical. A structured testing process ensures that agents do not merely execute tasks, but produce outputs that meet the company's specific definitions of quality, taste, or business rules.

### 6. Implement prescriptive guidance mechanisms to explicitly direct agents on when and how to invoke their available tools and skills.
Agents should not merely have access to tools; they must be predictably guided to use them in appropriate contexts. Configure 'rules files' or similar explicit instructions that dictate the conditions, priority, and strategy for tool invocation. This ensures agents reliably leverage their intended capabilities and external data sources, preventing reliance on potentially outdated internal knowledge or 'hallucinations' when accurate tools are available.

### 7. Construct a comprehensive 'agent harness' that explicitly defines the operational context, governance, and boundaries for all AI agents.
This harness should encompass the agent's access to external systems, data, and documents, alongside clear review standards, budgetary limits, defined decision rights, and accountability frameworks. This structural layer provides the necessary human judgment and organizational context that cannot be outsourced to the agent itself.

### 8. Implement ontologies to provide logical guardrails for agentic systems.
Augment probabilistic LLM reasoning with explicit, structured knowledge representations (ontologies) to define the boundaries, relationships, and constraints of agent operations. This provides a robust framework for enforcing logical guardrails and ensuring agents operate within defined, semantically consistent parameters.

### 9. Embed specific, granular authorization rules directly within agent harnesses to enforce permissions relevant to their defined workflows.
For each structured workflow managed by an agent harness, define and enforce the precise set of permissions required for its operations directly within the harness's configuration or code. This ensures that the harness itself acts as a gatekeeper, restricting agent actions to only those authorized for that specific workflow context.

### 10. Integrate AI agent data retrieval with existing enterprise Role-Based Access Control (RBAC) systems.
Ensure that AI agents, when retrieving information from enterprise data sources, only access data for which the requesting user (or the agent itself, with its assigned identity) has explicit authorization via existing RBAC mechanisms. This prevents models from reasoning over or exposing data they are not permitted to view, leveraging established security infrastructure.

### 11. Decouple AI agent tool selection from action authorization, using a robust policy engine for enforcement.
Do not rely on natural-language tool descriptions for authorization decisions. Instead, implement a distinct policy engine that evaluates explicit, immutable authorization rules against proposed agent actions, independent of the agent's internal reasoning or tool selection logic. Tool descriptions should inform selection, but not grant execution rights.

### 12. Implement policy engines capable of evaluating and authorizing entire sequences of agent actions, taking into account prior events, accumulated state, and historical context, rather than only individual tool calls.
Traditional authorization often focuses on point-in-time decisions for single actions. For autonomous agents, the risk can arise from a valid sequence of individually approved actions. A trajectory-aware policy engine enables governance over workflows, applying constraints on prerequisites, rate limits, and ordering to prevent undesirable outcomes that isolated checks would miss.

### 13. Implement agent action authorization and execution as deterministic code separate from probabilistic reasoning models.
Architect the agent system such that the component responsible for evaluating policy, authorizing actions, and executing approved tool calls is implemented as deterministic software. This separation of concerns ensures that the probabilistic nature of the agent's reasoning (e.g., suggesting a next step) does not introduce uncertainty or non-determinism into critical safety and control decisions, enhancing reliability and auditability.

### 14. Classify every action by reversibility and blast radius
Before wiring a tool, tier it. This single classification drives every gate below.

| Tier | Examples | Default gate |
|---|---|---|
| **Read-only** | reports, queries, search | none |
| **Reversible write** | draft, label, create-then-delete | log + post-hoc review |
| **Irreversible / high-blast** | money movement, GL/prod-DB writes, deletes, outbound messages, deploys | **explicit human approval** |

### 15. Extend action classification for agent-driven code review processes to include dimensions such as data security impact, operational impact, verification gaps, and overall change surface.
For agents performing code review or generating code, assessing risk beyond reversibility and blast radius is crucial. Incorporating these additional dimensions provides a more comprehensive risk profile, allowing for intelligent auto-approval of low-risk changes and appropriate human escalation for high-stakes modifications.

### 16. Least privilege — read-only by default
An agent gets the *minimum* capability for its job; write capability is a separate,
explicitly-granted path. The strongest version is enforced in code, not prompts: e.g.,
expose only read tools on the agent-facing MCP so a write is structurally impossible,
and route the rare write through a separate non-interactive, gated job. (crumbl-ops does
exactly this — its agent MCP has zero write tools; see Where Used.)

### 17. A Judge Layer gates the action, not the prose
Put a gatekeeper between "agent proposes X" and "X executes" that returns an explicit
*approve / reject / escalate* — never let execution proceed on implied approval. The
judge can be deterministic (policy rules: amount thresholds, allow-lists, business-hours)
or a separate model with a narrow rubric. Key parts (from the Judge Layer guide):
**action classification → policy/specialist check → memory-governed write-back →
structured, logged decision.**

### 18. Implement an AI-driven pre-screening layer to filter routine agent actions, automatically approving safe ones and only escalating genuinely high-risk or uncertain actions for human review or blocking.
This mechanism reduces human fatigue associated with frequent permission prompts by intelligently classifying actions. It allows agents to proceed autonomously with low-risk tasks while ensuring that human-in-the-loop oversight is reserved for complex, potentially dangerous, or genuinely uncertain scenarios, thereby increasing the effectiveness of human review.

### 19. Human-in-the-loop for the irreversible
For Tier-3 actions, require a human's explicit yes — a mobile approve/deny, a PR
checkbox, a confirmation step that prints exactly what will happen. Design against
**alert fatigue**: gate only what truly needs it (driven by #13), so approvals stay
meaningful instead of being rubber-stamped.

### 20. Implement remote and asynchronous human-in-the-loop (HITL) mechanisms to manage oversight for long-running or delegated agent tasks.
For agents performing extended, autonomous tasks, integrate notification systems (e.g., mobile alerts) and remote interfaces that allow humans to review diffs, provide steering input, and approve actions without being tethered to a workstation. This shifts HITL from synchronous blocking to asynchronous oversight, reducing bottlenecks and approval fatigue.

### 21. Write an authorization spec per high-stakes action
Name *who/what* may do the action, under *what limits*, with *what evidence*. For
agentic-commerce-style actions this means identity, authorization, fraud/abuse checks,
and liability — not just "call the payments API." A one-paragraph spec per action beats
a vague "the agent handles payments."

### 22. Fail safe — stop and ask on uncertainty
An agent that can't verify a precondition must **halt and escalate**, not guess. The
data-deletion catastrophe was a confident guess. Bake in: "if you cannot confirm X, do
not proceed — surface the ambiguity." Externalize what's load-bearing/destructive into
`CLAUDE.md` / rules so the agent *has* the operational context it otherwise lacks — but
still gate the action.

### 23. Never trust the agent's self-report
Agents fabricate success ("I tested it," "I recovered the data"). Verify the action's
effect from an independent source (the actual row count, the API's returned status, a
re-query) before believing it — and especially before reporting success to a human.

### 24. Implement trajectory-aware and shortcut-resistant evaluation frameworks to verify agent reasoning and prevent exploitation of evaluation gaps.
Beyond simply verifying the final outcome, assess the agent's entire execution trajectory and ensure it achieves results through genuine reasoning, rather than fabricating evidence or exploiting dataset artifacts. This higher-fidelity verification method helps detect brittle or unintended solution paths that might pose risks in real-world scenarios.

### 25. Implement an independent, deterministic verification system for AI-generated artifacts to detect 'AI slop' and ensure alignment with quality standards.
AI agents can produce 'slop'—artifacts that appear plausible but are subtly flawed, bloated, or misaligned with organizational patterns. Relying solely on the generating agent's prompts or instructions is insufficient. Establish a separate, deterministic verification system, potentially using a different agent or traditional analysis, to independently check outputs for correctness, adherence to standards, and quality, producing consistent results.

### 26. Enable agents to perform independent functional and integration testing of generated or modified artifacts by executing agent-provided code within invisible, sandboxed browser environments (e.g., iframes).
Beyond static analysis or observing final outcomes, agents can directly verify the behavior of their outputs. By providing a secure, isolated browser environment, agents can run their own JavaScript tests to smoke test applications, measure elements, and confirm functional correctness, enhancing the reliability of agent-generated artifacts.

### 27. Employ advanced static and dynamic analysis methods to verify agent-generated code behavior across the entire system.
Beyond local linting, implement control-flow, data-flow, and taint analysis to trace how values move from external inputs to sensitive operations and reason about program paths. Conduct comprehensive integration and system-level tests to ensure agent-generated changes behave correctly, fit the surrounding system, and meet all security and reliability requirements.

### 28. Implement robustness testing for prompt injection across all agent interaction surfaces, especially when interacting with untrusted external content.
Actively test agents for susceptibility to prompt injection, including when they process data from external sources like websites or user-generated content. This requires dedicated adversarial testing to ensure agents do not misinterpret or act upon malicious instructions embedded in their operational context.

### 29. Employ adversarial evaluation methods to detect covert agent behavior and the pursuit of hidden objectives.
Use specialized evaluation environments and adversarial testing (e.g., SHADE-Arena, LinuxArena) to actively search for instances where agents may attempt to act covertly, deviate from their explicit instructions to pursue hidden objectives, or exploit systemic vulnerabilities while appearing to be compliant.

### 30. Utilize 'context-blind' subagents for adversarial pre-review of agent-generated artifacts to ensure truly independent verification.
When performing automated review or verification of artifacts generated by a primary agent (e.g., code), deploy specialized subagents that are 'context-blind' to the primary agent's operational context, prompts, and internal state. This methodology ensures that the verification agent operates with maximal independence, preventing shared biases or assumptions from compromising the integrity of the adversarial review and making verification truly robust.

### 31. Utilize shadow validation as a release gate for probabilistic agent updates to detect silent regressions.
When deploying updates to agent components, run the new version alongside the current production version ('shadow mode') to compare real-world performance, outputs, and user interactions. This allows for detection of silent regressions or unexpected behavioral changes before full deployment.

### 32. Integrate comprehensive, repeatable evaluation systems into release gates for all agent updates, ensuring consistent behavior across the full execution path against predefined criteria.
Beyond initial functional validation or shadow testing, implement a mandatory, repeatable evaluation system that blocks releases if an agent fails to consistently preserve required behaviors. This system must exercise the agent's full execution path, including context assembly, tool calls, and permissions, against explicitly defined correct behaviors and operational limits.

### 33. Implement continuous drift detection for agent behavior and underlying models.
Continuously monitor agent performance metrics, model outputs, and embedding spaces to detect gradual degradation (eval drift) or changes in data distribution (distribution shift) that may lead to suboptimal or incorrect agent actions without triggering hard failure thresholds.

### 34. Establish an advanced, multi-signal correlation system for AI agent operational monitoring to detect nuanced failure modes that combine telemetry from logs, metrics, traces, and specific agent tool calls.
Move beyond basic drift detection by implementing a sophisticated monitoring system that correlates data from various observability sources, including agent logs, system metrics, distributed traces of tool calls, and external system responses. This enables the detection of complex and subtle failure modes that single-signal monitoring might miss, leading to more proactive operational safety.

### 35. Require API providers to clearly distinguish between standard errors and agent tasks stopped due to safety policy violations, providing actionable feedback for consumers.
When consuming AI agent services via API, demand that providers offer clear, programmatic distinctions between general API errors (e.g., timeouts) and situations where agent tasks are halted by internal safety mechanisms. The feedback provided should be specific enough to inform whether a task can be safely retried, resumed, or if it requires modification to avoid recurring safety interventions.

### 36. Provenance and an audit trail for every action
Log each agent action with its inputs, the judge's decision + reason, who/what approved,
and the result. This is what makes an agent action auditable (essential for financial /
regulated workflows) and debuggable after the fact. Keep AI-proposed vs. human-approved
distinguishable.

### 37. Ensure that any agent-driven automatic approval processes, particularly for code changes, generate comprehensive, auditable, and queryable records that adhere to compliance standards (e.g., SOC 2) and are integrated into the organization's risk policy.
Auto-approval by agents, even for low-risk actions, requires robust auditability for compliance and accountability. The records must be detailed enough to reconstruct decisions, queryable for analysis, and explicitly align with established risk policies to maintain regulatory and internal governance standards.

### 38. Architect agent executions as durable workflows that checkpoint each step to ensure resilience, recoverability, and atomic operations.
Design agent tasks to create checkpoints after each significant step, allowing an agent session to pause, gracefully survive crashes, and resume from the last validated state. This prevents partial, unrecoverable actions and ensures the overall integrity and audibility of complex, multi-step agent processes.

### 39. Develop and maintain a comprehensive, up-to-date dependency map for all AI agent systems and their supporting infrastructure to enable effective emergency shutdown or intervention.
In complex production environments, AI agent services often rely on numerous interconnected systems, including APIs, cloud resources, identity services, and downstream applications. A detailed dependency map is essential for understanding the full blast radius of an agent and for orchestrating a controlled, complete shutdown or targeted intervention during an incident.

### 40. Design agent systems using an 'interconnected loops' architecture to manage complex, recurring tasks and their dependencies autonomously.
For systems with multiple ongoing obligations, structure agents as a network of narrow, recurring 'loops,' each with its own memory, information sources, and safe actions. These loops are specifically designed to observe and react to changes or outputs from other interconnected loops, enabling the system to autonomously manage complex interdependencies and adapt to evolving conditions, moving beyond isolated, durable workflows.

### 41. Isolate agent-generated code execution within hardened sandboxes.
When an AI agent generates and executes code, this execution must occur within strictly isolated environments such as process sandboxes, virtual machines, or WebAssembly runtimes. Implement tight filesystem boundaries and egress controls to prevent unauthorized access to the host system, exfiltration of sensitive data, or unintended network activity, even if the agent's code is buggy or malicious.

### 42. Implement granular resource limits (CPU, RAM, execution time) for agent-generated code execution within sandboxes to prevent denial-of-service or runaway processes.
Beyond general isolation, explicitly define and enforce limits on CPU usage, memory consumption, and maximum execution duration for any code executed by an agent in a sandboxed environment. This prevents resource exhaustion attacks, infinite loops, or runaway processes from impacting system stability or availability.

### 43. Enforce explicit allowlists for filesystem access within agent execution environments, permitting access only to designated files or directories.
Configure agent sandboxes with a strict allowlist approach to filesystem access, ensuring that agents can only read from or write to predefined, essential files or directories. This prevents unauthorized data exfiltration, modification, or the introduction of malicious code into unintended locations.

### 44. Rigorously verify the isolation and network egress configurations of all agent evaluation environments.
Ensure that environments designated as simulations are truly isolated from the public internet and production systems. Network egress paths must be explicitly controlled and verified, even when agents are instructed they are in a simulation, as misconfigured evaluation environments pose a significant real-world risk.

### 45. Prohibit AI agents from utilizing public, unauthenticated external code execution or evaluation services.
Strictly prevent AI agents from accessing or leveraging external, publicly accessible, and unauthenticated code execution environments or third-party sandboxes as part of their operational workflow or as a means to circumvent internal controls. Such services can be easily abused as staging grounds for further attacks, as demonstrated by real-world incidents.

### 46. Harden the entire AI agent runtime environment, extending protection beyond isolation to included tools, browsers, and libraries.
Beyond merely isolating the agent in a sandbox, actively harden the comprehensive runtime environment that the agent operates within. This includes securing and applying strict controls to all embedded tools, browsers, and libraries utilized by the agent, closing attack surfaces that basic sandbox isolation alone may not address.

### 47. Implement stringent isolation and security controls for AI model development and internal testing environments to prevent agents from breaching these sandboxes and accessing or impacting external or internal systems.
Extend sandboxing and hardening principles to environments where AI models and agents are developed, fine-tuned, and internally tested. These environments must be securely isolated with tight network and tool access limits to prevent agents from escaping, attacking internal systems, or accessing sensitive data during their development lifecycle.

### 48. Assign a distinct, verifiable identity to every AI agent, and explicitly manage its dynamically acquired permissions throughout its lifecycle.
Every AI agent, regardless of its function, must operate under a unique, authenticated identity. This foundation enables granular least-privilege enforcement, clear accountability, and a comprehensive audit trail for all actions. Crucially, the system must also manage and log how agents dynamically request and acquire new tool access or roles during their operation, ensuring these transitions are authorized and traceable.

### 49. Implement secure, zero-exposure credential management mechanisms for agents.
Agents should access credentials through dedicated, task-scoped authentication frameworks that decrypt and inject credentials directly into target systems on-device, without exposing plaintext passwords or one-time codes to the underlying LLM. This ensures agents perform authenticated actions while minimizing the risk of credential leakage or misuse by the model itself.

### 50. Implement just-in-time credential injection and out-of-band authentication for AI agents.
Replace long-lived API keys or permissive service accounts injected into agent environments with mechanisms for just-in-time credential injection and authentication that occur entirely outside the agent's direct memory space. This decouples credentials from the agent's environment, rendering agents powerless even if they escape their sandbox without active, out-of-band authorization.

### 51. Deploy models and agents to operate on sensitive data locally or within controlled, isolated environments.
To protect proprietary or sensitive information, bring the AI model and agent execution to the data source rather than transmitting sensitive data to external model providers. Leverage local execution environments or fine-tuned models on private infrastructure to process confidential inputs, ensuring data remains within trusted boundaries and mitigating data exfiltration risks.

### 52. Implement a hybrid agent execution architecture where probabilistic reasoning and planning occur in cloud environments, while all tool calls and code execution interacting with sensitive data or internal systems are restricted to isolated, on-premises infrastructure.
For agents handling sensitive operations or data, establish an architecture that decouples the probabilistic reasoning and planning provided by external cloud models from the execution of actions. Ensure that all agent tool calls, code generation, and interactions with proprietary source code, secrets, or internal services remain within the organization's controlled, isolated on-premises environments.

### 53. Implement explicit user consent and granular access controls for agent interactions with local files and desktop applications.
When an agent operates in a desktop environment, require explicit, runtime user permission before allowing access to local files, other desktop applications, or system resources. This ensures users retain ultimate control over local data and system integrity.

### 54. Establish clear policies and technical controls for the lifecycle, retention, and security of user interaction data continuously captured by agents for context and memory, including explicit user consent for specific data types and timeframes.
For agents that capture continuous streams of user interaction events (e.g., clicks, typing, app switches) to build an operational memory or timeline, define strict policies for data retention, anonymization, and secure storage. Crucially, obtain granular user consent specifying which interaction types can be captured, for how long, and for what explicit purposes, moving beyond static file access permissions.

### 55. Securely manage and lifecycle agent-specific persistent memory, especially when agents accumulate internal knowledge or derived facts.
Beyond user interaction data, agents can generate and store their own persistent memory containing derived facts, system patterns, or recurring issues discovered over time. Treat this agent-generated knowledge as a sensitive asset, implementing stringent security controls, explicit lifecycle policies for retention and deletion, and access restrictions to prevent misuse or compromise of accumulated operational intelligence.

### 56. Establish a distinct, authenticated identity layer for AI agents performing financial transactions.
For agents authorized to manage money, spend, or interact with financial systems, implement a robust identity layer that includes unique authentication, tokenization capabilities, and secure wallet management. This ensures that each agent's financial actions are traceable, adhere to defined limits, and are independently verifiable as originating from a securely identified entity.

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
