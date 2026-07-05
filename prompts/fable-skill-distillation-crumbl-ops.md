# Fable 5 skill-distillation prompt — crumbl-ops

> **How to use.** Open a fresh Claude Code session **inside** `C:\Users\micha\crumbl-ops`, on Fable 5 (`claude --model fable-5` or `/model fable-5` in-session). Verify with `/model` that Fable is active before pasting. Then paste the block below verbatim as your first message. Expect one focused, expensive session — do it when you can supervise it start to finish. Do NOT run this via a subagent — Fable's own reasoning is the value; a subagent hop dilutes it.
>
> Reference: [Abhijay Vuyyuru — "How to Make Claude's Smartest Model Train Its Cheaper One"](https://abhijayvuyyuru.substack.com/p/how-to-make-claudes-smartest-model). The recurring line to hold in mind while reviewing the output: *"Every skill is a scar turned into a rule."*

---

```
You are the departing principal architect on crumbl-ops.

## Context
crumbl-ops is a Python 3.12 / FastAPI / PostgreSQL 17 / React 18 + TS platform
supporting 3+ Crumbl Cookies franchise locations in Kentucky, expanding to 10
stores via two acquisitions in July 2026. Owner/operator acts as both CTO and
CFO; effective team size is two. Primary development is done with Claude Code.
AI in production: Gemini for vendor invoice extraction, email classification,
digest synthesis, and draft response generation; Claude (Opus 4.7/Opus 4.8) for
month-end narratives and dual-model weekly reviews; a statistical median_v1/v3
demand forecast; LightGBM is roadmapped, not live. QBO journal-entry posting is
money movement; payroll is money movement; marketplace reconciliation touches
real cash. Blast radius is real.

## Your task
Your final task before you leave is to author a skill library under
`.claude/skills/` so Opus- and Sonnet-class models can carry crumbl-ops forward
at close to your standard.

## Rules
1. The repo is READ-ONLY. Write ONLY inside `.claude/skills/`. Do not modify
   `src/`, `tests/`, `.github/`, `migrations/`, `scripts/`, or any other tree.
   If you spot a real bug while reading, note it in your final summary — do
   not fix it.
2. Every skill must be justified by a REAL failure mode you can see in the
   code, tests, git history, memory files, audit issues, or post-mortems.
   No generic best-practices advice. Every skill is a scar turned into a rule.
3. Each skill lives at `.claude/skills/<name>/SKILL.md` with YAML frontmatter:
       ---
       name: <kebab-case, matches directory>
       description: <trigger-rich, symptom-focused sentence saying WHEN to load
         this skill — mention concrete files, tasks, or symptoms Claude will
         see when it should trigger. Not "what it does" — "when to load it".>
       ---
   Only set `model:` or `tools:` if the skill genuinely requires it.
4. Verify every command, file path, function name, DB column, and line number
   against the actual repo BEFORE writing it into a skill. A wrong runbook is
   worse than none. Prefer batched reads to save round trips.
5. Each skill must include a "When NOT to use" section that (a) names the
   concrete cases where it's the wrong tool, and (b) redirects to the sibling
   skill that IS the right tool. Skills without redirects are half-skills.
6. Match the voice, depth, and structure of the existing
   `.claude/skills/verify/SKILL.md` — that's the standard. Extend the library;
   do not duplicate. Before authoring, list every existing skill under
   `.claude/skills/` and skip any you'd otherwise re-author (note them in your
   summary).
7. Match crumbl-ops idioms: WSL bash on Windows; Cloud Run via
   `gcloud builds submit`; `gh` CLI is authenticated; structlog + JSON logs;
   raw psycopg with `%s` placeholders (NO ORM); single-file views by design;
   `Decimal` for money (never float); QBO client `_balanced` gate + $500
   variance cap for suspense JEs; agent-facing MCP is read-only by
   construction; `defaultMode:auto` is intentional.

## Scar-tissue map — READ THESE FIRST
These are your inputs. Every skill you author must trace back to a specific
locator in this map. Batch-read where possible.

### Audit findings (fetch each with `gh issue view <n> -R michaeladickson/crumbl-ops`)
- **#470 — Context/memory audit.** Produced the path-scoped `.claude/rules/*.md`
  files that already auto-load destructive-action context. Treat those rules
  as adjacent, existing infrastructure — don't re-author them as skills.
- **#473 — AI-slop / code review.** Two open items worth codifying: (a) shift
  the second-model review from post-merge Saturday cron to a pre-merge PR gate
  (aligns with already-open #444 / #442 / #443); (b) split
  `src/ops/data_quality.py` (7,836 lines) into a domain-partitioned package.
  Also: `/verify` Step 8 already implements the checklist — extend, don't
  duplicate.
- **#474 — Agent action safety.** Six of eight areas Good. Open items: a
  `PreToolUse` Bash hook enforcing gates on `gcloud builds submit`,
  `gcloud run * update`, `git push --force`, and unscoped
  `DELETE/TRUNCATE/UPDATE` (memory-only enforcement of the deploy rule was
  violated 3–4× in 48h); a single `assert_balanced_or_skip(payload)` helper to
  collapse 4+ independent `_balanced` checks; `posted_by`/`source` provenance
  columns on `marketplace_je_log` and a JE-post audit row.
- **#475 — LLM eval.** Weakest area. Open items: build fixture datasets for
  the CS Gemini features (classifier, donation screener, responder) and the
  SKU shadow matcher; pin `month_end_review.py:708` from floating `--model
  opus` to `claude-opus-4-7`; add a CI-gated backtest fixture for the demand
  forecast; extend `digest_synthesis._grounding_check` to
  `weekly_bi_report.generate_ai_insights` and the month-end narratives.

### Guardrails you MUST honor
- `.github/prompts/review-context.md` — the intentional-decisions list,
  pre-shipped ai-trust findings, known-backlog items (no-ORM, single-file
  views/#36, localStorage JWT/#34, hardcoded N-store loops/#426–428, structlog,
  pinned model-string literals per line 302), the "actionable by a 2-person
  team" and "every finding teaches" rules. Skills MUST NOT contradict any of
  these. If a candidate skill would, drop it.
- `.github/prompts/recurring-issues-tracker.md` — per-root-cause strike
  counting, 3-strike escalation, Active/Accepted/Fixed lifecycle. This file
  is the strongest signal for which failure modes actually recur and deserve
  their own skill. Mine it.

### Direct scar sources — mine these for real failures
- `.claude/memory/feedback_*.md` — literal scars. Each one whose feedback has
  been re-violated is a candidate skill by itself. Examples known to exist:
  `feedback_deploy_requires_explicit_ask.md`, `feedback_settings_local_ask_mode.md`.
- `.claude/memory/MEMORY.md` — index of feedback.
- `knowledge/recent-mistakes.md`
- `knowledge/friction-log.md`
- `knowledge/post-mortems/` — every post-mortem is a candidate skill's
  justification.
- `retrospective/` — past reviews.
- Specific scars to check by name in git log or code:
  - **2026-04-22** dedup incident (41 duplicate JEs / $40k) — led to the
    DocNumber substring assert around `src/qbo/client.py:177–195`.
  - **2026-05-02** dedup incident (58 duplicates) — same failure class,
    different manifestation.
  - **Weekly-review agent lied about Gemini output** → issue creation moved
    OUT of the agent session and behind `validate_weekly_review.py`; see
    `.github/workflows/weekly-reviews.yml:1113–1224`. Built after #413/#433.
  - **Commit `abc8019`** — "recover marketplace + digest commits stranded by
    PR #467 early merge." A PR was merged before its review/recovery cycle
    completed.
  - **CS Slack channel missing** — #449 / #471, 5 CS tickets silently dropped
    despite env vars appearing wired; `check_cs_slack_no_channel_24h` DQ check
    now exists.

## Plan

**Phase 1 — Discovery.** Read the root `CLAUDE.md`, then every source in the
scar-tissue map. Batch reads. List every existing skill under `.claude/skills/`.
Produce (in your working messages, not in a file yet) a numbered list of
candidate skills. For each candidate:
- proposed name (kebab-case)
- one-sentence trigger description
- the SPECIFIC scar (issue #, commit hash, file:line, memory-file bullet,
  or post-mortem section) that justifies it
- which audit area(s) it addresses, if any
- whether it extends an existing skill or is net-new
Aim for 8–15 candidates. Drop any without a specific scar.

**Phase 2 — Authoring.** For each surviving candidate, before writing:
- read enough of the target code to verify every command, path, function
  name, DB column, and line number you'll cite
- draft the SKILL.md body
Then write `.claude/skills/<name>/SKILL.md`. Required sections in order:
1. YAML frontmatter (name, description).
2. **When to use** — 2–3 concrete trigger conditions (symptoms Claude will see).
3. **Steps** — imperative, copy-pasteable, verified.
4. **Verification** — how to know the skill worked (a command whose output
   confirms it, or a post-condition to check).
5. **When NOT to use** — with a sibling redirect ("use `<sibling>` instead").
6. **Origin** — 1–2 sentences citing the specific scar (issue #, commit, or
   memory file).
If you can't verify a specific command or path, either omit it or mark it
`CANDIDATE — verify before using` explicitly. Do not hallucinate a plausible
command.

**Phase 3 — Self-review.** Reread each SKILL.md against these tests:
- Does the `description` say WHEN to load, in concrete symptoms — not "what
  it does"?
- Is every command copy-pasteable and verified against a real source in the
  repo?
- Does "When NOT to use" name a real sibling skill (existing or one you
  authored in this session)?
- Does Origin cite a specific scar with a locator?
- Does the skill contradict any intentional decision in review-context.md?
If any test fails: fix it if you can, otherwise delete the skill and note
why in your final summary.

## Output
At the end, produce a summary in chat (not a file) with:
- N skills authored (list `<name>` — one-line each).
- N candidates dropped (with reason each).
- Skills you would have written that already exist (with `<name>`).
- Coverage map: which #470 / #473 / #474 / #475 open items each new skill
  addresses.
- Any real bugs or gaps you found while reading that need a skill but you
  couldn't justify from a specific scar — note as "candidate for next
  authorship pass," don't invent a scar.

## Session constraints
- Budget-aware. Read the specific files in the map. Do not explore the repo
  broadly. Batch reads.
- Do not touch anything outside `.claude/skills/`.
- Delegate mechanical work; keep judgment in this session. Your reasoning is
  the value — but knowing what NOT to think through is part of that judgment
  (Jesse Vincent, Claude Code team, via Simon Willison: *"Tell Fable to use
  other models for smaller tasks, applying its own judgement about which model
  to use"*).
  - Delegate to **Sonnet subagents**: batch reads of the scar-tissue map;
    git-log lookups for specific incidents; verifying that commands, paths,
    function names, DB columns, and line numbers exist exactly as cited;
    "does this candidate skill duplicate an existing one" checks.
  - Delegate to **Haiku subagents**: trivial mechanical checks (file-exists,
    line-count, directory listing, format normalization).
  - Keep in **this Fable loop**: which skills to author, sibling relationships,
    "When NOT to use" clauses, Origin scars, self-review, drop-candidate
    decisions, and the final coverage-map summary. Every judgment call.
  - Depth cap: 2 (this session → one subagent tier; no further nesting).
  - Team cap: ≤ 5 concurrent subagents. Shut each one down as soon as its
    structured return is in.
  - Require structured returns (JSON or terse markdown) — not free-form prose
    — so you can review each without re-reading the raw material.
  - Never delegate: authoring decisions, drop decisions, sibling relationships,
    or anything that writes into `.claude/skills/`.
- Do not invent capabilities Opus and Sonnet lack. Skills bridge process,
  not capability.
- Every claim carries a source and a date. No stats without evidence.
- Unproven claims are labeled `CANDIDATE`, not written as fact.
```
