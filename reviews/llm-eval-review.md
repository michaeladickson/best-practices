FIRST: If review-context.md exists, read it for project context and intentional
design decisions. Follow it strictly — do NOT flag intentional decisions.
ALSO: Read existing-issues.md if present — do NOT report findings already tracked there.

---

Perform an **LLM-evaluation self-assessment** of this repository. The goal is to find AI
features whose output quality can drift or regress silently — when a prompt is edited or
a model is upgraded — because nothing tests the *quality of the model's output* (unit
tests only check code). Hunt the gap between "the code runs" and "the output is right."

Do two things:

**Part A — Inventory the AI features.** Find every place the app calls an LLM/ML model to
produce an output users or downstream logic depend on. Look at: Gemini/LLM client calls,
classification/extraction/generation prompts, forecasting/ML models, and any "draft" or
"summary" an agent emits. For each, note: task type (extraction / classification /
generation / forecast), and whether it has any eval coverage today.

**Part B — Grade the coverage.** For each area below: state the current state, grade it
**Good / Gap / Missing**, and give a concrete fix with the file/path.

1. **Golden/fixture dataset** — Does each AI feature have a curated `input → expected`
   set (including known edge cases), or is correctness judged ad hoc / "looks good"?

2. **Right metric per task** — Is quality measured with a task-appropriate metric
   (extraction → per-field accuracy; classification → precision/recall/confusion;
   forecast → backtest MAPE/RMSE; generation → rubric/LLM-as-judge), or not measured?

3. **Regression gate in CI** — Is the eval re-run on prompt changes and gated (fails if
   quality drops below baseline), or do prompt edits ship unchecked?

4. **Model-version pinning & upgrade gate** — Are model versions pinned (not floating to
   "latest"), and is a model upgrade gated behind the eval set? (Defense against
   "shrinkflation" / silent model regressions — HIGH weight for money/decision-critical
   features.)

5. **Production quality / drift monitoring** — Are live outputs sampled and tracked over
   time with drift alerts (sliding precision, widening forecast error, new-format
   extraction failures)? Or is quality only ever checked offline / never?

6. **LLM-as-judge validation** — If a model grades open-ended outputs, has the judge been
   validated against human labels? Or is an unvalidated grader trusted?

7. **Ground-truth / hallucination checks** — For extraction & research outputs, are
   results verified against the source and unsupported claims flagged? Are raw data and
   AI synthesis kept distinguishable?

8. **Eval set grows from failures** — When a bad output reaches production, is that case
   added to the fixture set so it can't silently regress again? Or is the eval set frozen
   / nonexistent?

9. **Cost/latency tracked with quality** — Is token count / latency recorded alongside
   the quality score, so an "improvement" that blows the budget is visible?

Reference standard: `best-practices/practices/ai/llm-evaluation.md`. This is about
*model output quality*; don't duplicate `reviews/qa-review.md` (code edge cases) or
`reviews/data-review.md` (pipeline integrity) — focus on whether AI outputs are evaluated
and gated.

Format your findings as a markdown document with:
- The Part-A feature inventory (feature → task type → eval coverage today).
- A one-line scorecard: count of Good / Gap / Missing across the 9 areas.
- Findings grouped by priority (High / Medium / Low) — money/decision-critical features
  with no eval or no model-upgrade gate rank High.
- Each finding: area number + name, current state, grade, concrete fix with file/path,
  and the feature/file that prompted it.
- Use markdown checkboxes so items can be tracked.

Output ONLY the findings, no title or preamble.
