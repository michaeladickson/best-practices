# LLM Evaluation & Prompt-Regression Testing

How to know whether an AI feature is *actually working* — and catch it when a prompt
edit or a model upgrade quietly makes it worse. Unit tests check your code; nothing in
the standard test suite checks the *quality of an LLM's output*. That gap is where
silent regressions live.

Related: [Prompt Engineering](prompt-engineering.md) (writing the prompts you're
evaluating), [Gemini Integration](gemini-integration.md) (the client these features
call), and the validation practice in
[Code Review & AI Slop](../claude-code/code-review-and-ai-slop.md).

For a ready-to-run audit, see [`reviews/llm-eval-review.md`](../../reviews/llm-eval-review.md).

## The Core Problem: Quality Drifts Silently

Two forces degrade an AI feature without changing a line of your code:
- **Prompt edits.** A "small" wording tweak that helps one case regresses five others.
- **Model updates.** A new model is not automatically better *for your task*; users
  reported Opus 4.7 felt *less* capable than what it replaced — "shrinkflation" (digest
  2026-04-26), and Anthropic's own postmortem traced quality complaints to harness bugs,
  not the model (digest 2026-04-26). "Newer" ≠ "better here."

Without an eval set, you find out from a customer. With one, you find out in CI. The
fix: treat AI outputs like any other contract — pin the expected behavior in a
**fixture/golden dataset**, run it on every prompt or model change, and gate the change
on the result.

## Best Practices

