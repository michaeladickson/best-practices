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

### 2. Require human developers to deeply understand the generated code and the underlying system architecture, not just the prompts.
While AI can generate code rapidly, human developers bear the ultimate responsibility for the robustness and maintainability of the entire system. This practice emphasizes that reviewers must fully comprehend how AI-generated code integrates and impacts the broader architecture, ensuring it aligns with long-term design principles and prevents hidden technical debt.

### 3. Implement a structured lifecycle management framework for all AI-generated software artifacts, including classification and demotion audits.
Address the proliferation of easily generated but often unmanaged AI-assisted prototypes and tools by establishing a clear lifecycle management framework. Classify all AI-generated artifacts into defined tiers (e.g., personal tool, team beta, supported internal product, customer-facing product) with explicit user-count and risk thresholds. Regularly conduct demotion audits to identify and deprecate unmaintained or unused tools, preventing the accumulation of undeclared technical debt and potential security liabilities from a 'prototype graveyard'.

### 4. Formally validate AI-generated or human-authored requirements for contradictions and ambiguities using logic engines before code generation begins.
Before an agent generates code, ensure its underlying requirements are precise and consistent. Use specialized tools (e.g., SMT solvers) that convert natural language requirements into formal logic and prove their soundness, surfacing any contradictions or ambiguities for human resolution. This prevents downstream 'slop' and rework by catching fundamental issues at the earliest stage.

### 5. Brief agents like a senior partner, providing goals, context, constraints, and quality bars, rather than explicit step-by-step instructions.
As AI agents become more capable, treat them like a senior partner instead of a junior employee. Provide a comprehensive brief with the goal, context, constraints, and desired quality bar, allowing the agent room to reason and operate autonomously within those bounds, rather than micromanaging with detailed prompts.

### 6. Strategically optimize the base-case of engineering processes for full automation by AI agents, establishing the necessary harnesses, controls, and comprehensive domain context to allow agents to handle most routine steps autonomously.
Design engineering processes with an 'agent-first' mindset for routine, repetitive tasks. Instead of simply augmenting human workflows, configure agents with sufficient autonomy, robust tooling harnesses, clear boundaries, and deep organizational context to execute the 'base-case' of most processes (e.g., standard code changes, minor refactors) end-to-end without human intervention. Human effort can then focus on exceptions and high-value, non-routine work.

### 7. Craft prompts that are hyper-literal and unambiguous to unlock better AI results and reduce generated 'slop'.
When interacting with AI agents, aim for extreme literalness and precision in your prompts. Avoid ambiguity or implied meanings. This specific approach to prompt engineering helps AI agents interpret instructions more accurately, leading to generated code and outcomes that more closely match human intent and significantly reduce unintended 'slop' or confident fabrications.

### 8. Encourage the use of agentic reasoning patterns like 'tree-of-thought with cognitive-frame branching' for complex planning and brainstorming tasks.
To proactively improve the quality of AI-generated code and reduce 'slop', agents should be designed to employ advanced reasoning techniques. Patterns like 'tree-of-thought with cognitive-frame branching' allow agents to explore multiple divergent ideas, evaluate their promise, and deepen promising paths during the planning phase, leading to more robust and reasoned pre-code generation output.

### 9. Leverage richer visual formats, like HTML artifacts, for agent communication and planning, generating interactive specs and living design systems before producing final code.
Encourage agents to produce HTML-based interactive plans, mockups, or living design systems instead of just raw code or plain text. This facilitates better human understanding, collaboration, and feedback in the planning stage, significantly reducing 'slop' by catching issues earlier and ensuring alignment before code generation. This also suggests that a large portion of AI's output should be in planning artifacts rather than production-ready code.

### 10. Adopt a structured Agent-Centric Development Cycle (AC/DC) framework (Guide, Generate, Verify, Solve) for continuous, integrated verification.
Managing the rapid pace of AI-generated code requires a holistic governance model, not just isolated checks. The AC/DC framework guides the entire agentic development lifecycle, ensuring that verification is not a late-stage checkpoint but a continuous, integrated activity woven throughout guiding, generation, and problem-solving stages, building trust at speed.

