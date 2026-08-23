---
name: backward-pass
description: Train a repo's project-level CLAUDE.md against recent session transcripts. Reviews what agents actually did (rules followed, violated, or re-derived), scores each addressable unit of the file, and proposes at most 5 gated edits — 2-session evidence minimum, verbatim quotes, token budget respected, skills as the release valve. Human reviews every edit before anything is written. Run monthly per active repo, or on demand ("run a backward pass on crumbl-ops").
user_invocable: true
---

# /backward-pass — Train a project CLAUDE.md on real sessions

The always-loaded `CLAUDE.md` is the weights; every session is a forward pass; this skill
is the backward pass. Method and rationale live in
[`practices/claude-code/context-memory-management.md`](../../../practices/claude-code/context-memory-management.md)
("Training the Always-Loaded File"). This skill exists so the loop runs with Claude reading
the transcripts directly — never a third-party tool, because local transcript stores mix
public- and private-repo material.

**Scope guard:** this trains **project-level** `CLAUDE.md` files only. Never propose edits
to `~/.claude/CLAUDE.md` (user-level, hand-written) or to voice content (owned by
command-center `/voice-sync`).

## Arguments

- Optional repo name: `best-practices` (default: the current repo), `crumbl-ops`,
  `command-center`, `wealth-mgmt`.
- Optional window: `--since 30d` (default). Shorter windows rarely clear the 2-session bar.

## Steps

### 1. Locate the inputs

- Target file: the repo's root `CLAUDE.md` (note per-module `CLAUDE.md` files exist but are
  load-on-demand; only audit them if the transcripts show one misleading an agent).
- Transcripts: `~/.claude/projects/<encoded-repo-path>/*.jsonl`, filtered to the window by
  file mtime. The encoding replaces path separators and colons with `-`
  (e.g. `C--Users-micha-crumbl-ops`). Skip trivial sessions (< ~10 turns).
- Count the target file's tokens (estimate: bytes / 4). Budget: **5,000 tokens** unless the
  repo's CLAUDE.md header declares another.

### 2. Distill each transcript (no judgment yet)

For each session, extract only: what the user asked, what the agent concluded or delivered,
each user correction or redirect, and any fact the agent had to re-derive (schema spelunking,
rediscovering a build command, re-asking something the file should have answered). Ignore
tool-call noise. Keep a verbatim quote for anything that will become evidence.

### 3. Score every addressable unit

Treat each list item / paragraph / heading-block of the target `CLAUDE.md` as a unit. For
each unit tally across sessions: **helped** (visibly steered behavior), **violated**
(agent did the opposite), **wrong** (rule itself is stale/incorrect), **irrelevant**
(never mattered). Then the inverse: cluster the gaps — things agents got wrong or
re-derived that **no unit covers**.

### 3b. Skill-usage tally (rides along, costs nothing extra)

While reading the transcripts, count Skill invocations against the repo's
`.claude/skills/` inventory. **Count BOTH logging forms** — user-typed slash commands
log as `<command-name>/<name></command-name>`, model-initiated calls as
`"skill":"<name>"`; counting only the second concluded /start was never used when it
had 61 invocations (2026-08-23 audit bug). Report per skill: invocations this window,
and consecutive windows at zero (tracked in the state file). A skill at zero for 3+
windows is a deletion/merge candidate *unless* its cadence is longer than the window
(monthly close, quarterly rituals) or it's invoked by scheduled/headless jobs — check
both before proposing. Skill deletions count toward the ≤5 edit budget like any other
edit. (Corrected 2026-08-23 baseline: the only genuinely dormant skills are
wealth-mgmt's analysis set (analyze-earnings, thesis-check), command-center voice-sync,
and crumbl-ops financials/payroll-import — the latter possibly headless now.)

### 4. Propose edits — the gates are hard

- **At most 5 edits** per pass: add / remove / rewrite / extract-to-skill.
- **A new rule needs evidence from ≥2 independent sessions.** One incident is noise.
- **Every edit carries a verbatim transcript quote** as its evidence. No quote, no edit.
- **Post-edit file must fit the budget.** At or near budget, every addition names the
  removal or extraction that pays for it.
- **Broad/narrow triage:** relevant in ≥~20% of sessions or safety-critical → stays in the
  file. Narrow with a detectable trigger → propose extraction to a skill. Narrow with no
  trigger → propose deletion.
- Check rejections: if `~/.claude/backward-pass/<repo>.json` records a previously rejected
  edit, don't re-propose it without new evidence.

### 5. Present for review — nothing writes before approval

Show a table: edit, type, evidence quote(s) + session count, token delta (measured from the
actual text). The user accepts or rejects each edit individually. Apply only accepted edits.
Record rejections (edit summary + date) in `~/.claude/backward-pass/<repo>.json` so they
don't return; record `last_run` there too (dead-man's tell: if it's much older than the
intended cadence, the loop has stopped).

For a non-best-practices target repo, make the edits in that repo's checkout on a branch
and open a PR (never push to main of another repo); for best-practices itself, commit
directly per this repo's convention.

## Scheduled (non-interactive) mode

The `monthly-backward-pass` scheduled task runs this skill headlessly on the 1st of each
month for all four repos (best-practices, crumbl-ops, command-center, wealth-mgmt). In that
mode, **stop after step 4**: write each repo's proposal table (edits, evidence quotes,
session counts, token deltas) to `~/.claude/backward-pass/proposals-<repo>.md`, update
`last_run` in the state file, and end. Never apply edits, commit, or open PRs from a
scheduled run. The user reviews by opening a normal session and saying
"review the backward-pass proposals" — that resumes at step 5 using the saved proposal
files, and deletes each proposals file once its edits are accepted/rejected.

If a proposals file from a previous month still exists unreviewed, the scheduled run
regenerates it fresh (stale proposals age poorly) and notes the skipped review.

The task lives in app storage, not git — to rebuild it on a new machine, recreate a
monthly scheduled task pointing at this SKILL.md (same dead-man's tell as skills-sync:
`last_run` in `~/.claude/backward-pass/*.json` much older than a month means it stopped
firing).

## What this skill never does

- Run `npx backpass` or any third-party tool over transcript stores.
- Rewrite the whole file ("large step = starting over").
- Touch user-level CLAUDE.md, voice files, or another repo's main branch.
- Write anything the user hasn't individually approved.