Practices are deliberately unnumbered — entries get inserted and merged over time, and
numbered cross-references rot. This section was consolidated 2026-08-28 (59 → 27
entries); the per-article trail is unchanged under [Sources](#sources).

### Build a golden/fixture dataset per AI feature
For each feature (invoice extraction, email classification, draft generation, forecast),
curate a set of representative `input → expected` examples — including the gnarly edge
cases that have bitten you. This is the institutional memory of "what good looks like."
Start small (20–50 cases) and grow it.

### Grade with the right metric for the task type
"Looks good" is not a metric. Match the metric to the output:

| Task | Metric |
|---|---|
| Extraction (invoice fields) | per-field exact/normalized accuracy |
| Classification (email routing) | precision / recall / confusion matrix |
| Forecasting (demand) | backtest error — MAPE / RMSE vs. actuals |
| Open-ended generation | rubric score (LLM-as-judge) + spot human review |

### Run the eval on every prompt change AND every model change — in CI
The eval set is a regression gate, not a one-time exercise. Re-run it when a prompt
changes and when you consider a model upgrade; **fail the change if quality drops**
below the baseline. This is "prompt-regression testing" / fixture-based testing for
prompts (digest 2026-05-16). Re-test inherited prompt *patterns* too: few-shot examples
and negative-constraint lists that helped an older model can actively degrade a newer
one, so prompt-engineering habits are themselves a thing the eval must catch.

### Pin model versions; gate upgrades behind the eval
Never let a model float to "latest" silently. Pin the version, and treat a model bump
as a change that must pass the eval set first. This is the concrete defense against
"shrinkflation" and silent harness regressions. When an upgrade *does* improve agentic
or long-horizon work, the gain often comes from post-training/RL rather than a new base
model — evaluate the claim on your tasks instead of assuming a capability jump.

### LLM-as-judge for open-ended outputs — but validate the judge
For generation tasks where exact-match doesn't apply, score against an explicit rubric
using a model judge. Validate the judge against human labels on a sample before trusting
it, and watch for it rewarding fluent-but-wrong answers. Complement it with cheap human
"vibe scoring": a lightweight local scoring page where a human rates a sample of outputs
and exports structured scores keeps subjective quality in the loop without ceremony.

### Verify against ground truth; flag unsupported claims
For extraction and research outputs, check against the source document and flag anything
the source doesn't support (the hallucination guard). Keep raw data and AI synthesis
distinguishable so a reviewer can verify. Apply the same check to *intermediate* outputs
inside pipelines — data one AI component extracts or summarizes before storing or
passing on can silently poison downstream context ("silent hallucination"). In domains
demanding mathematical or logical rigor (code, math, planning), step up from spot-checks
to formal verification of the artifact.

### Track production quality over time (drift detection)
Offline eval is necessary but not sufficient. Sample live outputs and track accuracy
over time; alert on **drift** — a classifier whose precision is sliding, a forecast
whose error is widening, an extractor failing on a new vendor's format. For ML models
this is model-drift detection; for LLM features it's the same idea on output quality.
Before a cutover, **shadow-validate**: run the candidate model or prompt passively
against live traffic — binary CI thresholds miss the gradual eval drift that only shows
up on messy production inputs.

### Graduate production failures into the eval set
When a bad output reaches production, add that case (with its correct answer) to the
fixture set so it can never silently regress again. The eval set should grow from real
misses, not stay frozen. Make it the default debugging motion — a customer bug becomes
an eval case *first*, then the fix is validated against it (an eval-first workflow).

### Track cost, latency, and the human cost alongside quality
A prompt that's 3% more accurate but 2× the tokens may be a bad trade. Record token
count and latency next to the quality score so an "improvement" that blows the budget is
visible (ties into AI spend governance). Split token accounting between internal
*reasoning* and final *output* — in agentic systems the scratchpad is often the dominant
cost driver. And count the humans: a cheaper model that needs more review and correction
per accepted output costs more than its API price suggests, and an agent fleet carries
operational overhead — allocation, specification, intervention, coordination, recovery
("agent fatigue") — that belongs in the same total-cost-of-ownership ledger.

### Probe benchmarks for overfitting — and publish your eval methodology
Models memorize benchmark patterns. Vary known benchmark prompts and probe for direct
recall to test generalization rather than trusting headline scores. Prefer benchmarks
shaped like the real task — most coding-agent benchmarks skip large-scale refactoring
and whole-codebase comprehension, so use ones built for it. And when your eval claims
need to be trusted by others, publish the datasets, harness, judging criteria, results,
and raw traces so outside reviewers can replicate and attack the methodology.

### Implement double-blind evaluation setups using confidential computing to prevent benchmark leakage and ensure unbiased assessment of proprietary models.
Utilize confidential computing environments (e.g., hardware-encrypted enclaves) where model weights and inference code are kept private from evaluators, and test benchmarks and evaluation code are kept private from model providers. This prevents accidental or intentional contamination of benchmarks and ensures unbiased evaluation results.

### Evaluate operational characteristics, not just benchmark scores
Production reliability lives in behaviors benchmarks don't score: source discipline,
operational judgment, provenance tracking, self-correction. Sweep configurable
"effort"/reasoning settings — turning the dial up sometimes makes output *worse*. And
when selecting a model, weigh non-functional criteria — cost, control, vendor lock-in,
open-weight viability — alongside raw capability.

### Evaluate retrieval and context quality separately from generation
When a RAG or agentic feature fails, the retrieval/context-building step is a distinct
suspect from the generator — score whether the right context was assembled at all. If
agents reason over raw, messy enterprise data, evaluate a "context compilation" layer
that structures it into a queryable knowledge base first. Expect embedding-proximity
memory to hallucinate and forget more as it grows — an architectural limit, not a tuning
problem. And test the gap between *retrieving* a fact and *understanding* it: agents can
recall accurately while misapplying meaning or context.

### Evaluate RAG infrastructure at scale — including access control
Naive RAG architectures fail at production scale (timeouts, data loss). Evaluate the
ingestion pipeline, prompt caching, cost, and latency as part of output quality, not as
a separate ops concern. Verify retrieval honors RBAC and multi-tenant isolation: an
agent must only surface data the requesting user is authorized to see.

### Judge agent trajectories and require evidence, not just outputs
Score the sequence of steps, not only the final answer. Trajectory-aware judges catch
reasoning shortcuts, fabricated intermediate results, and exploitation of test
artifacts — right answers for wrong reasons. For agents drawing data-driven
conclusions, make them emit an **evidence packet** — queries run, statistical
justification, completeness assessment, alternative hypotheses considered — and
evaluate the packet as part of the output.

### Evaluate the orchestration layer: routers, decomposition, tool prompts
Multi-agent decomposition and dynamic model routing are their own failure surfaces.
Evaluate the router's decisions and the decomposition quality by their effect on
end-to-end quality, cost, and latency — even when the internal logic is proprietary or
opaque. At the prompt level, most tool-use retry loops trace to missing context (a
schema listed without column names, instructions that invite guessing); fix the tool
documentation before blaming the model.

### Run long-horizon simulations — and verify the eval environment itself
Beyond isolated input→output checks, run dynamic, business-like multi-step simulations;
emergent failures only appear there. Then treat the environment as a system under test:
an unreliable harness teaches agents wrong behavior and voids results, and a simulated
boundary ("this is a simulation," "no internet access") must be *enforced* by the
environment rather than asserted to the agent — especially in security-critical evals.
Serving these environments at agent speed is a platform capability in its own right:
measure provisioning latency, concurrent capacity, and dependency fidelity.

### Develop and validate sophisticated simulations of human behavior and user interactions (digital twins) for pre-deployment testing of AI systems.
Beyond basic simulations, create high-fidelity digital twins of human behavior. This involves extensive data collection from interviews, observations, and transactions, and applies techniques like Randomized Controlled Trials (RCTs) and modeling causal mechanisms to accurately reproduce human decision-making and emergent behaviors in a simulated environment before product or policy deployment.

### Account for non-determinism in evaluation
Outputs vary run to run, and more so with external tools enabled. Quantify the
variation, run each eval case multiple times and score aggregates, reduce
non-determinism where you can (temperature, seeding), and use matching strategies
robust to it where you can't.

### Test safety multi-turn and in-environment
Single-turn safety checks miss most real attacks. Evaluate across multi-turn
interactions, and test prompt injection where it actually arrives — embedded in web
pages the agent browses and code it executes, not just pasted into a prompt. Probe for
covert behavior too: agents pursuing hidden goals while appearing compliant.

### Sandbox agent execution — and evaluate the whole stack
Agents that generate and run code get robust, isolated sandboxes, full stop. Then
evaluate the security of the whole execution stack — hardened runtime, browsers, tools,
libraries — not just container isolation. For agents touching critical systems
(databases, production infra), correctness requirements are unforgiving: stricter
sandboxing, human-in-the-loop validation, or formal methods.

### Evaluate agent identity, credentials, and action-sequence policy
Agents request tools and assume roles dynamically, so verify least privilege, clear
ownership, and complete audit trails explicitly — traditional IAM assumptions don't
hold. Keep credentials out of the agent's memory and environment entirely:
just-in-time, out-of-band authorization means a sandbox escape yields nothing. And test
policy engines on *sequences* of tool calls rather than point-in-time actions —
valid-but-wrong workflows are the emergent risk.

### Design human oversight that scales
Critical agent actions need review points a human can meaningfully exercise. Two levers
keep that real at volume: review the *artifacts and observable outcomes* rather than the
AI's internal code or logic, and put an AI classifier in front of the approval queue so
humans see genuinely dangerous actions instead of drowning in routine ones — approval
fatigue is how safety gates fail.

### Gate AI-generated code with automated verification
Put an AI gate in the merge queue: check changes against production requirements,
internal standards (often expressed in natural language), cross-repository dependency
risk, and lightweight functional tests in a sandbox, ending in a clear verdict (BLOCK /
proceed with caution / safe). Verify adherence to architectural patterns and
non-functional conventions (scalability, error handling) as a step distinct from
functional testing — that separation is what lets AI-written code ship without
line-by-line human review.

### Use Abstract Syntax Trees (ASTs) to evaluate the safety and potential side effects of AI-generated code commands before execution.
Analyze AI-generated shell commands by parsing them into ASTs to understand their structural capabilities, track variable resolutions across commands, and identify potential read/write side effects. This method helps catch dangerous command transformations that string-based checks miss.

### Instrument agentic systems with correlated observability
Traditional log-metric-trace models fall short when a workflow spans multiple tools,
models, and execution environments. Correlated traces across every tool call and
intermediate step (e.g. OpenTelemetry extended for agent actions) are what make
reasoning failures, retrieval issues, and latency bottlenecks diagnosable.

### Centralize shared evaluation infrastructure
Don't let every team hand-roll its own eval setups, guardrails, and dashboards — that
fragments quality management and duplicates effort. A platform function owning shared
eval tooling, services, and standard workflows keeps assessment consistent, reusable,
and higher-fidelity across all AI features.

### Let agents optimize the system — and its training data
With a clear metric and operational constraints, an agent can iteratively edit, test,
and update prompts or code unattended ("autoresearch") — active self-optimization on
top of passive regression detection. The same pattern applies upstream: agentic
generation and meta-optimization of synthetic training data converts inference compute
into distribution-matched training signal.

### For huge label vocabularies, hallucinate then map
Don't stuff thousands of valid tags into the context window. Prompt the model to invent
descriptive labels for the input, then map them onto the existing taxonomy with vector
embeddings — faster and more accurate than constrained selection.

### Automate visual inspection of multimodal outputs
Models miss visually-apparent flaws in their own renders even when shown the result.
Use a separate automated visual check (a different model, or computer-vision tooling)
for generated visual content rather than trusting self-review.

## Anti-Patterns

- **Ship-and-pray prompt edits** — changing a prompt with no eval, validating on "a few examples."
- **Blind model upgrades** — moving to the newest model without re-running the eval.
- **Floating model version** — pointing at "latest" so quality changes under you silently.
- **No production monitoring** — offline eval only; drift discovered via customer complaint.
- **Frozen eval set** — never adding the cases that actually failed in production.
- **Unvalidated LLM-as-judge** — trusting a model grader that was never checked against humans.
- **Quality-only view** — ignoring the token/latency cost of a quality "win."

## Self-Assessment

Use [`reviews/llm-eval-review.md`](../../reviews/llm-eval-review.md) to inventory a repo's
AI features, check which have eval coverage and regression gates, and emit a tracked
checklist. Paste it into a Claude Code session in the target repo, or wire it into the
shared review workflow.

## Sources

Saved articles synthesized here (full summaries in `data/digest_knowledge/`):

- **An update on recent Claude Code quality reports** (Simon Willison) — model/harness quality regressions; the need to detect quality change. Digest: 2026-04-26 (crumbl-ops).
- **AI shrinkflation: Why Claude Opus 4.7 may be less capable than the model it replaced** (The New Stack) — "newer ≠ better for your task"; gate model upgrades. Digest: 2026-04-26 (crumbl-ops).
- **Prompt-regression / fixture-based testing recommendations** — testing prompts and agent workflows to keep decision quality stable across model updates. Digests: 2026-05-16 (crumbl-ops, command-center).
- **We Taught AI to Write Code But We Forgot to Teach It to Think** — output quality is reasoning quality, not surface plausibility. Digest: 2026-05-18 (referenced).
- **Spec-driven development at Notion** (Lenny's Newsletter) — autonomous verification against an expected spec. Digest: 2026-05-18.
- **I Don't Review the Code. I Review the Artifacts.** (Paweł Huryn (The Product Compass)) — human review of artifacts over code. Digest: 2026-06-01.
- **OpenAI, Anthropic, Google, Amazon, and xAI all fail on type of attack, study finds** (The New Stack [devops]) — multi-turn interactions for robustness. Digest: 2026-06-02.
- **Opus 4.8 scored 81 in my benchmark. I still wouldn't default to it. (The full breakdown + Nate's Community Slack)** (Nate Jones [ai_strategy]) — evaluating 'effort' settings; beyond benchmark scores, operational characteristics. Digest: 2026-06-03.
- **Why CPUs still matter in the age of AI agents** (The New Stack [devops]) — secure sandboxes for code-generating agents. Digest: 2026-06-03.
- **Autonomous agents have met their biggest challenge yet: The database.** (The New Stack [devops]) — unforgiving correctness for agents in critical systems. Digest: 2026-06-04.
- **Your AI agent is going to hallucinate at scale** (Ruben Dominguez (The AI Corner)) — embedding-proximity memory limitations and hallucination. Digest: 2026-06-04.
- **Scaling Past Informal AI - Carina Hong, Axiom Math** (Latent Space [ai_engineering]) — formal verification for logical rigor. Digest: 2026-06-04.
- **Reality: The Final Eval — Lukas Petersson and Axel Backlund of Andon Labs** (Latent Space [ai_engineering]) — dynamic, multi-step evaluations. Digest: 2026-06-05.
- **How to Stop Shipping Low-Quality RL Environments (with Examples)** (Latent Space [ai_engineering]) — rigor in testing environments. Digest: 2026-06-05.
- Forecast-model evaluation interest (backtesting, accuracy tracking, model-drift detection) recurring across the crumbl-ops digests.
- **AI Agents of the Week: Papers You Should Know About** (Pascal Biese (LLM Watch)) — trajectory-aware evaluation for agents. Digest: 2026-06-14.
- **AWS puts an AI bouncer at the merge queue** (The New Stack) — AI-powered pre-merge gate for code changes. Digest: 2026-06-17.
- **Sakana Fugu is more than a router. But it’s not the blueprint for AI sovereignty, either.** (The New Stack) — evaluating internal logic in multi-agent orchestration. Digest: 2026-06-24.
- **The AI agent identity problem nobody’s talking about** (The New Stack) — explicit IAM evaluation for dynamic AI agents. Digest: 2026-06-26.
- **How I AI: GLM-5.2 review & How Gusto built a new product line with Claude Code** (Lenny's Newsletter) — evaluating open-weight models by non-functional criteria. Digest: 2026-06-29.
- **No Figma. No Jira. No docs. How Gusto built a new product line with Claude Code | Eddie Kim (CTO)** (Lenny's Newsletter) — integrating eval into debugging and iteration workflow. Digest: 2026-06-29.
- **AI Agents of the Week: Papers You Should Know About** (Pascal Biese (LLM Watch)) — agentic systems for synthetic training data generation. Digest: 2026-06-29.
- **Anthropic’s Claude Sonnet 5 system card says more about the future of AI than its benchmarks do** (The New Stack) — evaluating agents for covert behaviors and dynamic prompt injection. Digest: 2026-07-01.
- **Sonnet 5 review: I ran 64 generations to find out if it's worth it** (Lenny's Newsletter) — efficient human qualitative evaluation methods. Digest: 2026-07-01.
- **Why traditional CI/CD fails for LLMs (and the release gates we built to fix it)** (The New Stack) — probabilistic release gates and shadow validation for LLMs. Digest: 2026-07-02.
- **Using DSPy to evaluate and improve Datasette Agent's SQL system prompts** (Simon Willison) — refining tool-use prompts for agents. Digest: 2026-07-02.
- **Set a metric. Walk away. Let the agent optimize overnight.** (Ruben Dominguez (The AI Corner)) — autonomous agent-driven optimization loops. Digest: 2026-07-03.
- **Watch AWS engineers troubleshoot agentic AI with OpenTelemetry and OpenSearch** (The New Stack) — fine-grained, correlated observability for complex agentic systems. Digest: 2026-07-08.
- **The “silent hallucination” loop: how our autonomous data pipeline poisoned its own vector store** (The New Stack) — robust validation and ground-truth checks on intermediate data outputs. Digest: 2026-07-09.
- **Enterprise AI benchmarks are broken** (The New Stack) — cultivating trust and verifiability by openly publishing evaluation methodologies. Digest: 2026-07-09.
- **Why retrieval quality is becoming the defining challenge in AI agent architecture** (The New Stack) — explicitly evaluating retrieval system context quality. Digest: 2026-07-10.
- **Kimi K3, and what we can still learn from the pelican benchmark** (Simon Willison) — granular token usage tracking that differentiates between tokens spent on internal 'reasoning' and tokens used for the final 'output'. Digest: 2026-07-16.
- **A Fireside Chat with Cat and Thariq from the Claude Code team** (Simon Willison) — systematically evaluate the effects of traditional prompt engineering techniques (like providing few-shot examples or negative constraints) on the performance of advanced models. Digest: 2026-07-21.
- **Platform engineering’s new job: serving environments at agent speed** (The New Stack) — evaluate the underlying platform engineering capabilities to provide ephemeral, on-demand, and realistic execution environments for AI agents. Digest: 2026-07-22.
- **Can prompt caching tame RAG costs without sacrificing accuracy?** (The New Stack) — beyond evaluating RAG context quality, systematically evaluate the underlying RAG infrastructure's robustness and efficiency at scale. Digest: 2026-07-22.
- **Cursor, Ramp, and Meta are all building model routers — but two have major model ambitions themselves** (The New Stack) — implement specific evaluations and monitoring for dynamic model routing systems to verify the router's effectiveness. Digest: 2026-07-22.
- **Are AI labs pelicanmaxxing?** (Simon Willison) — systematically test models for benchmark overfitting or training data leakage by varying known benchmark prompts. Digest: 2026-07-22.
- **Your Agent Doesn’t Have a Memory Problem** (Pascal Biese (LLM Watch)) — design evaluations to distinguish between an AI agent's ability to retrieve information and its capacity for semantic understanding and correct application. Digest: 2026-07-22.
- **[AINews] AI Cybersecurity becomes top of mind** (Latent Space) — implement explicit mechanisms for human oversight and intervention in AI agent workflows. Digest: 2026-07-22.
- **The bottleneck for AI agents isn’t the model anymore. It’s the context layer.** (The New Stack) — design, implement, and rigorously evaluate a 'context compilation' layer for AI agents. Digest: 2026-07-22.
- **Why every AI agent decision needs a receipt** (The New Stack) — for agentic systems making data-driven conclusions, mandate and evaluate the generation of a comprehensive 'evidence packet'. Digest: 2026-07-22.
- **Stop guessing whether a cheaper model can do the job. Grab the bakeoff guide: the validator, the manifest, the score sheet, and the fixtures.** (Nate Jones [ai_strategy]) — quantifying hidden costs including human review and correction time. Digest: 2026-07-27.
- **Sam Altman on model distillation: “This is not in my top ten list of worries”** (The New Stack [devops]) — decoupling and evaluating AI agent credentials from direct memory space. Digest: 2026-07-28.
- **The AI “vibe shift”: Why NanoClaw and Echo have teamed up to stop the next Hugging Face Breach** (The New Stack [devops]) — evaluating the security posture of an agent's entire execution stack. Digest: 2026-07-29.
- **Shipping code without human verification** (The New Stack [devops]) — automated verification for AI-generated code against organizational standards and non-functional requirements. Digest: 2026-07-29.
- **OpenAI and Elastic are tackling the AI problem enterprises can’t ignore** (The New Stack [devops]) — evaluating context retrieval for RBAC and multi-tenant data isolation. Digest: 2026-07-30.
- **Investigating three real-world incidents in our cybersecurity evaluations** (Simon Willison [ai_engineering]) — verifying enforcement of simulated boundaries to match agent instructions. Digest: 2026-07-31.
- **Every software company will become a dev tools company** (The New Stack) — centralized platform engineering for shared evaluation infrastructure. Digest: 2026-08-05.
- **LLM Watch Weekly: The Measurement Problem** (Pascal Biese (LLM Watch)) — quantify and track non-determinism in AI model outputs. Digest: 2026-08-07.
- **Your AI agent’s next tool call may be valid but wrong. AWS’s Dogwood promises to fix that.** (The New Stack) — implement and evaluate policy engines that govern AI agent behavior based on the sequence of tool calls and past events. Digest: 2026-08-07.
- **Auto Mode will soon be the default in Claude Code — because humans can’t be trusted** (The New Stack) — design human intervention mechanisms for agentic systems to incorporate an AI-powered classifier. Digest: 2026-08-08.
- **Moonlight & Mayhem (Raccoon Heist by Codex + GPT-5.6 Sol Ultra)** (Simon Willison) — implement specialized automated evaluations for multimodal (e.g., visual) AI outputs. Digest: 2026-08-08.
- **GLM-5.3 didn’t change the base model — where did its coding gains come from?** (The New Stack) — design evaluations that specifically assess the impact of scaled post-training and reinforcement learning on long-horizon tasks for fixed base models. Digest: 2026-08-14.
- **Don't classify. Hallucinate!** (Simon Willison) — for classification or tagging tasks with extensive vocabularies, allow LLMs to 'hallucinate' novel labels, then map these to existing categories using vector embeddings. Digest: 2026-08-15.
- **Most coding agent benchmarks skip large-scale refactoring. Not this one.** (The New Stack) — develop or utilize benchmarks specifically designed to evaluate AI coding agents' capability for large-scale code refactoring and understanding of entire codebases. Digest: 2026-08-21.
- **Google found a way to test Gemini without seeing the questions** (The New Stack) — double-blind evaluation using confidential computing. Digest: 2026-08-28.
- **LM Studio built a judge for AI commands. Then the judge started agreeing with the defendant.** (The New Stack) — AST parsing for safety and side effects in AI-generated commands. Digest: 2026-08-28.
- **Simulation: the new Scaling Law — Joon Sung Park, Simile AI** (Latent Space) — advanced simulations of human behavior (digital twins) for pre-deployment testing. Digest: 2026-08-22.

## Where Used

- **crumbl-ops** — Gemini invoice extraction (per-field accuracy) and email classification (precision/recall) are prime fixture-set candidates; the LightGBM demand forecast needs backtest error + drift tracking; gate any Gemini/Claude model bump behind these.
- **command-center** — digest/classification quality and meeting-prep outputs; LLM-as-judge with human-validated samples; production sampling for drift.
- **wealth-mgmt** — research/extraction accuracy in a "fortress" context; ground-truth verification and hallucination flags are load-bearing before any output is trusted.
