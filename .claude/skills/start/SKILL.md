---
name: start
description: Session kickoff in best-practices — sync all three git refs, read the automation heartbeats (this repo's whole point is standing jobs), surface unreviewed [automated] commits from the last Friday run, scan concurrent sessions, then ask. Counterpart to /wrap-up.
user_invocable: true
---

# /start — Session Kickoff (best-practices)

Counterpart to `/wrap-up`. Wrap-up pushes state out and leaves all three refs matching;
/start pulls state in and checks that the standing automation is still alive.

**What makes this repo's kickoff different from the siblings':** in crumbl-ops and
wealth-mgmt, a checkout that is behind means a prior *session* left work behind. Here it
usually means the **Friday automation pushed** — `[automated]` knowledge files, practice-doc
edits and telemetry land on `origin/main` with no session involved. So being behind is the
normal weekly state, and the interesting question is not "did someone forget to push" but
**"did the automation run, and has anyone read what it wrote."** CLAUDE.md asks that the
`[automated]` practice commits be reviewed like any other diff; nobody does that at 6pm
Friday. This skill is where that debt surfaces.

## Step 0 (BLOCKING — worktree integrity guard)

Near-zero cost, prints nothing in the normal case. If the working directory is a
`.claude/worktrees/<name>/` path that is **empty** or a **phantom** (the dir exists but is NOT
registered in `git worktree list`, or has no `.git`), git resolves every Edit/Read/Bash to the
**main** checkout. In a repo that pushes straight to main, that means edits land on `main`
with no branch and no review. `git worktree list` is the authority — a file count is not
enough, because a phantom dir has files and still resolves to main.

```bash
WORKTREE_PWD="$(pwd)"
if [[ "$WORKTREE_PWD" == *".claude/worktrees/"* ]]; then
  wt_name="$(basename "$WORKTREE_PWD")"
  file_count="$(ls -A "$WORKTREE_PWD" 2>/dev/null | wc -l)"
  git worktree list --porcelain 2>/dev/null | grep -qF -- "/$wt_name" && reg=yes || reg=no
  if [[ "$file_count" == "0" ]]; then
    echo "WORKTREE IS EMPTY: $WORKTREE_PWD - edits resolve to main, not a branch."
  elif [[ "$reg" == "no" || ! -e "$WORKTREE_PWD/.git" ]]; then
    echo "PHANTOM WORKTREE: $WORKTREE_PWD - matches a worktree path but is NOT registered in git worktree list; git resolves it to MAIN."
  fi
fi
```

If either fires: stop, surface it first, and ask whether to re-create the worktree or proceed
on `main` knowingly. Do not continue until Michael picks. (Pattern from crumbl-ops `/start`.)

## Step 1 — Sync all three refs (live, always)

`/wrap-up` step 1 verifies worktree = origin/main = main checkout. /start re-establishes it,
because the Friday run moves `origin/main` and the main checkout independently of any session.

```bash
git fetch origin
git status --short --branch
git rev-parse --short HEAD
git rev-parse --short origin/main
git -C C:/Users/micha/best-practices rev-parse --short HEAD
git -C C:/Users/micha/best-practices status --short
```

- **Behind + clean tree** → fast-forward, mention it ("pulled N commits").
- **Behind + dirty** → warning block at the top: list the files, ask "commit, stash, or
  leave?" before pulling. Withhold the focus prompt until it is resolved. A prior session
  likely left these; treat as this session's first task. (Untracked files never block a pull;
  just report them.)
- **Ahead** → a prior session pushed nothing. Surface `git log origin/main..HEAD --oneline`
  and offer to push per `/wrap-up` step 1.
- **Main checkout behind or dirty** → say so. The weekly automation assumes a clean main
  checkout, and a dirty one is either a scheduled run that died mid-commit or a session step
  that resolved an absolute path and wrote there.
- **Never use bare `git stash` / `git stash pop`.** The stash stack is shared across every
  worktree and other sessions pop it. Prefer a WIP commit; if you must stash, use
  `git stash push -u -m "<tag>"`, capture the SHA, and `apply` it by SHA.

Silent cleanup: `git worktree prune`. Mention only if something was cleaned.

## Step 2 — Automation health (the repo-specific half)

This repo *is* the estate's automation registry (`AUTOMATION.md`, one row per standing job).
A session that starts without knowing whether those jobs are alive is the exact failure the
registry exists to prevent.

**a. Heartbeats — run from the MAIN CHECKOUT, not from a worktree:**

```bash
python C:/Users/micha/best-practices/scripts/check_heartbeats.py --no-issue
```

**The path matters and the failure is silent.** `data/feed_archive/` is gitignored, so it does
not exist in a fresh worktree. Run from a worktree, the check reports the repo's primary job as
`CC-WeeklyDigest  PENDING  no state yet (never run?)` — byte-identical to a job that genuinely
never ran. From the main checkout the same check reads `OK, 3.8d ago` (verified 2026-09-09).
Use `--no-issue`: /start reads the tell, it does not file the issue — `CC-Heartbeats` (Tue 9am)
owns that.

Report only non-OK rows. `PENDING` from the main checkout is real (a job before its first run);
`PENDING` from a worktree is an artifact — re-run at the correct path rather than reporting it.

**b. Unreviewed `[automated]` commits** — the debt this skill exists to surface:

```bash
git log --format='%h %s' --since='8 days ago' origin/main | grep -F '[automated]'
```

**Filter on the subject, not `--grep`.** `git log --grep='[automated]'` searches the whole
commit message, so a hand commit whose *body* discusses automated commits matches and inflates
the count — `ead3cf0` does exactly that, and `-F` does not help because the body genuinely
contains the string. Piping `%s` through `grep -F` is the honest count (verified 2026-09-09:
4 automated commits, not the 5 `--grep` reported).

