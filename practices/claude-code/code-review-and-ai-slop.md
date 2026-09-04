# Code Review & Preventing AI Slop

How to review AI-generated code so velocity doesn't quietly turn into technical debt —
and how to catch the failure modes that are *specific* to code an agent wrote.

This is a hub doc. Adjacent mechanics:
- [Token Efficiency](token-efficiency.md) — spec prompts (vague requests are where slop starts)
- [Context & Memory Management](context-memory-management.md) — assembling the context an agent needs to act correctly
- [Prompt Engineering](../ai/prompt-engineering.md) — structured output, code-review prompts
- General review prompt: [`reviews/code-review.md`](../../reviews/code-review.md). This doc is the AI-slop-specific layer on top.

For a ready-to-run audit, see [`reviews/ai-slop-review.md`](../../reviews/ai-slop-review.md).

> **Note on structure (consolidated 2026-08-01).** This doc previously carried 81 flat
> numbered practices, most of them one-sentence headings with a paragraph restating the
> heading — slop, in a doc about preventing slop. They are folded below into 22 practices
> across 9 themes. Nothing was dropped on the merits; overlapping entries were merged and
> the restatement paragraphs cut. Cross-references now use **names, not numbers** — the old
> numeric refs had rotted as entries were inserted (a "see #17" pointing at an unrelated
> practice). Sub-practices are bullets under the practice they belong to.

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

### Theme A — Before the agent writes: spec and context

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

- **Validate the requirements themselves before generating.** SMT solvers and similar logic engines convert natural-language requirements into formal logic and prove soundness, surfacing contradictions for human resolution. AWS found bugs in 60% of software requirements this way.
- **Brief like a senior partner, not a junior.** Goal, context, constraints, quality bar — then room to reason. Micromanaged step-by-step prompts underperform on capable models.
- **Be hyper-literal where it matters.** Precision beats implication; ambiguity is where fabrication enters.
- **Plan in richer formats.** Interactive HTML artifacts, mockups, and living design systems catch misalignment before code exists. A large share of an agent's output should be planning artifacts, not production code.
- **Use divergent planning for hard problems.** Tree-of-thought with cognitive-frame branching explores and prunes alternatives instead of committing to the first path.

### 2. For workflows requiring consistency and predictability, use AI to generate the workflow manifest or plan, but implement the actual execution steps using ordinary, deterministic code.
Leverage AI for its strengths in planning and natural language interpretation to define the steps of a process. Then, hand off the execution to traditional, predictable code to ensure reliable and consistent outcomes, mitigating AI's inherent unpredictability in critical operations.

### 3. Give the agent a permanent context foundation
A `CLAUDE.md`-style business snapshot — operations, conventions, historical decisions,
what's load-bearing — makes generated code domain-correct without re-explaining every
session. Most "the agent didn't know X" failures are context failures, not reasoning failures.

- **Clean the context before the task.** Have an agent build a source inventory, flag duplicates and conflicts, and list missing context *first*. Messy input reliably produces bad synthesis.
- **At scale, structure it.** A semantic knowledge base / "Context Lake" (service ownership, architectural decisions, trade-off discussions) beats stuffing the window.
- **Retrieval quality is the bottleneck, not reasoning.** Rank trade-off discussions and design rationale above implementation detail; agents fabricate confidently when fed partial or poorly ranked context.
- **Fix the data at the source.** Redundant, obsolete and trivial (ROT) enterprise data poisons everything downstream — garbage in, confident garbage out.

### 4. Create and continuously optimize dedicated, agent-facing documentation files (e.g., AGENTS.md) that explicitly define tech stacks, build/test commands, off-limits directories, and team conventions.
Unlike human-centric documentation, agent-facing configuration files serve as a direct, structured context foundation for AI agents, detailing operational parameters, architectural constraints, and forbidden actions. Regularly refine and optimize these documents to improve agent task success, ensure adherence to engineering standards, and reduce inference costs, rather than relying on implicit understanding or human interpretation.

### 5. Treat agent guidance files (e.g., prompts, guardrails) as versioned software, subject to rigorous development, testing, and continuous evaluation.
Formalize the creation and maintenance of agent-facing documentation and instruction sets by treating them as critical software artifacts. Implement version control, automated testing, and evaluation processes to assess the effectiveness of these guidance files in preventing specific failure modes and ensuring on-brand, high-quality output. Continuously optimize them based on agent performance metrics.

