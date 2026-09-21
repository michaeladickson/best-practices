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

### 2. Scan agent skills for vulnerabilities before deployment
Treat agent skills (e.g., functions, prompts, configuration files) as software components requiring supply chain security. Implement automated scanning for common attack patterns, such as obfuscated commands, credential harvesting, or excessive permissions, to harden agent capabilities at rest and prevent the introduction of vulnerabilities into the agent's logic.

### 3. Restrict package pre-execution hooks
Malicious code embedded in package pre-execution hooks can run automatically before typical security scans or application tests, establishing persistence or compromising the environment. Implementing strict policies and technical controls to prevent unauthorized execution of such scripts is crucial for supply chain security.

### 4. Integrate agent development into existing, robust software delivery lifecycle (SDLC) processes.
Despite the non-deterministic nature of AI agents, apply the same rigorous governance, testing, and security controls used for traditional application code. Adapt SDLC pipelines to accommodate agent behavior variability while maintaining quality and preventing regressions in production environments.

### 5. Test new skills against your own definition of done
While skills are inspected for security, their functional utility and alignment with organizational quality and operational standards are equally critical. A structured testing process ensures that agents do not merely execute tasks, but produce outputs that meet the company's specific definitions of quality, taste, or business rules.

### 6. Tell agents when to invoke each tool
Agents should not merely have access to tools; they must be predictably guided to use them in appropriate contexts. Configure 'rules files' or similar explicit instructions that dictate the conditions, priority, and strategy for tool invocation. This ensures agents reliably leverage their intended capabilities and external data sources, preventing reliance on potentially outdated internal knowledge or 'hallucinations' when accurate tools are available.

### 7. Define the agent harness explicitly
This harness should encompass the agent's access to external systems, data, and documents, alongside clear review standards, budgetary limits, defined decision rights, and accountability frameworks. This structural layer provides the necessary human judgment and organizational context that cannot be outsourced to the agent itself.

### 8. Implement ontologies to provide logical guardrails for agentic systems.
Augment probabilistic LLM reasoning with explicit, structured knowledge representations (ontologies) to define the boundaries, relationships, and constraints of agent operations. This provides a robust framework for enforcing logical guardrails and ensuring agents operate within defined, semantically consistent parameters.

### 9. Embed authorization rules in the harness
For each structured workflow managed by an agent harness, define and enforce the precise set of permissions required for its operations directly within the harness's configuration or code. This ensures that the harness itself acts as a gatekeeper, restricting agent actions to only those authorized for that specific workflow context.

### 10. Reuse existing RBAC for agent retrieval
Ensure that AI agents, when retrieving information from enterprise data sources, only access data for which the requesting user (or the agent itself, with its assigned identity) has explicit authorization via existing RBAC mechanisms. This prevents models from reasoning over or exposing data they are not permitted to view, leveraging established security infrastructure.

### 11. Decouple tool selection from action authorization
Do not rely on natural-language tool descriptions for authorization decisions. Instead, implement a distinct policy engine that evaluates explicit, immutable authorization rules against proposed agent actions, independent of the agent's internal reasoning or tool selection logic. Tool descriptions should inform selection, but not grant execution rights.

### 12. Authorize action sequences, not single calls
Traditional authorization often focuses on point-in-time decisions for single actions. For autonomous agents, the risk can arise from a valid sequence of individually approved actions. A trajectory-aware policy engine enables governance over workflows, applying constraints on prerequisites, rate limits, and ordering to prevent undesirable outcomes that isolated checks would miss.

### 13. Keep authorization in deterministic code
Architect the agent system such that the component responsible for evaluating policy, authorizing actions, and executing approved tool calls is implemented as deterministic software. This separation of concerns ensures that the probabilistic nature of the agent's reasoning (e.g., suggesting a next step) does not introduce uncertainty or non-determinism into critical safety and control decisions, enhancing reliability and auditability.

### 14. Classify every action by reversibility and blast radius
Before wiring a tool, tier it. This single classification drives every gate below.

| Tier | Examples | Default gate |
|---|---|---|
| **Read-only** | reports, queries, search | none |
| **Reversible write** | draft, label, create-then-delete | log + post-hoc review |
| **Irreversible / high-blast** | money movement, GL/prod-DB writes, deletes, outbound messages, deploys | **explicit human approval** |