If any landed since the last session, name them and offer to diff the practice-doc ones.
`digest/practice_updater.py` auto-edits living docs in place; its structural validator only
proves the file still has its H1 and required anchors, not that the edit was any good. Most
weeks change nothing — a week that changed something is worth ten seconds.

**c. Digest inbox** — one-off inputs waiting for Friday (gitignored, so main-checkout path):

```bash
ls -1 C:/Users/micha/best-practices/data/digest_inbox/*.md 2>/dev/null | wc -l
```

Non-zero → one line: "N inbox item(s) queued for Friday's run."

**d. Calendar awareness.** Say what fires next, from `AUTOMATION.md`, without extra calls:
Fri 6pm ET digest → Mon 8am skills-sync → Tue 9am heartbeats → 1st backward-pass → 10th
thesis-check → 15th and 22nd review types. A Friday-afternoon session should hear "digest fires
tonight"; a weekend session should hear "last night's run is unreviewed."

## Step 3 — Concurrent-session scan (non-blocking)

Five or more sessions run in parallel here and cross-repo findings go stale in minutes. Two
sources — run both, they disagree in both directions:

- `mcp__ccd_session_mgmt__list_sessions(limit: 15)` — titles, PR state, `lastActivityAt`.
  Usually a *deferred* tool: load it first with
  `ToolSearch(query: "select:mcp__ccd_session_mgmt__list_sessions")` or the call fails with
  `InputValidationError`. If the harness lacks it, fall back to `git worktree list` alone and
  say the session-title half is missing — do not silently drop the section.
- `git worktree list` — authoritative for which branch each tree is actually on (a session
  record's `branch` goes stale the moment that session switches branches), and the only view
  of trees with no session record.

**Live = `isRunning: true` OR `lastActivityAt` within ~2h.** Never `isRunning` alone — it goes
false between turns, so a session Michael is typing in reads `false`.

Report one line per live session, plus any sibling worktree with unmerged commits. With none
live, say "No other live sessions" in those words — silence reads as unchecked.

Then flag only the collision rules that intersect what Michael picks up:

- **Direct-to-main pushes.** This repo lands work with `git push origin HEAD:main`, so two
  sessions pushing collide for real. A non-fast-forward rejection is the tell; the fix is fetch
  and rebase, never force.
- **Same practice doc as a live session, or as Friday's updater.** `practice_updater` rewrites
  whole docs; a hand edit landing the same week is the one that loses.
- **`MEMORY.md` index writes.** Two sessions appending to the same index conflict, and the
  memory repo at `~/.claude/projects` is shared by every repo on this machine.
- **A stale worktree whose commits already landed.** Judge by the PR record or ancestry, not by
  `rev-list --count`: after a squash merge, ancestry, patch-id and content diff can all read a
  landed branch as unmerged. Match with `awk`, not `grep -P` — this locale kills `grep -P`, and
  every branch then silently reads "no PR", which looks identical to "safe to delete".

## Step 4 — Memory and open items (batch with step 2)

- `MEMORY.md` auto-loads into the system prompt every session. **Do not re-read it.** Fetch
  individual memory files lazily, only when their topic comes up.
- Open issues in this repo — mostly auto-filed feed candidates awaiting a human decision:
  ```bash
  gh issue list -R michaeladickson/best-practices --state open --limit 15 --json number,title --jq '.[] | "\(.number) \(.title)"'
  ```
  Summarize by class ("6 feed-candidate issues, 1 other"), not one line each. A feed candidate
  is approved by editing `digest/config/feeds.yaml` by hand — never auto-add one.

## Briefing

Order:

1. **Blocking** — worktree integrity (step 0) or a dirty tree (step 1). Withhold the focus
   prompt until resolved or acknowledged.
2. **Git** — one line: `worktree = origin/main = main checkout at <sha>`, or what drifted and
   what you did about it.
3. **Automation** — non-OK heartbeats; `[automated]` commits landed since the last session;
   inbox count; what fires next. If everything is healthy and nothing landed, one line:
   "Automation green, nothing new since <date>."
4. **Concurrent sessions** — one line each, or "No other live sessions."
5. **Open items** — issue counts by class.
6. Then ask: **What do you want to pick up?**

## Lazy-load on focus

- A practice or convention → `practices/INDEX.md` routes; read only the one doc.
- Digest internals → `digest/ai_digest.py`, `digest/practice_updater.py`, and the configs under
  `digest/config/`.
- Anything scheduled → `AUTOMATION.md` first (cadence, freshness tell, kill criteria, rebuild
  steps). Read it before adding, changing, or diagnosing any scheduled work.
- Review prompts or workflow → `reviews/README.md` is the router; `workflow-template.yml` is
  ground truth.
- Past learning → `knowledge/INDEX.md`.

## Deliberately skipped

No PROJECT_STATUS (this repo is a catalog, not a delivery tracker — see `/wrap-up`), no sprint,
no dev services, no email triage, no `practices/INDEX.md` preload, no skills list (already in
the system prompt).

## Context rules (best-practices specific)

- **Public repo.** Mechanisms live here; personal content does not. "This needs
  de-identification" is the tell that it belongs in command-center instead — voice content
  especially.
- **Secrets** come from GCP Secret Manager at runtime. There is no `.env` here and there should
  never be one.
- **A zero-result run and a genuinely quiet week produce the same output.** Any change that
  narrows what a step reads — a filter, a glob, an anchor, a keyword prefilter — buys a stretch
  of silence that proves nothing. Verify it by hand once, while you still know what you changed.