### 6. Integrate AI agents as 'teaching agents' earlier in the development workflow to preserve knowledge sharing and address cognitive debt before formal code review.
With the overwhelming volume of AI-generated code, traditional code review is no longer effective for knowledge transfer. Shift left by employing AI agents to act as interactive teaching tools during code creation, explaining anti-patterns, architectural decisions, and team conventions. This proactively shares knowledge and helps developers understand the 'why' behind design choices, mitigating the accumulation of cognitive debt.

### 7. Make the agent defend its reasoning
In review, prompt the agent to explain *why* it chose this design, what it ruled out,
and what it's unsure about. This directly attacks "wrote code but didn't think"
(digest 2026-05-18) and forces the latent reasoning into the open where a human can
challenge it. If it can't defend a choice, that's a finding.

- **Test comprehension, not recall.** Verify the agent can synthesize and apply what it retrieved, not just quote it back.
- **Prefer models that flag their own uncertainty.** It lets reviewers spend attention where the model is least reliable.
- **The human still has to understand the code.** Reviewers own the architecture and its integration, not just the prompt that produced it.

### 8. Require facts, not inferences, in agent-written reports
When an agent writes an issue, a bug report, or a problem description, restrict it to
observables: command run, expected outcome, actual outcome, exact error and logs.
Inferred root causes and suggested fixes read as authoritative and send humans chasing
fabrications.

- **Keep humans on change descriptions.** PR titles, commit messages and issue summaries need strategic framing an agent can't supply; agent-written ones restate the diff verbosely and omit the *why*.
- **Score the trajectory, not just the outcome.** Pass/fail hides memorization, hard-coded metrics and fabricated intermediate steps. Evaluate reasoning steps and tool use, or you reward shortcuts.
- **Treat AI extraction as probabilistic.** In data pipelines, force explicit uncertainty flags or exceptions rather than letting a silent hallucination land in a store downstream.
- **Run a de-slop pass.** A dedicated post-generation step to strip generative filler, boilerplate and stylistic tells from code comments, docs and messages.

### 9. Integrate deliberate friction into AI workflows to preserve human critical thinking and decision-making skills.
Introduce intentional resistance points in AI-assisted tasks, such as requiring manual verification steps or specific human overrides, to prevent over-reliance on AI-generated outputs and safeguard against cognitive atrophy. This 'friction-maxxing' approach ensures humans remain active decision-makers, especially for high-stakes work.

### Theme C — Validation in a real environment

### 10. Validate in a real environment — "looks done" is not done
The validation loop is central to agentic dev: code should be run, tested, and where
relevant deployed to an ephemeral environment before it's trusted (digest 2026-04-26;
"81% PR acceptance" came from environment-based validation, not better prompts).
Don't accept an agent's claim that it tested something — require evidence (CI green +
the actual diff read). Agents will confidently assert success they didn't achieve.

- **Build checks agents can run in seconds.** Traditional CI is too slow to be a feedback loop. Compact end-to-end validation units an agent can author and run in-session are what actually close the loop.
- **Give agents stateful execution.** A live kernel (cell-by-cell execution) lets an agent observe intermediate effects and adapt, instead of guessing across static tool calls.
- **Test adversarially.** Hostile simulations and deliberately non-ideal conditions surface the edge cases ordinary validation misses.

### 11. Re-validate when anything underneath changes
A model upgrade is a behavior change even when benchmarks improve. Re-run the critical
paths; the "AI Upgrade Trap" is regression introduced by a version bump nobody treated
as a deploy.

- **Design tests for non-determinism.** Identical inputs produce variable outputs, so single-instance reproduction fails as a debugging strategy — target patterns and systemic failures.
- **Keep a language-independent conformance suite.** It's what makes large AI-driven migrations or refactors verifiable when the implementation language itself changes.
- **Benchmark against your own work.** Public benchmarks miss enterprise-shaped, large-context tasks; build task-representative evals with transparent data and traces.

### 12. When using AI for code translation or large-scale refactoring, implement rigorous verification processes to prove behavioral equivalence with the original code, beyond just successful compilation and basic testing.
AI-generated code, especially in translation or refactoring tasks, can compile and pass initial tests while still behaving differently from the original. Employ advanced techniques like fuzzing, formal program analysis, and symbolic repair to systematically identify and rectify subtle behavioral mismatches, ensuring the translated code faithfully replicates the intended functionality.