### 11. Design AI agents using structured loop patterns (e.g., heartbeat, cron, hook, goal loops) and equip them with essential components like work trees, well-defined skills, modular plugins, subagents, and robust state tracking to manage complex, multi-step workflows effectively and predictably.
Move beyond single-turn prompting to architect agents around explicit loop types, each suited for different tasks (e.g., scheduled reviews, event-driven responses). Ensure these loops integrate 'work trees' for task decomposition, leverage subagents for specialized tasks, and maintain persistent state to prevent re-dos, manage progress, and facilitate debugging of complex, autonomous operations.

### 12. Structure AI agents as self-contained directories, encapsulating model configuration, system prompts, tools, and skills as explicit files, and build on durable workflow SDKs that checkpoint each step for resilience and restartability.
Adopt a 'developer experience' approach to agent construction, treating each agent as a structured software project. Organize all agent definitions (models, prompts, tools, skills) into a single, version-controlled directory, similar to a web app. Crucially, run agent conversations as durable workflows that checkpoint at each step, allowing sessions to pause, survive crashes, and resume seamlessly, minimizing lost work and improving robustness.

### 13. Regularly review and prune AI agent toolkits, removing unnecessary or redundant tools to improve agent focus, reduce system complexity, and enhance reliability by minimizing potential failure modes and unintended interactions.
Just as with human-written code, 'less is more' applies to AI agent design. Periodically audit the set of tools an agent has access to, systematically removing those that are not essential, redundant, or introduce unnecessary cognitive load or potential for error. This focused approach helps agents perform more reliably and reduces 'slop' from over-complexity.

### 14. Provide AI agents with a permanent, comprehensive context foundation detailing business operations, brand voice, and historical decisions to ensure domain-specific, high-quality code generation.
Implement a 'CLAUDE.md'-like file or similar mechanism within projects to serve as a persistent 'Business Snapshot.' This ensures the agent consistently generates code that aligns with the organization's unique context, reducing the need for repeated explanations and improving code relevance and quality across sessions.

### 15. Before commencing complex agentic tasks, particularly code generation, utilize agents to first organize and validate their input context by building a source inventory, identifying duplicate or conflicting information, and flagging missing context.
Providing a messy, unverified context to an AI agent often leads to 'slop' in its output. Leverage agents' improved ability to perform file-level operations (e.g., walking folder trees, comparing metadata) to systematically prepare a clean, authoritative 'project room' of source materials, preventing bad synthesis before code generation begins.

### 16. Develop a centralized 'Context Lake' or semantic knowledge base for AI agents to store and retrieve domain-specific knowledge efficiently.
Beyond basic context provision, scaling AI agents requires an architectural solution to manage vast amounts of domain-specific knowledge effectively. A 'Context Lake' provides structured, semantically rich information (e.g., service ownership, architectural decisions), overcoming limitations of context windows and tool sprawl by ensuring agents have deep, relevant knowledge without overwhelming their working memory.

### 17. Standardize the externalization and portability of AI agent skills and workflows (e.g., prompts, runbooks, configuration files) to ensure they are visible, movable, inspectable, testable, and not vendor-locked.
As AI agents increasingly encapsulate complex procedures and problem-solving logic, treat these 'skills' as career capital. Document and store agent workflows in open, transferable formats (like SKILL.md files or runbooks) rather than leaving them embedded in proprietary tools or ephemeral chat histories, enabling easier sharing, maintenance, and migration across platforms.

### 18. Establish secure registries for AI agent skills, including public hardened skills and private organization-specific skills, and implement continuous scanning for vulnerabilities such as over-permissioned access, obfuscated execution, credential harvesting, or untrusted dependencies.
Treat AI agent skills as critical software supply chain components requiring rigorous security. Leverage public registries of continuously maintained and hardened skills, and develop private registries for internal skills, both subject to automated scanning against specific attack patterns. This proactively insulates development pipelines from compromised skills that could introduce vulnerabilities or exfiltrate data.

