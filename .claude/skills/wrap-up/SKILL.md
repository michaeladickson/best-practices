---
name: wrap-up
description: End-of-session in best-practices — verify all three git refs (worktree, origin/main, main checkout) match; trace cross-repo tangents (issues filed in crumbl-ops / command-center / wealth-mgmt, prompts handed off); flag digest-pipeline watch-items for Friday's run; capture any draft-edit voice deltas as feedback_voice_* memories for the monthly command-center /voice-sync; save any genuinely-surprising insight to cross-session memory; present a terse summary. No parking, no PROJECT_STATUS — this repo is a catalog, not a delivery tracker.
user_invocable: true
---

# /wrap-up — End-of-Session (best-practices)

Best-practices is a docs + digest catalog, not a delivery repo — sessions are usually terminal (build a doc, ship a feature, run an assessment) rather than multi-day. This is the whole ritual; there is no `/wrap-up-eod` variant like crumbl-ops has.

Run in order. Terse bullets in the summary; don't ask permission for git or memory steps that surface obvious candidates.

## Steps

### 1. Verify clean git state (REQUIRED — don't skip, don't ask)

The direct-to-main pattern this repo uses means every push in the session should already have synced. Confirm it did:

```bash
git status --short
git rev-parse --short HEAD
git rev-parse --short origin/main
git -C C:/Users/micha/best-practices rev-parse --short HEAD
git -C C:/Users/micha/best-practices status --short
```