### 13. Employ visual or perceptual validation methods using tools like browser automation and screenshot comparisons to verify the qualitative correctness of agent-generated output.
For agents generating visual interfaces, 3D assets, or other perceptual outputs, augment traditional tests with tools that capture screenshots from predefined viewpoints. Compare these visual artifacts against reference images or expected qualitative standards to detect subtle flaws like incorrect proportions or misalignments that pass conventional functional tests but appear 'wrong' to a human.

### Theme D — Automated review as a gate

### 14. Automated review as a gate, not a replacement
Layered/multi-agent review (e.g. Claude Code Review) examines diffs within the full
codebase, ranks findings by severity, and catches subtle bugs at a low false-positive
rate (digest 2026-03-27). Use it as a *first-pass gate* — it raises signal — but keep
a human accountable for merge. Two cheap, high-leverage gates:
- An independent automated pass reviews the diff — a reviewer agent that didn't
  author the change (e.g. a scheduled diff-scoped review workflow).
- The author-agent must address each finding or explain why it's a false positive.

### 15. Build the review pipeline out of independent verifiers
The recurring pattern across every source: the thing that generates must not be the
thing that accepts.

- **Verifier subagents as an acceptance function.** Independent of the primary model, enforcing factual grounding and citation fidelity, catching the cases where the generating agent cheated.
- **An LLM judge for pre-screening.** Score and prioritize artifacts so expensive review lands where it pays.
- **Multi-engine static analysis.** Deterministic rules plus AI engines plus a false-positive classification layer — without that third layer, noise trains developers to ignore findings.
- **A gate at the merge queue.** Autonomous release-readiness review against production requirements, cross-repo dependencies and plain-English standards, emitting explicit BLOCK / caution / safe decisions.
- **LLM-specific release gates.** Baseline evals, drift detection, shadow validation, cost and latency guardrails — traditional CI/CD doesn't catch probabilistic degradation.
- **Keep a slop registry.** Classify and track recurring anti-patterns (over-engineering, misaligned architecture, non-existent API calls) so detection compounds instead of restarting each review.

### 16. When implementing AI-driven self-correction or feedback loops, rigorously evaluate and ensure the reliability of the AI component acting as the 'verifier' or critic.
Many AI self-improving loops fail because the AI providing feedback for critique, scoring, or iterative refinement is not reliable enough to guide the process effectively. Treat the AI verifier as a critical system component and subject it to stringent validation, ensuring its feedback mechanisms are consistently accurate and lead to genuine improvements, rather than just perpetuating a self-correction spiral.

### 17. Extend existing governance to agent-run pipeline steps
Agents can execute whole CI/CD stages, not just author code. When they do, the
pipeline's audit trail and human oversight have to cover agent actions too, or the
governance you already built silently stops applying. Frameworks like AC/DC
(Guide → Generate → Verify → Solve) make verification continuous rather than a
late checkpoint.

### Theme E — Keeping changes reviewable

### 18. Keep diffs small and scoped
Big-bang AI diffs are unreviewable, so they get rubber-stamped — that's how slop
merges. Constrain each change to one concern, fitting existing conventions. Small
diffs make the review checklist and the reasoning defense (*Make the agent defend its
reasoning*, above) actually tractable.

### 19. Leverage integrated, multiplayer supervision environments that provide real-time visibility into an AI agent's plans, diffs, and execution for effective human oversight and intervention.
Beyond passive audit logs, utilize tools that offer a dedicated, collaborative space where human supervisors can actively monitor an agent's real-time progress, review generated code and outputs (including diffs and live previews), and intervene to request changes or halt execution. This facilitates continuous human-in-the-loop oversight and enhances knowledge sharing.

### 20. Stop the self-correction spiral
When a model starts re-fixing its own output in a loop (digest 2026-04-26), it rarely
recovers in-context and it burns tokens while drifting. Cut it: `Esc Esc` / `/rewind`
to before the spiral, re-spec, and retry — don't keep arguing with it. (See
[token-efficiency.md](token-efficiency.md) session moves.)

- **Put stop conditions in the loop design.** Explicit acceptance criteria, success metrics and a human sign-off point. Defining "done" for an agent loop matters as much as for a human task, and it's what prevents open-ended burn.