### 19. Implement processes to actively manage and cleanse enterprise data, systematically identifying and removing redundant, obsolete, and trivial (ROT) information to prevent it from poisoning AI models and leading to flawed conclusions or 'slop' at the source.
Poor data quality is a primary cause of AI project failure. Establish a continuous data governance and cleansing strategy focused on eliminating Data ROT across all enterprise data sources. This ensures that the foundational information feeding AI models is clean, relevant, and accurate, directly preventing 'garbage in, garbage out' and improving the reliability of AI-generated outputs.

### 20. Make the agent defend its reasoning
In review, prompt the agent to explain *why* it chose this design, what it ruled out,
and what it's unsure about. This directly attacks "wrote code but didn't think"
(digest 2026-05-18) and forces the latent reasoning into the open where a human can
challenge it. If it can't defend a choice, that's a finding.

### 21. Prioritize using AI models that are designed to proactively flag uncertainties or potential flaws in their own generated code and reasoning.
Instead of confidently fabricating or requiring explicit prompts to defend reasoning, advanced AI models can now surface their internal uncertainties. Selecting and leveraging models with this 'honesty' feature allows human reviewers to focus more efficiently on areas the AI itself deems less reliable, thereby reducing 'confident fabrication' risks.

### 22. When agents generate issue reports or problem descriptions, mandate that they stick to observable facts (commands, expected outcome, actual outcome, exact errors/logs) rather than inferring root causes or suggesting solutions.
AI-generated issue reports often present confident but inaccurate conclusions, leading to wasted human effort and misdiagnosis. By restricting agents to factual observations, teams can avoid acting on fabricated root causes or irrelevant implementation suggestions, thus preventing a new form of 'slop' in issue tracking.

### 23. Validate in a real environment — "looks done" is not done
The validation loop is central to agentic dev: code should be run, tested, and where
relevant deployed to an ephemeral environment before it's trusted (digest 2026-04-26;
"81% PR acceptance" came from environment-based validation, not better prompts).
Don't accept an agent's claim that it tested something — require evidence (CI green +
the actual diff read). Agents will confidently assert success they didn't achieve.

### 24. Design small, agent-executable, end-to-end validation checks that run quickly in a real environment to provide immediate feedback to coding agents.
Traditional CI is too slow for agents. Create 'plans' – compact, end-to-end validation units that agents can author, select, and run within their session in seconds. This provides rapid, real-environment feedback crucial for iterative agent development and preventing slop.

### 25. Invest in robust 'harness engineering' and integrated evaluation loops for coding agents, combining model outputs, runtime feedback, and continuous validation to drive self-improvement.
Achieving high-quality AI-generated code requires more than just a strong base model; it demands sophisticated 'harness engineering.' This involves building an integrated system that continuously feeds back runtime results and validation against benchmarks to the agent, enabling it to self-correct and improve its outputs iteratively, thereby preventing the accumulation of 'AI slop'.

### 26. Employ 'trajectory-aware' evaluation metrics for AI agents, moving beyond outcome-only assessments to detect hidden behaviors like fabricated evidence, hard-coded metrics, or shortcut-taking that mask genuine capability gaps and produce superficial 'slop'.
Traditional pass/fail evaluations can be misleading, as agents may achieve correct outcomes through unreliable or 'slop'-producing means (e.g., memorization, fabricating intermediate steps). Implement evaluation methodologies that scrutinize the agent's entire 'trajectory'—its reasoning steps, tool usage, and internal thought process—to ensure that successful outcomes are based on genuine understanding and robust problem-solving, rather than superficial 'shortcuts'.

### 27. Implement stateful, interactive execution environments for AI agents (e.g., a Python kernel for cell-by-cell code execution), enabling agents to dynamically write and execute code, adapt to intermediate observations, and refine their actions for improved task completion and reasoning quality.
Enhance agent capabilities by providing dynamic, interactive execution environments rather than static tool calls. For coding tasks, allow agents to operate within a stateful kernel (like Python REPL), where they can write and execute code in an iterative, cell-by-cell manner. This enables agents to observe the real-time effects of their code, adapt their subsequent actions, and refine their reasoning based on intermediate results, leading to more robust and less 'sloppy' solutions.