Handle any drift:
- **Uncommitted changes in the worktree** → commit + push using the one-shot identity override + `Co-Authored-By` footer pattern this repo uses. Never leave the session with a dirty tree.
- **Worktree ahead of origin/main** → `git push origin HEAD:main`.
- **Main checkout behind origin/main** → `git -C C:/Users/micha/best-practices merge --ff-only origin/main`.
- **Worktree diverged from origin/main** → do NOT force-push. Fetch, rebase onto origin/main, resolve any conflicts (usually trivial — this session's edits vs. the weekly `[automated]` commits from the scheduled Friday runs), push. Match the pattern the session already used. And judge "diverged" by **content, not count**: after a squash-merged PR, `rev-list --count` reports commits that already landed (squash breaks ancestry) — `git diff origin/main` decides whether anything is actually unlanded (both crumbl-ops and command-center carry this scar).
- **Main checkout dirty** → don't wrap past it: a session step that resolved an absolute path wrote there while this worktree stayed clean (command-center scar, 2026-08-01), or a scheduled Friday run died mid-commit. Commit it via the normal pattern or clean it — the weekly automation assumes a clean main checkout.
- **Stray temp files** — check for `_tmp_*`, `*.bak`, or scratchpad artifacts that shouldn't be tracked and remove them.

Do not proceed past this step until all three refs match and the working tree is clean.

### 2. Trace cross-repo tangents

Sessions here often file issues or hand off artifacts to other repos. Note in the summary:

- **GH issues filed** in `michaeladickson/crumbl-ops`, `command-center`, or `wealth-mgmt` — link by number so there's a trail (`gh issue view <n> -R michaeladickson/<repo>` if uncertain).
- **Commits pushed to another repo** — rare from a best-practices session, but possible (e.g., `feedback_*.md` memory files on the crumbl-ops side, or a `decisions/` entry).
- **Prompts or docs handed off** for use elsewhere — e.g., a Fable prompt authored here meant to be pasted into a crumbl-ops session. Name the file path so the user can find it Monday.

### 3. Flag digest-pipeline watch-items

The weekly digest + `practice_updater` runs Friday 6pm ET via the `CC-WeeklyDigest` Windows Task Scheduler task. If this session changed anything the next run will exercise, name it in the summary — the goal is a short "look at this on Saturday" list, not a full changelog.

- **New practice doc registered** in `digest/config/practice-docs.yaml` → *"first `practice_updater` run against this doc will be Friday; skim the auto-commit."*
- **`digest/practice_updater.py` edits** (extract/integrate prompts, `_validate` rules) → *"monitor the first affected doc's diff for the failure mode you were defending against."*
- **New feed** in `digest/config/feeds.yaml` → *"starts feeding Friday; expect first candidates from &lt;source&gt; the following week."*
- **`scripts/run_weekly_digest.sh` changed** → *"next run exercises the change; check the Task Scheduler log."*
- **`.github/workflows/weekly-digests.yml` changed** → *"manual-dispatch fallback affected — the local runner is untouched."*
- **Any workflow or `reviews/*.yml` template changed** → dispatch it once before wrapping (`gh workflow run …`) or name why not. GitHub treats unparseable workflow YAML as *trigger-less with no error* — the tell is the API showing the file path as the workflow name. The push-time validator gates parse errors; only a dispatch proves end-to-end (2026-07-26: the freshness dead-man's-switch shipped dead and only a manual dispatch caught it).
- **A practice doc within ~10% of the 70KB cap** → *"consolidation pass due before the updater starts skipping it (`at_capacity:consolidate`)."*
- **A doc's keyword prefilter, scope, or required anchors narrowed** in `digest/config/practice-docs.yaml` → *"a prefilter that now matches nothing produces a clean run and no commit — byte-identical to the quiet week this pipeline has most weeks."* Prove it still reaches the doc with `python -m digest.practice_updater --dry-run` before wrapping; don't wait on a Friday silence you can't read.

The shape behind that last one is worth carrying into every item above: **a zero-result run and a genuinely quiet week produce the same output.** The failure guards don't help, because they cover the *unreachable* case — a successful call that returns nothing is not distinguishable from a real empty set. Any change that narrows what a step reads (a filter, a label, a roster, a glob, an anchor) buys a stretch of silence that proves nothing, so verify it once by hand while you still know what you changed.

Do NOT invent watch-items. If the session didn't change any of these areas, say *"no digest-pipeline watch-items."*

### 3b. Automation-parity check (only if the session touched scheduled automation)

Two invariants from the 2026-07-26 audit — confirm both for anything scheduled this session touched:

- **Recovery parity** — the register script (`scripts/register_*.ps1`) must produce the same trigger as the live Task Scheduler entry. Drift here means a machine rebuild silently restores the wrong schedule (the Sunday-vs-Friday class).
- **Evidence of work** — a run that exits 0 without producing its artifact must be *detectable* (freshness workflow, output-delta guard, health-check artifact map). "Scheduler says success" is not evidence; the usage scanner logged "Done" for four weeks while processing zero files.

### 4. Voice harvest (only if the session drafted prose to be sent as Michael)

If this session drafted anything meant to go out as Michael (email, letter, briefing,
update, text, post) and he edited, corrected, or rewrote it (in chat, by pasting back his
version, or by editing the draft file), capture the style deltas for the master voice
memory:

1. Diff Claude's last version against his final one. Ignore factual/content edits; keep
   style deltas: cuts, word choice, greeting/sign-off, structure, punctuation, register.
2. Write one capture per distinct delta to THIS project's memory directory
   (`C:\Users\micha\.claude\projects\C--Users-micha-best-practices\memory\`):
   `feedback_voice_<slug>.md`, standard memory frontmatter (`metadata.type: feedback`).
   Body: the rule, his words (one line), one before/after pair. Add the MEMORY.md index
   line.
3. Do NOT edit the master voice memory directly (command-center
   `knowledge/voice/master.md`). Capture locally, reconcile centrally: the monthly
   `/voice-sync` task in command-center sweeps `feedback_voice_*` captures from every
   project's memory into the master with dedup and contradiction checks. Pattern spec:
   `practices/writing/voice-memory.md`.
4. Note it in the summary ("voice: N deltas captured" or "voice: nothing to harvest").

An unedited draft he explicitly approved can be captured as a confirming example; mere
non-edits are not signal.

**Portability (skills-sync):** this step is a portable mechanism; every repo's wrap-up
should carry it, each writing to its own project memory directory. Only the memory-dir
path changes per repo.

### 5. Cross-session memory (only if something surprising surfaced)

If — and only if — the session surfaced a genuinely non-obvious insight about *how this repo works* (a subtle constraint, a recurring gotcha, a user preference the session confirmed for the first time), save it as its own memory file at `C:\Users\micha\.claude\projects\C--Users-micha-best-practices\memory\` following the standard frontmatter format (`name`, `description`, `metadata.type`), and add a one-line entry to `MEMORY.md` in that directory.

Skip by default. Save memory only for insights that would surprise a fresh reader of the repo — never for anything derivable from the code, git log, or existing docs. Match the anti-fragmentation stance in `practices/claude-code/context-memory-management.md`.

### 5b. Push the memory repo (REQUIRED — a different repo from this one)

Steps 4 and 5 write into `C:\Users\micha\.claude\projects\`, which is its own private git
repo, version-controlled in place so recall paths are unchanged. Step 1 verifies *this* repo's
three refs and never looks at it. Skip this and the session's memory exists only on this
machine, while the backup ages silently and still reads as healthy.

```bash
git -C /c/Users/micha/.claude/projects status --porcelain
```

If dirty: `add -A`, commit naming what changed (`memory: <what>`), push.

- **`add -A` is correct there specifically.** That repo's `.gitignore` ignores everything and
  re-admits `*/memory/**` plus its own root files, so `-A` cannot reach the session
  transcripts sharing the directory. If it ever stages a path outside `memory/`, stop and fix
  the allowlist rather than committing.
- **It spans every project on this machine, not just this one.** Commit all of it from here —
  a session in another repo writes memory too, and one commit beats a file left behind. Do
  not narrow it to the best-practices slug.
- **It is private and stays private.** It carries memory from repos that are not public.
  Never mirror any of it into this repo, and never make that repo public.
- Single-branch backup repo: commit straight to its `main`. No PR, no landing rules.

**Portability (skills-sync):** portable mechanism; every repo's wrap-up should carry it. Only
the project's own memory-directory path and the step numbering change.

### 6. Present the summary

Terse bullets, in this shape:

```
Wrapped YYYY-MM-DD.

Shipped:
- <sha> <one-line commit message>
- <sha> <one-line commit message>
- ...

Cross-repo:
- Filed <repo>#<num> — <one-line>
- Handed off <path> for use in <repo>
- (or "none")

Watch next Friday's digest for:
- <doc/feature> — <why>
- (or "no digest-pipeline watch-items")

Voice:
- captured <n> deltas as feedback_voice_* memories: <one-line each>  (or "nothing to harvest")

Memory saved:
- <slug>: <one-line>  (or "none — nothing surprising")

Memory repo:
- pushed <sha> — <one-line>  (or "clean — nothing to push")

Git: worktree = origin/main = main checkout at <sha>. Working tree clean.
```

## Rules
- Step 1 is required, not optional — a session that leaves any of the three refs out of sync is unfinished.
- Steps 2–3 are enumeration, not judgment: name what happened; don't editorialize.
- Step 4 fires only on actual draft edits. No outbound prose, one line ("voice: nothing to harvest"), move on. Captures are private project memory; the public repo never carries voice content, only this mechanism.
- Step 5b is required whenever step 4 or 5 wrote a file, and costs one `status` call when they didn't.
- Skip step 5 by default. The bar for a memory save is "would surprise a fresh reader"; anything less belongs in a doc or a commit message.
- Bullet points over paragraphs — terse wins.
- No emojis unless the user has explicitly asked for them.
