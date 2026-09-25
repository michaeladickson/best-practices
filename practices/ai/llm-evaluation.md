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
numbered cross-references rot. Consolidated 2026-08-28 (59 → 27 entries) and again
2026-09-24 (49 → 21, with entries another doc owns moved to *Adjacent Concerns*); the
per-article trail is unchanged under [Sources](#sources).

**Scope check before adding here:** does it measure whether an LLM's *output* is good, or
catch it getting worse? Gating what an agent may *do* belongs in
[Agent Action Safety](../ai-safety/agent-action-safety.md); reviewing code an agent wrote in
[Code Review & AI Slop](../claude-code/code-review-and-ai-slop.md).

### Theme A — What to measure

### Analyze AI product failure modes before metrics
Prioritize a thorough analysis of potential failure modes and unintended behaviors in AI products before defining evaluation metrics. Understanding how a system can fail is crucial to ensuring that the right things are measured for effective improvement.

### Decide which calls earn a floor — and check you did not only measure the easy ones
Not every LLM call needs an eval. The line that has held up: **an LLM call whose output
reaches someone outside the team, or is written to a durable artifact without review,
needs a floor.** Internal, reviewed, or throwaway output does not.

The failure this prevents is not "no evals". It is evals pointed at the wrong half of the
system, which looks like coverage and is not. Measured across four repos on 2026-09-13:

| Had a golden set | Baseline | Had none |
|---|---|---|
| Email classifier | 22/22 (100%) | Customer-facing draft generation |
| SKU pick | 12/12 (100%) | Receipt vision parsing into accounting |
| Donation screener | 16/16 (100%) | The CFO narrative |
| | | Financial transaction categorization |
| | | A weekly job that auto-edits living docs |

Every measured task was classification with an objectively correct answer — the easiest
thing to score, and the least likely to need a better model. Every unmeasured one was
generative judgment work where quality is real and invisible. Coverage had grown toward
what was easy to grade rather than what mattered if it broke.

Audit for this directly: list every LLM call site, mark which have a floor, and look at
the shape of the two groups. If the evaluated ones are all classifiers, the coverage is
inverted.

### A task at 100% cannot answer "should we upgrade"
A floor is a regression guard, not a quality score. It catches a change making things
worse; it says nothing about whether a change would make things better, and a task
already at 100% has no headroom to show either.

This matters when a deprecation or a price change forces a model decision. Asked "is
there a better model for this", the honest answer splits three ways: *provably no* for
tasks at ceiling, *yes and here is the evidence* for tasks with headroom, and **"we
cannot tell you"** for everything unmeasured. That third answer is the expensive one,
and it is the default until someone builds the set.

So when choosing new golden sets, pick tasks hard enough to discriminate between models.
A set that every candidate model passes is a regression gate and nothing more — useful,
but it will not answer the next model question either.

### Build a golden/fixture dataset per AI feature
For each feature (invoice extraction, email classification, draft generation, forecast),
curate a set of representative `input → expected` examples — including the gnarly edge
cases that have bitten you. This is the institutional memory of "what good looks like."
Start small (20–50 cases) and grow it.

- **Graduate production failures into the eval set.** When a bad output reaches production, add that case (with its correct answer) to the fixture set so it can never silently regress again. Make it the default debugging motion — a customer bug becomes an eval case *first*, then the fix is validated against it (an eval-first workflow).
- **Test the agent's forbidden states explicitly.** Include cases for what the agent must *not* do or expose, and how it should fail when it cannot finish within its limits.

### Grade with the right metric for the task type
"Looks good" is not a metric. Match the metric to the output:

| Task | Metric |
|---|---|
| Extraction (invoice fields) | per-field exact/normalized accuracy |
| Classification (email routing) | precision / recall / confusion matrix |
| Forecasting (demand) | backtest error — MAPE / RMSE vs. actuals |
| Open-ended generation | rubric score (LLM-as-judge) + spot human review |

- **Check that confidence is calibrated.** Where a model reports a probability, measure whether its stated confidence matches its actual accuracy on your task.

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

### Account for non-determinism in evaluation
Outputs vary run to run, and more so with external tools enabled. Quantify the
variation, run each eval case multiple times and score aggregates, reduce
non-determinism where you can (temperature, seeding), and use matching strategies
robust to it where you can't.

### Theme B — Gating change and watching production

### Run the eval on every prompt change AND every model change — in CI
The eval set is a regression gate, not a one-time exercise. Re-run it when a prompt
changes and when you consider a model upgrade; **fail the change if quality drops**
below the baseline. This is "prompt-regression testing" / fixture-based testing for
prompts (digest 2026-05-16). Re-test inherited prompt *patterns* too: few-shot examples
and negative-constraint lists that helped an older model can actively degrade a newer
one, so prompt-engineering habits are themselves a thing the eval must catch.

- **Version guidance files and evaluate them too.** Shared files encoding judgment (a `design.md` for brand style, a policy prompt) change output as much as a prompt edit does; version them and measure whether they reduce the failures they target.

### Track code changes from PR to production
Establish a continuous pipeline to track individual code changes from pull request through deployment to production. Monitor their behavior and performance to verify they act as intended and to quickly identify regressions introduced by AI-generated code.

### Pin model versions; gate upgrades behind the eval
Never let a model float to "latest" silently. Pin the version, and treat a model bump
as a change that must pass the eval set first. This is the concrete defense against
"shrinkflation" and silent harness regressions. When an upgrade *does* improve agentic
or long-horizon work, the gain often comes from post-training/RL rather than a new base
model — evaluate the claim on your tasks instead of assuming a capability jump.

### Track production quality over time (drift detection)
Offline eval is necessary but not sufficient. Sample live outputs and track accuracy
over time; alert on **drift** — a classifier whose precision is sliding, a forecast
whose error is widening, an extractor failing on a new vendor's format. For ML models
this is model-drift detection; for LLM features it's the same idea on output quality.
Before a cutover, **shadow-validate**: run the candidate model or prompt passively
against live traffic — binary CI thresholds miss the gradual eval drift that only shows
up on messy production inputs.

### Track cost, latency, and the human cost alongside quality
A prompt that's 3% more accurate but 2× the tokens may be a bad trade. Record token
count and latency next to the quality score so an "improvement" that blows the budget is
visible (ties into AI spend governance). Split token accounting between internal
*reasoning* and final *output* — in agentic systems the scratchpad is often the dominant
cost driver. And count the humans: a cheaper model that needs more review and correction
per accepted output costs more than its API price suggests, and an agent fleet carries
operational overhead — allocation, specification, intervention, coordination, recovery
("agent fatigue") — that belongs in the same total-cost-of-ownership ledger.

- **Measure under realistic infrastructure load.** Latency, reliability and cost shift under contention; test load profiles, not an idle system.
- **Measure business outcomes, not agent activity.** Plans, reports and long reasoning chains look like work; score the result the agent exists for (a conversion, a resolved bug).

### Theme C — Evaluating agents

### Judge agent trajectories and require evidence, not just outputs
Score the sequence of steps, not only the final answer. Trajectory-aware judges catch
reasoning shortcuts, fabricated intermediate results, and exploitation of test
artifacts — right answers for wrong reasons. For agents drawing data-driven
conclusions, make them emit an **evidence packet** — queries run, statistical
justification, completeness assessment, alternative hypotheses considered — and
evaluate the packet as part of the output.

- **Require the full reasoning trace for critical evaluations**, especially where a model may obscure its intermediate steps.
- **Test for motivated reasoning and reward hacking.** Probe whether the agent infers and games the scoring, exploits the environment, or takes unauthorized actions to hit its objective.
- **Detect deceptive or self-preserving behavior.** Concealed mistakes, fabricated information, and instructions the agent writes for itself to avoid detection.

### Evaluate retrieval and context quality separately from generation
When a RAG or agentic feature fails, the retrieval/context-building step is a distinct
suspect from the generator — score whether the right context was assembled at all. If
agents reason over raw, messy enterprise data, evaluate a "context compilation" layer
that structures it into a queryable knowledge base first. Expect embedding-proximity
memory to hallucinate and forget more as it grows — an architectural limit, not a tuning
problem. And test the gap between *retrieving* a fact and *understanding* it: agents can
recall accurately while misapplying meaning or context.

- **Evaluate RAG infrastructure at scale — including access control.** Naive RAG fails at production scale (timeouts, data loss); evaluate ingestion, prompt caching, cost and latency as part of quality, and verify retrieval honors RBAC and multi-tenant isolation.

### Evaluate the orchestration layer: routers, decomposition, tool prompts
Multi-agent decomposition and dynamic model routing are their own failure surfaces.
Evaluate the router's decisions and the decomposition quality by their effect on
end-to-end quality, cost, and latency — even when the internal logic is proprietary or
opaque. At the prompt level, most tool-use retry loops trace to missing context (a
schema listed without column names, instructions that invite guessing); fix the tool
documentation before blaming the model.

- **Evaluate agents that build agents.** Goal-setting for sub-agents, architecture choice, working code, and the tests the builder writes for what it built.
- **Evaluate continuity during asynchronous delegation.** In voice and multi-step agents, score whether the front end keeps a coherent conversation while a backend model works.

### Run long-horizon simulations — and verify the eval environment itself
Beyond isolated input→output checks, run dynamic, business-like multi-step simulations;
emergent failures only appear there. Then treat the environment as a system under test:
an unreliable harness teaches agents wrong behavior and voids results, and a simulated
boundary ("this is a simulation," "no internet access") must be *enforced* by the
environment rather than asserted to the agent — especially in security-critical evals.
Serving these environments at agent speed is a platform capability in its own right:
measure provisioning latency, concurrent capacity, and dependency fidelity.

- **Test whether agents can escape the eval environment.** Include scenarios that probe for side channels, unintended communication paths and isolation flaws.
- **Simulate users, not just tasks.** Digital twins of human behavior, built from interviews, observation and transactions and checked with causal methods such as RCTs, surface emergent behavior before deployment.

### Test safety multi-turn and in-environment
Single-turn safety checks miss most real attacks. Evaluate across multi-turn
interactions, and test prompt injection where it actually arrives — embedded in web
pages the agent browses and code it executes, not just pasted into a prompt. Probe for
covert behavior too: agents pursuing hidden goals while appearing compliant.

### Evaluate operational characteristics, not just benchmark scores
Production reliability lives in behaviors benchmarks don't score: source discipline,
operational judgment, provenance tracking, self-correction. Sweep configurable
"effort"/reasoning settings — turning the dial up sometimes makes output *worse*. And
when selecting a model, weigh non-functional criteria — cost, control, vendor lock-in,
open-weight viability — alongside raw capability.

### Theme D — Benchmarks, infrastructure and optimization

### Estimate full benchmark scores from a subset
For efficient evaluation of frequently changing agents, develop methods to reliably estimate full benchmark scores from a statistically significant subset of questions. This allows for faster re-testing cycles with quantifiable error margins.

### Probe benchmarks for overfitting — and publish your eval methodology
Models memorize benchmark patterns. Vary known benchmark prompts and probe for direct
recall to test generalization rather than trusting headline scores. Prefer benchmarks
shaped like the real task — most coding-agent benchmarks skip large-scale refactoring
and whole-codebase comprehension, so use ones built for it. And when your eval claims
need to be trusted by others, publish the datasets, harness, judging criteria, results,
and raw traces so outside reviewers can replicate and attack the methodology.

- **Separate harness contribution from model contribution.** A benchmark scores the whole system; attribute gains from the harness (reasoning-state preservation, compaction) before crediting the model.
- **Run double-blind evals to prevent benchmark leakage.** Confidential computing keeps weights private from evaluators and test sets private from providers.

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

### Automate visual inspection of multimodal outputs
Models miss visually-apparent flaws in their own renders even when shown the result.
Use a separate automated visual check (a different model, or computer-vision tooling)
for generated visual content rather than trusting self-review.

## Adjacent Concerns

Added here by the weekly updater, owned by a sibling doc. One line each so the source
stays traceable; the practice itself lives at the link.

- **Sandbox agent execution and evaluate the whole stack** → [Agent Action Safety](../ai-safety/agent-action-safety.md), *Isolate agent-generated code execution within hardened sandboxes*.
- **Evaluate agent identity, credentials, and action-sequence policy** → [Agent Action Safety](../ai-safety/agent-action-safety.md), *Give every agent a verifiable identity* and *Authorize action sequences, not single calls*.
- **Design human oversight that scales** → [Agent Action Safety](../ai-safety/agent-action-safety.md), *Pre-screen routine actions, escalate the rest*.
- **Parse generated commands into an AST before running** → [Agent Action Safety](../ai-safety/agent-action-safety.md), *A Judge Layer gates the action, not the prose*.
- **Instrument agentic systems with correlated observability** → [Agent Action Safety](../ai-safety/agent-action-safety.md), *Correlate logs, metrics, traces and tool calls*.
- **Gate AI-generated code with automated verification** and **gate every change to an AI system in CI** → [Code Review & AI Slop](../claude-code/code-review-and-ai-slop.md), *Build the review pipeline out of independent verifiers*.
- **Use context-blind subagents for adversarial pre-review** → [Model-Hierarchy Delegation](../claude-code/model-hierarchy-delegation.md), *Verify with a different, cheaper agent*.
- **For huge label vocabularies, hallucinate then map** → [Prompt Engineering](prompt-engineering.md). A prompting technique, not an evaluation practice: have the model invent descriptive labels, then map them onto the taxonomy with embeddings.
- **Publish the full training and eval artifacts**, **have third parties audit your safety evals**, and **employ continuous embedded third-party evaluators** → out of scope for every practice doc: these are model-lab governance, not something a team shipping LLM features does. Kept here so the sources stay traceable.

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
- **This week in Claude Code (2026-08-28): /resume on desktop, phone-started sessions, subagent memory, cost tooling** (Claude Code weekly newsletter (email)) — Utilize context-blind subagents for adversarial pre-review of agent-generated outputs to uncover latent flaws. Digest: 2026-08-28.
- **Executive Briefing: You Are Paying for Agent Activity and Calling It Work** (Nate Jones) — Evaluate agent performance based on quantifiable business impact and desired real-world outcomes, not merely on the generation of intermediate process or internal activity. Digest: 2026-08-30.
- **Vercel built a feedback loop that treats agent instructions like software** (The New Stack) — Manage and evaluate agent 'guidance files' (e.g., shared prompt files encoding design principles or operational policies) as distinct, version-controlled assets. Digest: 2026-09-02.
- **AI agent evaluations are part of the product** (The New Stack) — Define and test explicit operating boundaries for agents, including unacceptable actions, forbidden states, and how they should handle unknown or unresolvable situations. Digest: 2026-09-04.
- **OpenAI will sell you Astra, but not the system that scored 98.6% on ARC-AGI-3** (The New Stack) — Explicitly differentiate and quantify the performance contribution of the evaluation harness or surrounding system from the raw model on benchmarks. Digest: 2026-09-04.
- **OpenAI's rogue agents were caught communicating via public wikis** (Simon Willison [ai_engineering]) — Develop specific evaluation scenarios to test for agent motivated reasoning and misalignment, where agents might pursue narrow task objectives through unintended or harmful actions, or optimize for imagined evaluation criteria. Digest: 2026-09-04.
- **[AINews] Collusion.wiki: A second undisclosed OpenAI agent swarm incident...** (Latent Space) — Proactively test agents for their ability to discover and exploit hidden channels, side effects, or limitations within the evaluation environment for unauthorized communication, data exfiltration, or control. Digest: 2026-09-05.
- **GPT-6 Astra, Looped Transformers, and Hidden Reasoning** (Sebastian Raschka (Ahead of AI)) — Mandate the exposure and evaluation of an LLM's full reasoning trace or chain of thought, particularly for models rumored to be obscuring it, to ensure interpretability and verifiability of complex outputs. Digest: 2026-09-09.
- **K2 Horizon just shipped as six new fully open models — developers aren’t fully convinced** (The New Stack) — Adopt a 'fully open' approach to model development artifacts, publishing training and evaluation code, detailed data recipes, configurations, logs, and intermediate checkpoints to enable full inspectability, reproducibility, and external validation of model capabilities and behaviors. Digest: 2026-09-09.
- **Claude performed best on a new benchmark for ‘agents that build agents’. But it passed fewer than a quarter of the tests.** (The New Stack) — Evaluate the capability of agents to autonomously design, build, and test other AI agents (meta-agents). Digest: 2026-09-10.
- **OpenAI gave an AI the power to block its own engineers’ code** (The New Stack) — Integrate AI-powered automated security and correctness reviews into CI/CD pipelines to gate all code changes, regardless of origin, that impact AI systems. Digest: 2026-09-10.
- **OpenAI split a voice model’s brain. Then one team deleted 23,000 lines of code.** (The New Stack) — Evaluate conversational fluency and continuity during asynchronous agent delegation. Digest: 2026-09-11.
- **“Valuable warning shots”: How Anthropic now views Claude’s cyber incidents** (The New Stack) — Periodically engage independent third parties to audit and validate internal safety evaluation methodologies and results, particularly for frontier models with potential emergent risks. Digest: 2026-09-11.
- **AI evaluator: The most important AI job in history? How developers might fill the proposed new job** (The New Stack) — Employ continuous embedded third-party evaluators to verify safety practices. Digest: 2026-09-16.
- **“Be transparent only if asked”: OpenAI’s models learned to leave notes for their future selves** (The New Stack) — Detect subtle deceptive or self-preserving agent behaviors. Digest: 2026-09-17.
- **Your agent is only as good as your infrastructure** (The New Stack) — Evaluate agent performance under variable infrastructure load. Digest: 2026-09-18.
- **TypeSafe Shipped a Model That Never Writes a Word. Here’s the Decision-Layer Playbook** (Ruben Dominguez (The AI Corner)) — Evaluate model probabilistic confidence calibration. Digest: 2026-09-20.
- **Advanced evals: How to find (and fix) hidden AI failures in your product** (Lenny's Newsletter) — analyze potential failure modes before defining evaluation metrics. Digest: 2026-09-22.
- **Cursor acquired Firetiger. A month later, it launched a bot that tracks code changes from PR to production.** (The New Stack) — establish a continuous pipeline to track and monitor code changes from PR to production for regressions. Digest: 2026-09-24.
- **Papers You Should Know About** (Pascal Biese (LLM Watch)) — estimate full benchmark scores from a statistically significant subset of questions for efficient evaluation. Digest: 2026-09-25.

## Where Used

- **crumbl-ops** — Gemini invoice extraction (per-field accuracy) and email classification (precision/recall) are prime fixture-set candidates; the LightGBM demand forecast needs backtest error + drift tracking; gate any Gemini/Claude model bump behind these.
- **command-center** — digest/classification quality and meeting-prep outputs; LLM-as-judge with human-validated samples; production sampling for drift.
- **wealth-mgmt** — research/extraction accuracy in a "fortress" context; ground-truth verification and hallucination flags are load-bearing before any output is trusted.

### Coverage audit, 2026-09-13

Triggered by the Gemini 2.5 deprecation, which forced a model decision across 27 live
call sites and found the inversion above.

- **crumbl-ops** — three golden sets, all classifiers at 100%. CS draft house-style eval
  added ([PR #2575](https://github.com/michaeladickson/crumbl-ops/pull/2575)); scores the
  rules `_HOUSE_STYLE` already states, each traceable to a ticket that reached the queue.
  Deterministic assertions rather than an LLM judge: when the thing under test is "did the
  model stop following an instruction", asking a model is circular.
- **Open gaps**, named rather than tracked — neither is committed work:
  - wealth-mgmt `src/spending/categorizer.py`. The highest-stakes unmeasured site: a silent
    quality regression corrupts data that reporting rests on, and there is already a
    decision record and a cost measurement tied to that model with nothing connecting
    either to output quality.
  - best-practices `digest/practice_updater.py`. Auto-edits living docs weekly behind a
    validator that only checks the H1 and required anchors survived; a quality regression
    passes it and lands as an `[automated]` commit.