### 28. Automated review as a gate, not a replacement
Layered/multi-agent review (e.g., Claude Code Review) examines diffs within the full
codebase, ranks findings by severity, and catches subtle bugs at a low false-positive
rate (digest 2026-03-27). Use it as a *first-pass gate* — it raises signal — but keep
a human accountable for merge. Two cheap, high-leverage gates:
- A second model/agent reviews the diff (dual-model, like this repo's review system).
- The author-agent must address each finding or explain why it's a false positive.

### 29. Implement a multi-engine static analysis approach, combining deterministic rules with AI-powered engines and a dedicated false-positive classification layer to improve accuracy and reduce developer fatigue from noise.
To overcome the 'noise problem' of traditional static analysis and prevent high false-positive rates from leading to ignored findings, integrate multiple types of scanning engines (e.g., rule-based, LLM-trained) with a Findings Analysis Engine. This third layer intelligently classifies findings as true or false positives before they reach development teams, making automated security review more effective and trustworthy.

### 30. Integrate an AI agent into the merge queue to perform autonomous release readiness reviews and testing, evaluating code changes against production requirements, cross-repository dependencies, access controls, and plain-English internal standards, providing explicit gating decisions (BLOCK, Proceed with Caution, Safe to Release).
Shift the bottleneck from code writing to safe deployment by deploying an AI agent specifically at the merge queue. This agent should conduct comprehensive pre-merge reviews, checking for compliance with architecture frameworks (e.g., AWS Well-Architected), cross-service dependency risks, and internal quality standards defined in plain language. It must issue clear, actionable gating decisions to prevent 'slop' from reaching production.

### 31. Deploy dedicated verifier agents to act as an independent acceptance function for AI-generated artifacts.
Implement specialized verifier agents whose sole purpose is to serve as an 'acceptance function' for AI-generated code or other artifacts. These agents should enforce specific quality criteria such as factual grounding, citation fidelity, and cross-modal consistency, operating independently of the primary reasoning model to ensure objective validation before acceptance.

### 32. Integrate AI-powered offensive security tools, such as continuous penetration testing, specifically designed for AI-generated code.
Traditional security testing struggles to keep pace with the velocity and unique vulnerabilities of AI-generated code. AI-powered penetration testing offers a continuous, offensive approach to actively find and exploit weaknesses, rather than just passively scanning, providing a proactive defense against agentic attackers.

### 33. Mandate multi-turn evaluation of AI models and agents to assess resilience against iterative attacks.
Recognize that single-turn performance is often a poor predictor of an AI model's resilience to attacks. Implement rigorous multi-turn security evaluations that simulate iterative attacker behavior, as real adversaries decompose tasks and reframe refusals across dialogue turns, revealing vulnerabilities missed by single-turn assessments in AI-generated code and agentic operations.

### 34. Secure the entire AI-driven development toolchain, including IDE extensions, agent platforms, and developer workstations, as part of the critical software supply chain.
The software attack surface has fundamentally shifted upstream, with malicious actors actively weaponizing IDE extensions, agent servers, and developer tools to inject harmful code or compromise systems. Treat all components of the AI development environment as high-value targets, implementing robust security controls to prevent supply chain attacks before code is generated.

### 35. Implement automated pre-installation scanning and blocking for all packages, plugins, and extensions introduced or proposed by AI agents.
AI agents can autonomously pull and install dependencies, leading to the introduction of unowned, unvetted, or malicious packages. To counter this, security teams must deploy real-time scanning and blocking mechanisms that inspect all proposed installations from agents *before* they are integrated into the development environment, closing a critical supply chain gap.

### 36. Implement robust, machine-speed data governance and sensitive data redaction, including the use of synthetic data, across the entire AI-driven SDLC.
AI agents interact with sensitive data in development sandboxes, CI/CD pipelines, training datasets, and agent memory, often without explicit instruction or human oversight, at speeds that traditional governance struggles to match. Proactively redact or replace sensitive information with synthetic data in all non-production environments to prevent data leaks and ensure compliance.

### 37. Implement strict credential brokering and isolation for AI agents, treating all external data sources (e.g., GitHub issues, web pages) as potentially malicious.
AI agents cannot distinguish between instructions from their operator and those embedded in external data they process, making them vulnerable to indirect prompt injection and credential leaks. Isolate agents, broker credentials carefully, and assume all external inputs can be weaponized to prevent sensitive data exposure.

### 38. Implement a dedicated Identity and Access Management (IAM) framework for AI agents, treating each agent as an individual entity with granular, least-privilege permissions.
AI agents are proliferating rapidly, often inheriting broad permissions from human users or service accounts, creating an 'Identity Vacuum' and a significant attack surface. A dedicated IAM for agents ensures each is treated as a distinct identity with granular, least-privilege access, mitigating risks from action-based threats and indirect prompt injection at scale.

### 39. Implement enterprise-managed authorization for AI agent tool connections, leveraging existing identity providers to enforce centralized policy, ensure comprehensive auditability, and prevent ad-hoc or personal account connections.
For enterprise-scale agent deployments, move beyond individual OAuth prompts for tool access. Integrate AI agent tool connections with the organization's existing identity provider (IdP) to centralize access control, enable consistent policy enforcement, generate a single audit trail, and eliminate the risk of employees connecting personal accounts to work tools.

### 40. Implement secrets management solutions that default to least privilege access for AI agents within CI/CD pipelines.
The 'AI paradox' means increased AI code leads to more workflow credentials to secure. Counter this by configuring secrets management in CI/CD pipelines to default to least privilege for AI agents. This automatically restricts agent access to specific credentials for only the jobs or contexts where they are strictly necessary, significantly reducing the blast radius of compromised agents.

### 41. Utilize managed agent runtime platforms that provide isolated, sandboxed environments for agent execution, reasoning, tool calling, and code running.
To enhance security and prevent unintended side effects from highly autonomous agents, deploy them within managed runtime platforms that offer robust isolation. These platforms, often using remote Linux sandboxes, contain agent actions, tool calls, and code execution, effectively limiting their blast radius and protecting underlying infrastructure from agent-induced vulnerabilities.

### 42. Scrutinize all agent output channels for potential data exfiltration vectors, ensuring agents cannot create or transmit pre-authenticated links or render malicious content.
AI agents' ability to generate and send content through various output channels (e.g., email, messaging, rendered interfaces) presents a critical exfiltration risk. This practice requires meticulous review of how agent outputs could be leveraged to leak sensitive data, such as through embedded pre-authenticated download links or malicious content designed to bypass security controls in client applications.

### 43. Implement governance mechanisms for AI agents that dynamically create tools or access device file systems at runtime.
As 'claw-style' agents gain the ability to self-modify by creating tools or directly interacting with device file systems, static security policies are insufficient. New governance frameworks are needed to log, review, and control these emergent capabilities, ensuring that dynamic actions align with pre-defined security policies and organizational intent.

### 44. Human-in-the-loop for irreversible / high-blast-radius actions
The data-loss catastrophe happened because an agent took a destructive action without
a gate (digest 2026-03-27). Never let an agent run migrations, deletes, prod writes,
or money movement unsupervised. Externalize operational knowledge (what's destructive,
what's load-bearing) into `CLAUDE.md` / `knowledge/` so the agent has the context it
otherwise lacks — and still gate the action.

### 45. Design human-in-the-loop interaction patterns for AI agents to prevent approval fatigue, ensuring that humans are only prompted for high-impact, non-routine decisions to maintain effective oversight without rubber-stamping.
Recognize that continuous, trivial human approvals for agent actions can lead to 'approval fatigue,' rendering the human-in-the-loop ineffective. Design interfaces and workflows where agents handle the vast majority of routine, low-risk decisions autonomously, surfacing only critical, high-impact, or truly ambiguous choices to human reviewers. This preserves the value of human judgment and prevents unintentional 'slop' from being approved by reflex.

### 46. Establish clear accountability for compliance with external regulations, including specific documentation requirements for AI-generated code.
As AI-generated code proliferates, organizations face increasing legal accountability under regulations like the EU's Cyber Resilience Act. This mandates defining clear roles for compliance and a significant, structured documentation burden for all software, regardless of generation method, to demonstrate due diligence and manage risks.

### 47. Proactively engage with and adopt open, modular specifications and standards (e.g., from Appia Foundation) to provide a consistent and verifiable way to demonstrate that AI systems meet trust and compliance obligations across the entire AI supply chain.
Beyond internal accountability, collaborate with industry efforts to establish and utilize common technical specifications and standards for AI system trust and compliance. This helps ensure that AI-generated code and agent behaviors are verifiable against external regulations, customer expectations, and international standards, fostering a more secure and reliable AI supply chain.

### 48. Define clear policies on whether to accept AI-generated code contributions and what formats are acceptable from external sources or other internal teams.
Organizations must establish explicit guidelines for handling AI-generated code submissions, particularly from external contributors or different internal teams. This includes deciding whether to accept full AI-generated code, or only specific artifacts like reproducible bug reports and test cases, to manage review burden and maintain code quality standards.

### 49. Keep diffs small and scoped
Big-bang AI diffs are unreviewable, so they get rubber-stamped — that's how slop
merges. Constrain each change to one concern, fitting existing conventions. Small
diffs make the checklist (#17) and reasoning review (#11) actually tractable.

### 50. Stop the self-correction spiral
When a model starts re-fixing its own output in a loop (digest 2026-04-26), it rarely
recovers in-context and it burns tokens while drifting. Cut it: `Esc Esc` / `/rewind`
to before the spiral, re-spec, and retry — don't keep arguing with it. (See
[token-efficiency.md](token-efficiency.md) session moves.)

### 51. Implement comprehensive observability for AI agent execution, tracking internal steps, model calls, tool usage, and decision paths to quickly identify inefficiency, looping behavior, and subtle failures.
Unlike traditional software, AI agent failures often manifest as subtle drifts, excessive loops, or inefficient resource consumption without crashing or explicit alerts. Establish granular monitoring of agent processes to understand their reasoning and resource consumption, ensuring operational efficiency and correct outcomes rather than just measuring final output or overall cost.

### 52. Shift debugging strategy from log-based thinking to observability-driven engineering for AI systems, specifically addressing non-deterministic outputs and hidden reasoning steps.
Unlike traditional software, AI systems exhibit non-deterministic behavior, silent failures, and opaque reasoning, rendering traditional log-based debugging ineffective. A robust observability strategy, encompassing tracing, granular logging, and token estimation, is crucial for understanding internal steps, identifying subtle failures, and debugging probabilistic AI systems effectively.

### 53. Measure the cleanup tax, not just velocity
"2x velocity" is meaningless if rework doubles too. Intercom paired Claude Code with
deep telemetry — invocations, sessions, dashboards (digest 2026-04-26). Track rework:
how often AI-authored code is reverted, hot-fixed, or refactored shortly after merge.
Treat **reducing maintenance cost** as a first-class goal (digest 2026-05-18, ref.),
not a side effect — prefer the simplest solution a human can maintain.

### 54. Implement 'AI business observability' to clearly connect AI agent activities and associated costs to measurable business outcomes.
Bridging the gap between engineering efforts and business value requires a new dimension of observability. 'AI business observability' moves beyond technical metrics to directly track how AI agent activities, their resource consumption, and costs contribute to specific business goals and KPIs, ensuring investments deliver tangible value and combatting 'tokenmaxxing' behaviors.

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
- **68% of AI power users do one thing differently — and it is not a prompt trick** (Nate Jones) — treat agents like senior partners. Digest: 2026-05-21.
- **Revised rules of engineering leadership.** (Will Larson (Irrational Exuberance) [eng_management]) — Strategically optimize the base-case of engineering processes for full automation... Digest: 2026-06-15.
- **CI wasn’t built for coding agents. Here’s what comes next.** (The New Stack) — rapid, agent-executable validation checks. Digest: 2026-05-21.
- **Tutorial: Build a CLAUDE.md That Makes Claude Code Work Like It Knows You** (The AI Break) — persistent context foundation for agents. Digest: 2026-05-19.
- **HTML is the new Markdown: How Anthropic engineers are building with Claude Code | Thariq Shihipar** (Lenny's Newsletter) — richer visual formats for planning. Digest: 2026-05-18.
- **AWS found bugs in 60% of software requirements. Its fix isn’t more AI — it’s a 50-year-old logic engine.** (The New Stack) — formally validate requirements using logic engines. Digest: 2026-05-15.
- **Build the room before you write the memo. Grab the 4-prompt project room kit: source inventory, duplicate log, missing-context list, grounded draft.** (Nate Jones) — agent-assisted context validation. Digest: 2026-05-22.
- **Quoting Armin Ronacher** (Simon Willison) — facts over inference in issue reports. Digest: 2026-05-24.
- **JFrog report recaps a tumultuous year in supply chain security** (The New Stack) — securing the AI development toolchain. Digest: 2026-05-22.
- **How MCP and synthetic data are reshaping compliance in the agentic era** (The New Stack) — machine-speed data governance and redaction. Digest: 2026-05-23.
- **When $8 Becomes $240** (AI Engineering) — credential brokering and isolation for agents. Digest: 2026-05-24.
- **Who’s monitoring the agents?** (The New Stack) — comprehensive observability for agent execution. Digest: 2026-05-24.
- **Why Linux creator Linus Torvalds gets angry hearing “99% of code is AI”** (The New Stack) — deep understanding. Digest: 2026-05-29.
- **“The AI did it” won’t save you when EU regulators come knocking** (The New Stack) — external regulations. Digest: 2026-05-29.
- **AI is shipping code faster than security was built to handle** (The New Stack) — offensive security tools. Digest: 2026-05-29.
- **Claude Opus 4.8: "a modest but tangible improvement"** (Simon Willison) — models flag uncertainties. Digest: 2026-05-28.
- **Claw-style AI agents are coming to the enterprise. The governance infrastructure is still catching up.** (The New Stack) — dynamic tool/filesystem access governance. Digest: 2026-05-28.
- **The agentic identity crisis: Why your security isn’t ready for the AI revolution** (The New Stack) — dedicated IAM for agents. Digest: 2026-05-28.
- **Debugging the undebuggable: building observability into probabilistic AI systems** (The New Stack) — observability-driven debugging. Digest: 2026-05-28.
- **sqlite AGENTS.md** (Simon Willison) — policies for AI code contributions. Digest: 2026-05-27.
- **[AINews] New AI Infra decacorns: Fireworks, Baseten (with OpenRouter on the way)** (Latent Space [ai_engineering]) — harness engineering. Digest: 2026-05-27.
- **Researcher “gave Claude Code ‘ADHD’… and it thinks 2x better now.” Outside experts want more proof.** (The New Stack) — tree-of-thought reasoning. Digest: 2026-05-27.
- **“There is no accountability”: AI coding agents are installing packages no one owns** (The New Stack) — pre-installation scanning for packages. Digest: 2026-05-27.
- **With Google’s debut, the most important AI agent feature is now the most boring one** (The New Stack) — sandboxed agent runtimes. Digest: 2026-05-27.
- **Why AI agents need a Context Lake** (The New Stack) — Context Lake. Digest: 2026-05-27.
- **Microsoft Copilot Cowork Exfiltrates Files** (Simon Willison) — agent output channels exfiltration. Digest: 2026-05-26.
- **Taming the agentic influx: a blueprint for AI business observability** (The New Stack) — AI business observability. Digest: 2026-05-26.
- **How the AC/DC framework helps teams govern AI coding agents** (The New Stack) — AC/DC framework. Digest: 2026-05-26.
- **GitLab 19.0 trades its string section for a full DevSecOps orchestra** (The New Stack) — least privilege for agents in CI/CD. Digest: 2026-05-25.
- **Your prototype graveyard is leaking secrets. The Prototype Classifier + Demotion Audit decide what stays** (Nate Jones) — structured lifecycle management. Digest: 2026-05-29.
- **AI Agents of the Week: Papers You Should Know About** (Pascal Biese (LLM Watch)) — dedicated verifier agents. Digest: 2026-06-01.
- **OpenAI, Anthropic, Google, Amazon, and xAI all fail on type of attack, study finds** (The New Stack) — multi-turn evaluation. Digest: 2026-06-02.
- **Building an iPhone app with zero technical skills | Bryce Rattner Keithley** (Lenny's Newsletter) — hyper-literal and unambiguous prompts. Digest: 2026-06-01.
- **Your skills are leaving your hands. Don't let a rent-a-brain keep them.** (Nate Jones [ai_strategy]) — Document and store agent workflows in open, transferable formats (like SKILL.md files or runbooks)... Digest: 2026-06-19.
- **Checkmarx’s new SAST engine isn’t about the LLM. It’s about what happens after.** (The New Stack [devops]) — To overcome the 'noise problem' of traditional static analysis... Digest: 2026-06-19.
- **MCP gets its missing enterprise authorization layer** (The New Stack [devops]) — Integrate AI agent tool connections with the organization's existing identity provider (IdP)... Digest: 2026-06-18.
- **Vercel deleted 80% of its agent's tools and the agent got better + what to delete from yours (guide inside!)** (Nate Jones [ai_strategy]) — Periodically audit the set of tools an agent has access to... Digest: 2026-06-17.
- **How to design AI agent loops: schedules, goals, and subagents in Claude Code and Codex** (Lenny's Newsletter [product]) — Move beyond single-turn prompting to architect agents around explicit loop types... Digest: 2026-06-17.
- **Vercel launches eve, an open-source framework that treats agents as directories** (The New Stack [devops]) — Adopt a 'developer experience' approach to agent construction... Digest: 2026-06-17.
- **Chainguard Agent Skills matures** (The New Stack [devops]) — Treat AI agent skills as critical software supply chain components... Digest: 2026-06-17.
- **AWS puts an AI bouncer at the merge queue** (The New Stack [devops]) — Shift the bottleneck from code writing to safe deployment... Digest: 2026-06-17.
- **“Agents need boring infrastructure around them”: Why we need to take an interest in ‘invisible’ AI** (The New Stack [devops]) — Recognize that continuous, trivial human approvals for agent actions can lead to 'approval fatigue'... Digest: 2026-06-17.
- **Google, Microsoft, and OpenAI join forces to help create AI’s missing trust layer** (The New Stack [devops]) — Collaborate with industry efforts to establish and utilize common technical specifications... Digest: 2026-06-17.
- **Your AI isn’t broken. Your data is.** (The New Stack [devops]) — Establish a continuous data governance and cleansing strategy focused on eliminating Data ROT... Digest: 2026-06-17.
- **AI Agents of the Week: Papers You Should Know About** (Pascal Biese (LLM Watch) [ai_engineering]) — Implement evaluation methodologies that scrutinize the agent's entire 'trajectory'... Digest: 2026-06-14.
- **AI Agents of the Week: Papers You Should Know About** (Pascal Biese (LLM Watch) [ai_engineering]) — Provide dynamic, interactive execution environments rather than static tool calls... Digest: 2026-06-14.
- Referenced-only (title in recommendations, no full summary saved): **We Taught AI to Write Code But We Forgot to Teach It to Think**, **You Need AI That Reduces Maintenance Costs**, **Beyond prompting: How KubeStellar reached 81% PR acceptance with AI agents**, **Are AI agents actually slowing us down?**, **Your Agent Can Code. It Just Can't See.**

## Where Used

- **best-practices**: dual-model review system in [`reviews/`](../../reviews/) (Gemini + Claude → synthesis → deduped GitHub issue) is this doc's #19 in practice.
- **crumbl-ops**: Claude Code for all development with a single engineer — primary consumer of the checklist, validation loop, and destructive-action gating (payroll, QBO writes).
- **command-center**: Scheduled agents taking outbound actions — #32 (human-in-the-loop) and reasoning-defense matter most.
- **wealth-mgmt**: "Fortress" software in a regulated context — spec-first + maintenance-cost discipline are load-bearing.