### 21. Consider regenerating rather than maintaining
Where the spec is the real artifact, update the spec and re-generate instead of
hand-patching generated code. It moves the review burden to the specification and
stops manual edits accreting into debt. Applies to genuinely spec-driven components,
not to everything.

### 22. Prioritize maintaining conceptual integrity and manage the cognitive load on human engineers when rapidly generating code with AI.
Rapid code generation by AI agents can lead to software that lacks conceptual integrity, accumulating 'weird bumps in funny different directions.' Teams must actively work to maintain a coherent system design, recognizing that while agents increase code output velocity, human cognitive capacity remains the bottleneck for understanding and integrating this volume of code.

### Theme F — Agent architecture and harness

### 23. Treat the harness as the engineering problem
Output quality is a property of the harness as much as the model: integrated
evaluation loops feeding runtime results back to the agent are what drive
improvement.

- **Structure agents as self-contained directories.** Model config, system prompts, tools and skills as explicit version-controlled files; run conversations as durable workflows that checkpoint each step so sessions survive crashes.
- **Design explicit loop types.** Heartbeat, cron, hook and goal loops, with work trees for decomposition, subagents for specialization, and persistent state to prevent re-dos.
- **Add a meta-harness when vendors multiply.** An orchestration layer standardizing session history, security controls and spend across heterogeneous agent platforms.
- **Route by cost-capability.** Default to the cheapest capable model; reserve frontier models for work where the reasoning demonstrably prevents expensive slop.

### 24. Implement an agent architecture that explicitly separates probabilistic reasoning from deterministic policy enforcement and execution.
Design agent harnesses to have a clear separation where the LLM's probabilistic reasoning proposes actions, but deterministic software in the harness (a 'loop controller') enforces policy, validates tools, and executes commands within a sandbox. This architectural pattern strengthens governance and security by ensuring inspectable code retains authority over execution.

### 25. Apply 'Graph Engineering' principles to design agent objective functions and feedback loops, preventing local optimizations from leading to systemic failures.
Counteract the risk of 'locally-correct-but-organizationally-catastrophic' outcomes by designing agents with a holistic understanding of interdependent business metrics and long-term consequences. Model the agent's objectives as a graph of interconnected dependencies, ensuring that optimizations in one area do not inadvertently degrade performance or create perverse incentives in others, thereby aligning agent behavior with complex organizational goals.

### 26. Prune the toolkit
Less is more. Audit an agent's tools regularly and delete the redundant ones — Vercel
deleted 80% of its agent's tools and the agent got better. Every extra tool is
cognitive load and a failure mode.

- **Design tool schemas defensively.** Models carry vendor-specific tool-use biases and will emit malformed calls and invented arguments; validate and recover rather than assuming well-formed input.

### 27. Configure agent 'reasoning effort' or similar internal deliberation parameters to optimize for task requirements, preventing unnecessary overthinking and associated token waste.
AI models often default to high 'reasoning effort,' which can lead to excessive processing, increased latency, and higher costs for routine tasks. Explicitly adjust these parameters within the agent's configuration to match the complexity of the task, ensuring the agent dedicates appropriate computational resources without overthinking or generating unnecessary intermediate steps or verbose output.

### 28. Make skills portable and inspectable
Encode agent procedures as open, movable artifacts (`SKILL.md` files, runbooks,
config) rather than leaving them embedded in a vendor tool or an ephemeral chat
history. They're career and organizational capital; they should be testable and
migratable.

- **Agents can also be built to persist and act proactively** — accumulating institutional knowledge, working asynchronously across channels, and triggering on observed thresholds rather than waiting to be prompted.

### Theme G — Blast radius, permissions, and supply chain

