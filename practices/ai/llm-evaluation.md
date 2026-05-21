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

### 1. Build a golden/fixture dataset per AI feature
For each feature (invoice extraction, email classification, draft generation, forecast),
curate a set of representative `input → expected` examples — including the gnarly edge
cases that have bitten you. This is the institutional memory of "what good looks like."
Start small (20–50 cases) and grow it.

### 2. Grade with the right metric for the task type
"Looks good" is not a metric. Match the metric to the output:

| Task | Metric |
|---|---|
| Extraction (invoice fields) | per-field exact/normalized accuracy |
| Classification (email routing) | precision / recall / confusion matrix |
| Forecasting (demand) | backtest error — MAPE / RMSE vs. actuals |
| Open-ended generation | rubric score (LLM-as-judge) + spot human review |

### 3. Run the eval on every prompt change AND every model change — in CI
The eval set is a regression gate, not a one-time exercise. Re-run it when a prompt
changes and when you consider a model upgrade; **fail the change if quality drops**
below the baseline. This is "prompt-regression testing" / fixture-based testing for
prompts (digest 2026-05-16).

### 4. Pin model versions; gate upgrades behind the eval
Never let a model float to "latest" silently. Pin the version, and treat a model bump
as a change that must pass the eval set first. This is the concrete defense against
"shrinkflation" and silent harness regressions.

### 5. Track production quality over time (drift detection)
Offline eval is necessary but not sufficient. Sample live outputs and track accuracy
over time; alert on **drift** — a classifier whose precision is sliding, a forecast
whose error is widening, an extractor failing on a new vendor's format. For ML models
this is model-drift detection; for LLM features it's the same idea on output quality.

### 6. LLM-as-judge for open-ended outputs — but validate the judge
For generation tasks where exact-match doesn't apply, score against an explicit rubric
using a model judge. Validate the judge against human labels on a sample before trusting
it, and watch for it rewarding fluent-but-wrong answers.

### 7. Verify against ground truth; flag unsupported claims
For extraction and research outputs, check against the source document and flag anything
the source doesn't support (the hallucination guard). Keep raw data and AI synthesis
distinguishable so a reviewer can verify.

### 8. Graduate production failures into the eval set
When a bad output reaches production, add that case (with its correct answer) to the
fixture set so it can never silently regress again. The eval set should grow from real
misses, not stay frozen.

### 9. Track cost and latency alongside quality
A prompt that's 3% more accurate but 2× the tokens may be a bad trade. Record token
count and latency next to the quality score so an "improvement" that blows the budget is
visible (ties into AI spend governance).

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
- Forecast-model evaluation interest (backtesting, accuracy tracking, model-drift detection) recurring across the crumbl-ops digests.

## Where Used

- **crumbl-ops** — Gemini invoice extraction (per-field accuracy) and email classification (precision/recall) are prime fixture-set candidates; the LightGBM demand forecast needs backtest error + drift tracking; gate any Gemini/Claude model bump behind these.
- **command-center** — digest/classification quality and meeting-prep outputs; LLM-as-judge with human-validated samples; production sampling for drift.
- **wealth-mgmt** — research/extraction accuracy in a "fortress" context; ground-truth verification and hallucination flags are load-bearing before any output is trusted.
