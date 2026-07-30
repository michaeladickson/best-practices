# Email Drafting — Voice, Brevity, and Process Exposure

How to draft email that reads like Michael wrote it, for both **interactive drafting**
(Claude drafting for him in a session) and **agent prompts** (CS auto-replies, prep emails,
digests). One source so the two don't drift.

Adjacent: [Prompt Engineering](../ai/prompt-engineering.md) · [LLM Evaluation](../ai/llm-evaluation.md)
(prompt changes need a regression check) · [Prompt Injection Mitigation](../ai-safety/prompt-injection-mitigation.md)
(untrusted email fields belong in `contents`, never `system_instruction`).

## The two rules

**R1 — the email carries the ask, not the derivation.**
The reader gets the conclusion and what's needed from them. How it was reached, what was
reviewed, who it was checked with, what was ruled out, and what the internal status is are
all internal. This is the rule Michael names most often: drafts "expose the process behind
how I arrived at the email."

**R2 — length follows from the ask, never from a budget.**
Two sentences is a complete email. Nothing is added to reach a length.

Everything below is a consequence of these two.

## Why this is hard to fix (the mechanism)

**A summary of the reasoning in the context leaks into the output.** This is the root cause
of R1 violations and it is a *context* problem, not an instruction problem.

The clearest demonstration is in code. crumbl-ops `generate_ai_draft` was handed the AI
classification summary of a customer complaint alongside the complaint itself. Answering a
*summary of a complaint* means demonstrating you understood it — i.e. restating it. The
prompt then had to fight its own input with "don't restate their whole issue back to them,"
and lost. Removing the summary parameter fixed what the instruction couldn't.

The same holds interactively: if the analysis is in the context, it shows up in the draft.
**Remove the derivation from the input rather than instructing against reproducing it.**

## Writing the draft

- **Open with the ask or the answer.** Not with context the reader already has, and never
  with "Thank you for reaching out and bringing this to our attention."
- **Don't restate their message.** They wrote it. Acknowledge in a few words, then respond.
- **No internal process.** No "I reviewed…", no "I've flagged this with our team," no
  explaining how the org works internally or how you reached the answer. If something
  genuinely needs escalation: one clause, no detail about who or how.
- **Let the reader draw the conclusion.** State facts plainly, strip adjectives. Address
  weaknesses factually rather than spinning them.
- **Check prior state first.** Fresh ask or follow-up? It changes tone and length. A
  follow-up that reintroduces itself reads as though the first one never happened.
- **Iterate down.** Start from the shortest version that carries the ask and add only what
  the reader demonstrably lacks.
- **Strip unsettled numbers from counterparty previews.** Keep contractual amounts; every
  not-yet-final dollar figure comes out. Asks are phrased as confirmations. The attachment
  carries the numbers.

## Writing the prompt (agent-drafted email)

Five levers, in the order they mattered on a measured fix (crumbl-ops#1185: **196 → 80 body
words, 59% shorter** on a live 3-sample A/B):

| Lever | Rule |
|---|---|
| **Length** | **A stated range reads as a FLOOR.** "4-6 sentences" tells the model to produce at least four, so it pads. State a ceiling only: "AT MOST 4 sentences, and use fewer whenever fewer will do. Two sentences is a complete reply. Never pad to reach a length." |
| **Token cap** | **A cap that never binds enforces nothing.** 500 tokens ≈ 375 words against a ~60-word reply — it was never reached. Size the cap just above a correct answer (200 for a 4-sentence reply + signoff). |
| **Input** | **Never pass a summary of the input.** See the mechanism above. Enforce at the signature, not in the prompt — an accepted-and-ignored parameter passes lint silently and gets rewired by the next reader. |
| **Exemplars** | **Prohibitions get you to inoffensive; an example gets you to brief.** Include one or two exemplar replies at the target length. |
| **Temperature** | These replies are formulaic on purpose. Sampling variety buys hedging and preamble. 0.7 → 0.2. |

Two footguns:

- **Gemini 2.5 flash bills hidden thinking against `max_output_tokens`** (routinely 5.5k+).
  Any cap below ~8k **requires** `thinking_config={"thinking_budget": 0}` or the reply
  truncates to nothing. Tightening a cap and disabling thinking are one change, not two.
- **A range can be legitimate for an internal report** where substance is the point. The
  floor effect is a bug for a customer email and a feature for a "3 key takeaways" section.
  Decide per prompt; don't sweep.

## Verification

**A live A/B is the acceptance test. A passing unit test is not.**

On the crumbl-ops fix, every test passed on a prompt that then offered a customer a free
6-pack "on the house" unprompted — an invented discount, caught only by generating real
output. Generate before/after on 3+ real samples, count body words, and read them.

Shape-level regression tests are still worth having where there's code — they lock the shape
of the fix without freezing the wording. See crumbl-ops `tests/test_cs_draft_brevity.py`:
no-range-stated, ceiling-stated, cap-actually-binds, no-summary-parameter (by
`inspect.signature`), temperature-low, exemplar-present.

Also assert on the **task**, not on persona prose. A security test that checked
`"customer service representative" in system_instruction` made legitimate prompt tuning look
like a security regression. Anchor to what an attacker must not reach: the output contract
and the injection warning.

## One more leak to check

Internal *rationale* fields are the highest-risk thing to hand a drafting prompt. crumbl-ops
`generate_donation_draft` was passing `screening_details["reasoning"]` to the model — for a
tier-C decline, literally *why we said no* ("low marketing value, outside our trade area") —
into a draft a manager sends from Slack. Before adding any field to a drafting prompt, ask
what it says if it reaches the recipient verbatim.