### 15. Classify review actions by blast radius
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

### 18. Pre-screen routine actions, escalate the rest
This mechanism reduces human fatigue associated with frequent permission prompts by intelligently classifying actions. It allows agents to proceed autonomously with low-risk tasks while ensuring that human-in-the-loop oversight is reserved for complex, potentially dangerous, or genuinely uncertain scenarios, thereby increasing the effectiveness of human review.

### 19. Human-in-the-loop for the irreversible
For Tier-3 actions, require a human's explicit yes — a mobile approve/deny, a PR
checkbox, a confirmation step that prints exactly what will happen. Design against
**alert fatigue**: gate only what truly needs it (driven by #13), so approvals stay
meaningful instead of being rubber-stamped.

### 20. Give every high-blast-radius action an undo
For certain agent actions, particularly those that are technically reversible or where a swift reversal can mitigate harm, provide users with an immediate 'undo' or rollback capability. This mechanism allows a human operator to reverse an agent's executed action within a defined timeframe, adding a layer of post-execution safety and reducing the impact of erroneous or misaligned agent behavior without requiring pre-approval.

### 21. Support remote and asynchronous human approval
For agents performing extended, autonomous tasks, integrate notification systems (e.g., mobile alerts) and remote interfaces that allow humans to review diffs, provide steering input, and approve actions without being tethered to a workstation. This shifts HITL from synchronous blocking to asynchronous oversight, reducing bottlenecks and approval fatigue.

### 22. Write an authorization spec per high-stakes action
Name *who/what* may do the action, under *what limits*, with *what evidence*. For
agentic-commerce-style actions this means identity, authorization, fraud/abuse checks,
and liability — not just "call the payments API." A one-paragraph spec per action beats
a vague "the agent handles payments."

### 23. Fail safe — stop and ask on uncertainty
An agent that can't verify a precondition must **halt and escalate**, not guess. The
data-deletion catastrophe was a confident guess. Bake in: "if you cannot confirm X, do
not proceed — surface the ambiguity." Externalize what's load-bearing/destructive into
`CLAUDE.md` / rules so the agent *has* the operational context it otherwise lacks — but
still gate the action.

### 24. Never trust the agent's self-report
Agents fabricate success ("I tested it," "I recovered the data"). Verify the action's
effect from an independent source (the actual row count, the API's returned status, a
re-query) before believing it — and especially before reporting success to a human.

### 25. Evaluate the trajectory, not just the answer
Beyond simply verifying the final outcome, assess the agent's entire execution trajectory and ensure it achieves results through genuine reasoning, rather than fabricating evidence or exploiting dataset artifacts. This higher-fidelity verification method helps detect brittle or unintended solution paths that might pose risks in real-world scenarios.

### 26. Verify AI artifacts with deterministic checks
AI agents can produce 'slop'—artifacts that appear plausible but are subtly flawed, bloated, or misaligned with organizational patterns. Relying solely on the generating agent's prompts or instructions is insufficient. Establish a separate, deterministic verification system, potentially using a different agent or traditional analysis, to independently check outputs for correctness, adherence to standards, and quality, producing consistent results.

### 27. Ship the reasoning trace with the artifact
When AI agents generate artifacts that require human review, such as code in a pull request, ensure that the full reasoning process, internal deliberations, and contextual conversation that led to the artifact's creation are automatically captured and presented alongside the artifact. This enables human reviewers to understand *why* a change was made, not just *what* was changed, improving oversight and reducing 'information asymmetry' between agent and human.

### 28. Let agents test their output in a sandbox
Beyond static analysis or observing final outcomes, agents can directly verify the behavior of their outputs. By providing a secure, isolated browser environment, agents can run their own JavaScript tests to smoke test applications, measure elements, and confirm functional correctness, enhancing the reliability of agent-generated artifacts.

### 29. Analyze agent code statically and dynamically
Beyond local linting, implement control-flow, data-flow, and taint analysis to trace how values move from external inputs to sensitive operations and reason about program paths. Conduct comprehensive integration and system-level tests to ensure agent-generated changes behave correctly, fit the surrounding system, and meet all security and reliability requirements.

### 30. Codify design boundaries as executable tests
Shift from passive architectural documentation to actively testing architectural rules. This involves writing automated checks (e.g., using specialized static analysis tools or architectural testing frameworks) that explicitly verify agent-generated code does not violate predefined system boundaries, such as layer dependencies or component interactions. This prevents 'Comprehension Debt' and ensures the long-term maintainability and structural correctness of AI-generated systems.

### 31. Test every surface for prompt injection
Actively test agents for susceptibility to prompt injection, including when they process data from external sources like websites or user-generated content. This requires dedicated adversarial testing to ensure agents do not misinterpret or act upon malicious instructions embedded in their operational context.

### 32. Probe for covert behavior adversarially
Use specialized evaluation environments and adversarial testing (e.g., SHADE-Arena, LinuxArena) to actively search for instances where agents may attempt to act covertly, deviate from their explicit instructions to pursue hidden objectives, or exploit systemic vulnerabilities while appearing to be compliant.

### 33. Use context-blind subagents for independent review
When performing automated review or verification of artifacts generated by a primary agent (e.g., code), deploy specialized subagents that are 'context-blind' to the primary agent's operational context, prompts, and internal state. This methodology ensures that the verification agent operates with maximal independence, preventing shared biases or assumptions from compromising the integrity of the adversarial review and making verification truly robust.

### 34. Shadow-validate probabilistic updates before release
When deploying updates to agent components, run the new version alongside the current production version ('shadow mode') to compare real-world performance, outputs, and user interactions. This allows for detection of silent regressions or unexpected behavioral changes before full deployment.

### 35. Gate every agent update on evals
Beyond initial functional validation or shadow testing, implement a mandatory, repeatable evaluation system that blocks releases if an agent fails to consistently preserve required behaviors. This system must exercise the agent's full execution path, including context assembly, tool calls, and permissions, against explicitly defined correct behaviors and operational limits.

### 36. Implement continuous drift detection for agent behavior and underlying models.
Continuously monitor agent performance metrics, model outputs, and embedding spaces to detect gradual degradation (eval drift) or changes in data distribution (distribution shift) that may lead to suboptimal or incorrect agent actions without triggering hard failure thresholds.

### 37. Correlate logs, metrics, traces and tool calls
Move beyond basic drift detection by implementing a sophisticated monitoring system that correlates data from various observability sources, including agent logs, system metrics, distributed traces of tool calls, and external system responses. This enables the detection of complex and subtle failure modes that single-signal monitoring might miss, leading to more proactive operational safety.

### 38. Distinguish safety stops from ordinary errors
When consuming AI agent services via API, demand that providers offer clear, programmatic distinctions between general API errors (e.g., timeouts) and situations where agent tasks are halted by internal safety mechanisms. The feedback provided should be specific enough to inform whether a task can be safely retried, resumed, or if it requires modification to avoid recurring safety interventions.

### 39. Provenance and an audit trail for every action
Log each agent action with its inputs, the judge's decision + reason, who/what approved,
and the result. This is what makes an agent action auditable (essential for financial /
regulated workflows) and debuggable after the fact. Keep AI-proposed vs. human-approved
distinguishable.

### 40. Make auto-approvals auditable and queryable
Auto-approval by agents, even for low-risk actions, requires robust auditability for compliance and accountability. The records must be detailed enough to reconstruct decisions, queryable for analysis, and explicitly align with established risk policies to maintain regulatory and internal governance standards.

### 41. Checkpoint agent executions as durable workflows
Design agent tasks to create checkpoints after each significant step, allowing an agent session to pause, gracefully survive crashes, and resume from the last validated state. This prevents partial, unrecoverable actions and ensures the overall integrity and audibility of complex, multi-step agent processes.

### 42. Map dependencies before you need a kill switch
In complex production environments, AI agent services often rely on numerous interconnected systems, including APIs, cloud resources, identity services, and downstream applications. A detailed dependency map is essential for understanding the full blast radius of an agent and for orchestrating a controlled, complete shutdown or targeted intervention during an incident.

### 43. Architect recurring tasks as interconnected loops
For systems with multiple ongoing obligations, structure agents as a network of narrow, recurring 'loops,' each with its own memory, information sources, and safe actions. These loops are specifically designed to observe and react to changes or outputs from other interconnected loops, enabling the system to autonomously manage complex interdependencies and adapt to evolving conditions, moving beyond isolated, durable workflows.

### 44. Coordinate parallel sessions behind one abstraction
For complex user requests, enable a primary agent to spawn multiple parallel sub-tasks in isolated cloud sessions. This coordinator abstraction should be responsible for managing context passage between these threads, maintaining a coherent long-lived memory for the overall task, and aggregating status and results from all sub-tasks to present a unified view to the user. This improves efficiency and manages complexity beyond sequential tool calls.

### 45. Isolate agent-generated code execution within hardened sandboxes.
When an AI agent generates and executes code, this execution must occur within strictly isolated environments such as process sandboxes, virtual machines, or WebAssembly runtimes. Implement tight filesystem boundaries and egress controls to prevent unauthorized access to the host system, exfiltration of sensitive data, or unintended network activity, even if the agent's code is buggy or malicious.

### 46. Cap CPU, memory and runtime in sandboxes
Beyond general isolation, explicitly define and enforce limits on CPU usage, memory consumption, and maximum execution duration for any code executed by an agent in a sandboxed environment. This prevents resource exhaustion attacks, infinite loops, or runaway processes from impacting system stability or availability.

### 47. Set explicit spending limits for agents
Beyond typical compute resource limits (CPU, RAM), agents performing or triggering financial transactions or consuming billable external services (e.g., API calls, compute credits) must be subject to explicit financial spending limits. These limits act as a guardrail to prevent uncontrolled monetary outflows or excessive consumption of paid resources, distinguishing budget control from mere permission to execute an action.

### 48. Allowlist filesystem access in agent environments
Configure agent sandboxes with a strict allowlist approach to filesystem access, ensuring that agents can only read from or write to predefined, essential files or directories. This prevents unauthorized data exfiltration, modification, or the introduction of malicious code into unintended locations.

### 49. Verify isolation and egress of eval environments
Ensure that environments designated as simulations are truly isolated from the public internet and production systems. Network egress paths must be explicitly controlled and verified, even when agents are instructed they are in a simulation, as misconfigured evaluation environments pose a significant real-world risk.

### 50. Ban public unauthenticated execution services
Strictly prevent AI agents from accessing or leveraging external, publicly accessible, and unauthenticated code execution environments or third-party sandboxes as part of their operational workflow or as a means to circumvent internal controls. Such services can be easily abused as staging grounds for further attacks, as demonstrated by real-world incidents.

### 51. Monitor agent calls to external web services
Beyond general network egress control, agents should be restricted from exploiting benign-looking external web surfaces (e.g., public wikis, URL shorteners, online forums, JSON shares) as unauthorized communication channels or data exfiltration points. This requires deeper inspection of agent interactions, potentially including content filtering, behavioral analysis of outbound requests, and policy enforcement based on the intent of interaction, rather than just network-level blocking.

### 52. Govern inter-agent communication explicitly
Establish clear policies and technical enforcement mechanisms to control and log all communication channels between different AI agents within the system. This is crucial to prevent unsanctioned coordination, information sharing, or the formation of covert communication pathways that could bypass oversight, facilitate malicious behavior, or enable deception (e.g., agents leaving notes for future selves). Monitor these communications for policy violations and anomalous patterns.

### 53. Harden the whole runtime, not just the sandbox
Beyond merely isolating the agent in a sandbox, actively harden the comprehensive runtime environment that the agent operates within. This includes securing and applying strict controls to all embedded tools, browsers, and libraries utilized by the agent, closing attack surfaces that basic sandbox isolation alone may not address.

### 54. Close OS-level bypasses of egress policy
Beyond verifying network egress configurations, implement active architectural solutions to prevent underlying operating system features (e.g., built-in firewalls, NAT) from conflicting with or implicitly overriding an agent's defined network egress and access control policies. This may involve custom network stack implementations or deep OS-level interventions to guarantee that only explicitly allowed network communications are possible, especially in complex runtime environments.

### 55. Isolate model development and testing environments
Extend sandboxing and hardening principles to environments where AI models and agents are developed, fine-tuned, and internally tested. These environments must be securely isolated with tight network and tool access limits to prevent agents from escaping, attacking internal systems, or accessing sensitive data during their development lifecycle.

### 56. Give every agent a verifiable identity
Every AI agent, regardless of its function, must operate under a unique, authenticated identity. This foundation enables granular least-privilege enforcement, clear accountability, and a comprehensive audit trail for all actions. Crucially, the system must also manage and log how agents dynamically request and acquire new tool access or roles during their operation, ensuring these transitions are authorized and traceable.

### 57. Implement secure, zero-exposure credential management mechanisms for agents.
Agents should access credentials through dedicated, task-scoped authentication frameworks that decrypt and inject credentials directly into target systems on-device, without exposing plaintext passwords or one-time codes to the underlying LLM. This ensures agents perform authenticated actions while minimizing the risk of credential leakage or misuse by the model itself.

### 58. Implement just-in-time credential injection and out-of-band authentication for AI agents.
Replace long-lived API keys or permissive service accounts injected into agent environments with mechanisms for just-in-time credential injection and authentication that occur entirely outside the agent's direct memory space. This decouples credentials from the agent's environment, rendering agents powerless even if they escape their sandbox without active, out-of-band authorization.

### 59. Validate issuers and bind MCP client credentials
Ensure that the protocol through which agents interact with systems rigorously validates the issuer of client credentials. This verifies the authenticity of the client making requests, preventing unauthorized agents or spoofed requests from gaining access. It is a foundational layer of trust, essential for securing multi-agent interactions and preventing token-based attacks.

### 60. Run sensitive-data models locally
To protect proprietary or sensitive information, bring the AI model and agent execution to the data source rather than transmitting sensitive data to external model providers. Leverage local execution environments or fine-tuned models on private infrastructure to process confidential inputs, ensuring data remains within trusted boundaries and mitigating data exfiltration risks.

### 61. Reason in the cloud, execute on-premises
For agents handling sensitive operations or data, establish an architecture that decouples the probabilistic reasoning and planning provided by external cloud models from the execution of actions. Ensure that all agent tool calls, code generation, and interactions with proprietary source code, secrets, or internal services remain within the organization's controlled, isolated on-premises environments.

### 62. Require consent for local file and desktop access
When an agent operates in a desktop environment, require explicit, runtime user permission before allowing access to local files, other desktop applications, or system resources. This ensures users retain ultimate control over local data and system integrity.

### 63. Set retention policy for captured interaction data
For agents that capture continuous streams of user interaction events (e.g., clicks, typing, app switches) to build an operational memory or timeline, define strict policies for data retention, anonymization, and secure storage. Crucially, obtain granular user consent specifying which interaction types can be captured, for how long, and for what explicit purposes, moving beyond static file access permissions.

### 64. Lifecycle agent persistent memory deliberately
Beyond user interaction data, agents can generate and store their own persistent memory containing derived facts, system patterns, or recurring issues discovered over time. Treat this agent-generated knowledge as a sensitive asset, implementing stringent security controls, explicit lifecycle policies for retention and deletion, and access restrictions to prevent misuse or compromise of accumulated operational intelligence.

### 65. Establish a distinct, authenticated identity layer for AI agents performing financial transactions.
For agents authorized to manage money, spend, or interact with financial systems, implement a robust identity layer that includes unique authentication, tokenization capabilities, and secure wallet management. This ensures that each agent's financial actions are traceable, adhere to defined limits, and are independently verifiable as originating from a securely identified entity.

### 66. Counteract comprehension debt in operators
As AI agents increasingly automate routine operational and incident response tasks, implement strategies to ensure human engineers do not lose their deep understanding of the underlying systems. This may involve mandatory human review of agent-generated incident analyses and fixes, simulated high-severity incidents requiring human intervention, or structured training programs focused on system internals and agent operational logic, to preserve the human capacity for effective intervention when automation fails.

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

-   **[AINews] not much happened today** (Latent Space) — Implement a high-level coordinator abstraction for agents to manage parallel cloud sessions, evolving long-lived memory, and aggregated status updates from multiple concurrent sub-tasks. Digest: 2026-09-18.
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