### 29. Human-in-the-loop for irreversible / high-blast-radius actions
The data-loss catastrophe happened because an agent took a destructive action without
a gate (digest 2026-03-27). Never let an agent run migrations, deletes, prod writes,
or money movement unsupervised. Externalize operational knowledge (what's destructive,
what's load-bearing) into `CLAUDE.md` / `knowledge/` so the agent has the context it
otherwise lacks — and still gate the action.

- **Design against approval fatigue.** If humans are prompted for everything, they rubber-stamp everything and the gate is decorative. Route only high-impact and genuinely ambiguous decisions to a human.

### 30. Treat every external input as hostile
An agent cannot distinguish its operator's instructions from instructions embedded in
a GitHub issue, a web page, or a document it reads. Indirect prompt injection is the
default threat model, not an edge case.

- **Scrutinize output channels for exfiltration.** Pre-authenticated links, rendered content and message sends are all data-egress paths (Microsoft Copilot Cowork exfiltrated files this way).
- **Broker credentials; never let them sit in context.** Isolate auth flows from the agent's context window and harness behind a dedicated gateway issuing temporary least-privilege access.

### 31. Give agents their own identity and least-privilege permissions
Agents inheriting a human's or a service account's broad permissions create an
"identity vacuum" — a large attack surface with no attribution.

- **Dedicated IAM per agent**, each a distinct principal with granular permissions.
- **Enterprise-managed authorization** through the existing IdP, so tool connections carry central policy and one audit trail instead of ad-hoc personal OAuth.
- **Least-privilege secrets in CI/CD**, scoped to the specific job that needs them, to bound the blast radius of a compromised agent.
- **Encode permissions in the harness itself**, so authorized actions and reachable resources are explicit and auditable.
- **Sandbox the runtime.** Managed, isolated execution environments contain tool calls and code execution.
    - **Mandate strict network sandboxing and isolation for all AI agent testing and evaluation environments, especially for cybersecurity capabilities, to prevent accidental real-world attacks.** Ensure that any environment where AI agents is tested, particularly for capabilities like cyber attack or vulnerability exploitation, is completely isolated from production and real-world networks.
- **Govern self-modifying agents.** Agents that create tools or touch the filesystem at runtime outrun static policy; log and review emergent capability.

### 32. Secure the toolchain and everything the agent installs
The attack surface moved upstream: IDE extensions, agent platforms and developer
workstations are now weaponized supply-chain targets.

- **Scan and block pre-installation.** Agents autonomously pull dependencies; inspect proposed installs *before* they enter the environment.
- **SBOMs with no minimum depth**, covering transitive dependencies and config files, cross-referenced against vulnerability data.
- **Secure skill registries** — hardened public skills, private internal ones, both continuously scanned for over-permissioned access, obfuscated execution and credential harvesting.
- **Offensive testing, continuously.** AI-powered penetration testing keeps pace with AI-generated code in a way periodic passive scanning does not.
- **Evaluate multi-turn.** Single-turn safety results are a poor predictor; real adversaries decompose and reframe across turns.
- **Redact at machine speed.** Sensitive data reaches sandboxes, pipelines, training sets and agent memory without anyone instructing it to; use synthetic data in non-production.

### 33. Ensure all code and data processed within an AI agent's execution environment, including decrypted content, is subject to rigorous security filtering and inspection.
Adversaries can bypass input/output filters by providing encrypted malicious payloads that the AI agent decrypts and executes within its internal code environment. Implement robust security measures to inspect all intermediate states, including any plaintext generated from encrypted inputs, to prevent the agent from willingly acting on self-generated malicious instructions.

### 34. Cryptographically sign all AI-generated artifacts, including container images, model weights, and inference runtimes, to establish proactive provenance and verify integrity throughout the software supply chain.
The proliferation of AI artifacts (model weights, training datasets, inference runtimes) in container images creates new supply chain vulnerabilities. Implement cryptographic signing to ensure that the origin and integrity of these artifacts can be verified. This proactive measure provides verifiable provenance, addressing the question of 'who built this, and has it been modified?' which static vulnerability scanning alone cannot answer.

### Theme H — Ownership, governance, accountability

### 35. Name an owner for every deployed agent
Unowned agents become haunted houses — stale policies, rotted instructions, nobody
accountable for the output. An "Agent Owner's Card" (purpose, context, health,
owner) makes ownership visible.

- **Run a lifecycle, not a graveyard.** Classify AI-generated artifacts by tier (personal tool → team beta → supported internal → customer-facing) with explicit user-count and risk thresholds, and run demotion audits to deprecate the unmaintained.
- **Govern across vendors.** A layer above individual tools enforcing shared context, reusable processes, quality gates and cost controls regardless of which agent ran.
- **At fleet scale, add checks and balances.** Audition processes for new agents, review boards, and appeals mechanisms — a system that self-corrects rather than trusting any single agent.
- **Set a policy on accepting AI-generated contributions**, internal and external: full code, or only reproducible bug reports and test cases?
- **Regulatory accountability is arriving.** The EU Cyber Resilience Act and similar impose documentation duties regardless of who — or what — wrote the code; open standards work (e.g. Appia Foundation) is where verifiability is being built.

### 36. Define explicit job titles and responsibilities for AI agents to clarify their scope and accountability.
Treat AI agents as virtual team members with persistent identities, complete with defined roles, responsibilities, and associated permissions. This helps delineate their operational scope, aligns expectations for their contributions, and clarifies accountability when issues arise, much like assigning a job title to a human team member.

### 37. Implement policy enforcement for AI agents that governs sequences of tool calls and actions, rather than just evaluating each action in isolation.
Use policy languages that can evaluate the context of previous actions when deciding whether to permit a subsequent agent action. This ensures multi-step agent behaviors adhere to organizational rules, preventing valid but contextually wrong actions within complex workflows.

### 38. Measure the cleanup tax, not just velocity
"2x velocity" is meaningless if rework doubles too. Intercom paired Claude Code with
deep telemetry — invocations, sessions, dashboards (digest 2026-04-26). Track rework:
how often AI-authored code is reverted, hot-fixed, or refactored shortly after merge.
Treat **reducing maintenance cost** as a first-class goal (digest 2026-05-18, ref.),
not a side effect — prefer the simplest solution a human can maintain.

- **Connect changes to production outcomes.** "Percentage of code written by AI" measures nothing; link specific contributions to bugs, performance and maintenance cost to learn where agents are actually additive.
- **Tie activity to business outcomes.** AI business observability counters "tokenmaxxing" — spend that looks like progress.

### 39. Instrument the agent, not just the output
Agent failures are usually silent: drift, looping, inefficient consumption, no crash
and no alert. Traditional log-based debugging doesn't reach them.

- Track internal steps, model calls, tool usage and decision paths.
- Observability-driven engineering — tracing, granular logging, token estimation — is the workable strategy for non-deterministic systems with hidden reasoning steps.

## Anti-Patterns

- **Merge on green CI without reading the diff** — tests can be as sloppy as the code.
- **Trusting "I tested it / I fixed it"** — require evidence; agents fabricate success.
- **Big-bang diffs** — too large to review, so they aren't really reviewed.
- **No spec** — vague request in, slop out; nothing to validate against.
- **Arguing with a spiraling model in-context** — rewind and re-spec instead.
- **Velocity-only metrics** — ignores the rework/maintenance tax that lands later.
- **Unsupervised destructive actions** — migrations/deletes/prod writes with no human gate.
- **Parallel-pattern invention** — agent reimplements something the repo already has.
- **The generator grading itself** — acceptance has to come from something that didn't produce the artifact.
- **Approval prompts for everything** — trains the human to rubber-stamp, and the gate stops working.
- **A doc that only ever grows** — appending every new finding as its own entry produces exactly the slop this doc warns about. Consolidate on a cadence.

## Self-Assessment

Use [`reviews/ai-slop-review.md`](../../reviews/ai-slop-review.md) to have a repo grade
its AI-code-review process and recent AI-authored changes against these practices, and
emit a tracked checklist of fixes. Paste it into a Claude Code session in the target
repo, or wire it into the shared review workflow.

## Sources

Saved articles synthesized here (full summaries in `data/digest_knowledge/`):

- **AI Agents built a 3D city for $33 in two hours —and exposed a major flaw** (The New Stack) — employ visual or perceptual validation methods. Digest: 2026-09-03.
- **Forget Loop Engineering. It’s all about Graph Engineering Now** (Ruben Dominguez (The AI Corner)) — apply 'Graph Engineering' principles to design agent objective functions. Digest: 2026-09-02.
- **Vercel built a feedback loop that treats agent instructions like software** (The New Stack) — treat agent guidance files as versioned software. Digest: 2026-09-02.
- **Perplexity just separated reasoning from authority. Here’s why it matters for enterprises.** (The New Stack) — implement agent architecture separating probabilistic reasoning from deterministic policy enforcement. Digest: 2026-08-26.
- **Codex, Grok and Claude all agree, and you still don't know if they're right. The guide I use to decide.** (Nate Jones) — integrate deliberate friction into AI workflows. Digest: 2026-08-28.
- **Your AI agent’s next tool call may be valid but wrong. AWS’s Dogwood promises to fix that.** (The New Stack) — policy enforcement for sequences of agent actions. Digest: 2026-08-07.
- **Why Todoist says less AI can deliver more** (The New Stack) — leverage AI for planning, deterministic code for execution. Digest: 2026-08-06.
- **Investigating three real-world incidents in our cybersecurity evaluations** (Simon Willison [ai_engineering]) — strict network sandboxing for AI agent cybersecurity testing. Digest: 2026-07-31.
- **Agents keep changing their answers. Harness just built delivery pipelines that don’t care.** (The New Stack) — Adaptive testing and debugging for non-deterministic AI agent outputs. Digest: 2026-07-22.
- **Why retrieval quality is becoming the defining challenge in AI agent architecture** (The New Stack) — Retrieval quality mechanisms. Digest: 2026-07-10.
- **Anthropic wants you to use AI to decide whether or not you should use AI.** (The New Stack) — Feedback loop for AI-generated code to production outcomes. Digest: 2026-07-10.
- **Why zero vulnerability code packages could still be your biggest software supply chain risk** (The New Stack) — SBOMs with no minimum depth. Digest: 2026-07-10.
- **Rewriting Bun in Rust** (Simon Willison) — Language-independent test suites as conformance criteria. Digest: 2026-07-09.
- **Quoting Kenton Varda** (Simon Willison) — Prohibit AI for change descriptions lacking higher-level context. Digest: 2026-07-09.
- **Enterprise AI benchmarks are broken** (The New Stack) — Enterprise-specific AI agent benchmarks. Digest: 2026-07-09.
- **The “silent hallucination” loop: how our autonomous data pipeline poisoned its own vector store** (The New Stack) — Design data pipelines for probabilistic AI outputs. Digest: 2026-07-09.
- **Stop waiting for AI you can trust. Borrow the 500-year-old trick that made untrustworthy agents useful anyway. (Yes, there's a no-code guide!)** (Nate Jones) — Organizational framework for managing fleets of AI agents. Digest: 2026-07-08.
- **The Pragmatic Engineer AMA** (The Pragmatic Engineer) — Hostile simulations and adversarial testing. Digest: 2026-07-08.
- **What a harness is and how to build one with Claude Agent SDK** (Lenny's Newsletter) — Granular permission encoding in AI agent harnesses. Digest: 2026-07-08.
- **JetBrains’ next move isn’t a better IDE — it’s a governance layer over Claude Code, Codex, and Gemini CLI** (The New Stack) — Centralized governance layer over diverse AI tools and agents. Digest: 2026-07-08.
- **Coinbase runs 1,200 agents and just slashed its AI bill in half** (The New Stack) — Multi-model AI routing strategy for cost efficiency. Digest: 2026-07-08.
- **Better Models: Worse Tools** (Simon Willison) — Design AI agent toolkits robust against model-specific biases. Digest: 2026-07-05.
- **Why traditional CI/CD fails for LLMs (and the release gates we built to fix it)** (The New Stack) — LLM-specific release gates. Digest: 2026-07-02.
- **“The harness is where the hard work is”: Harness bets on agents that enterprises can trust in production** (The New Stack) — integrate autonomous agents into CI/CD. Digest: 2026-06-30.
- **Your engineering org needs an AI slop registry** (The New Stack) — systematic tracking of AI slop anti-patterns. Digest: 2026-06-26.
- **`Code should be regenerated, not maintained`: Codeplain makes the case for spec-driven development** (The New Stack) — regenerative code paradigm. Digest: 2026-06-25.
- **[AINews] It's Meta-Harness Summer** (Latent Space) — meta-harnesses for multi-agent orchestration. Digest: 2026-06-25.
- **[AINews] Claude Tag: Multiplayer, Proactive, Persistent Agents in Slack** (Latent Space) — persistent, proactive, asynchronous agents. Digest: 2026-06-24.
- **The AI Upgrade Trap: Why Switching to a Better Model Breaks Everything You Built** (Ruben Dominguez (The AI Corner)) — re-validation upon model upgrades. Digest: 2026-06-23.
- **How Claude Mythos found a 15-year-old bug in Mozilla Firefox | Brian Grinstead** (Lenny's Newsletter) — multi-component bug-finding pipeline with LLM judge. Digest: 2026-06-22.
- **Agent Loops for PMs: 20+ You Can Run This Week** (Paweł Huryn (The Product Compass)) — explicit stop conditions and acceptance criteria for agent loops. Digest: 2026-06-22.
- **Executive Briefing: Your team is running agents nobody owns. The one-page card and two prompts that fix it.** (Nate Jones) — single-point ownership for AI agents. Digest: 2026-06-21.
- **Quoting Sean Lynch** (Simon Willison) — isolated agent authentication flows. Digest: 2026-06-20.
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
- **Revised rules of engineering leadership.** (Will Larson (Irrational Exuberance) [eng_management]) — Strategically optimize the base-case of engineering processes for full automation... Digest: 2026-06-15.
- **AI Agents of the Week: Papers You Should Know About** (Pascal Biese (LLM Watch) [ai_engineering]) — Implement evaluation methodologies that scrutinize the agent's entire 'trajectory'... Digest: 2026-06-14.
- **AI Agents of the Week: Papers You Should Know About** (Pascal Biese (LLM Watch) [ai_engineering]) — Provide dynamic, interactive execution environments rather than static tool calls... Digest: 2026-06-14.
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
- **☕🤖Tutorial: Build Your Founder Skill Pack (5 Claude Skills You Install Once and Use Every Week)** (The AI Break) — Implement a dedicated 'De-Slop pass' for post-generation refinement. Digest: 2026-07-17.
- **Your Agent Doesn’t Have a Memory Problem** (Pascal Biese (LLM Watch)) — Structured mechanisms to verify an AI agent's comprehension of information. Digest: 2026-07-20.
- **Grok, Claude, and Hermes agents get job titles — and persistent permissions** (The New Stack) — defining explicit job titles and responsibilities for AI agents. Digest: 2026-08-21.
- **Conceptual integrity and counting lines of code** (Simon Willison) — prioritizing conceptual integrity and managing human cognitive load with AI-generated code. Digest: 2026-08-20.
- **Researchers hid an attack inside AES encryption. The AI model cracked it open willingly.** (The New Stack) — rigorous security filtering and inspection of decrypted content in AI agent execution environments. Digest: 2026-08-20.
- **Slack has a new channel type — but only agents can create one** (The New Stack) — leveraging integrated, multiplayer supervision environments for human oversight of AI agents. Digest: 2026-08-20.
- **Why Most Self-Improving AI Loops Fail and How to Build One That Works** (Ruben Dominguez (The AI Corner)) — rigorously evaluating the reliability of AI components acting as verifiers in self-correction loops. Digest: 2026-08-19.
- **Your coding agent got the onboarding your developers never did** (The New Stack) — creating and continuously optimizing dedicated, agent-facing documentation files (e.g., AGENTS.md). Digest: 2026-08-19.
- **AI broke code review. What about knowledge sharing?** (The New Stack) — integrating AI agents as 'teaching agents' earlier in the development workflow. Digest: 2026-08-19.
- **AI-generated Rust compiles perfectly. That’s the scary part.** (The New Stack) — implementing rigorous verification processes for behavioral equivalence in AI code translation/refactoring. Digest: 2026-08-20.
- **Qwen 3.8 27B is excellent, but it defaults to wildly overthinking things** (Simon Willison) — configuring agent 'reasoning effort' to optimize for task requirements. Digest: 2026-08-17.
- **Your container images are unsigned. In the AI era, that’s a ticking time bomb.** (The New Stack) — cryptographically signing all AI-generated artifacts for provenance and integrity. Digest: 2026-08-14.
- Referenced-only (title in recommendations, no full summary saved): **We Taught AI to Write Code But We Forgot to Teach It to Think**, **You Need AI That Reduces Maintenance Costs**, **Beyond prompting: How KubeStellar reached 81% PR acceptance with AI agents**, **Are AI agents actually slowing us down?**, **Your Agent Can Code. It Just Can't See.**

## Where Used

- **best-practices**: Claude-only, diff-scoped review system in [`reviews/`](../../reviews/) (weekly diff reviews + monthly full-scope self-assessments → deduped GitHub issue) puts this doc's *Automated review as a gate, not a replacement* into practice.
- **crumbl-ops**: Claude Code for all development with a single engineer — primary consumer of the checklist, validation loop, and destructive-action gating (payroll, QBO writes).
- **command-center**: Scheduled agents taking outbound actions — *Human-in-the-loop for irreversible / high-blast-radius actions* and the reasoning-defense practices matter most.
- **wealth-mgmt**: "Fortress" software in a regulated context — spec-first + maintenance-cost discipline are load-bearing.
