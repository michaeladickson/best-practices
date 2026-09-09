---
name: judgment-sync
description: Promote portable judgment out of a single repo's memory store into the shared namespace every repo reads, and repair everything the move breaks. Selection is by content, never by filename or type. Enforces the referrer scan BEFORE the move, link-level index surgery, cross-store wikilink annotation, and an integrity gate. Run on demand after a repo accumulates behavioral memory, or when a rule is found to have been learned twice.
user_invocable: true
---

# /judgment-sync — Promote Portable Judgment to the Shared Store

Behavioral memory is captured in whichever repo the work happened in, and a `[[link]]`-free
slug resolves only inside the store holding the file. So a rule learned once is invisible
from every other repo, and the second repo pays to learn it again. That is not hypothetical:
two rules were re-learned independently, in a second repo, weeks after the first repo wrote
them down — a truncated read reported as an absence, and a structured edit anchored on a
substring. Both had been written down. Neither was reachable.

This skill moves that class of memory into one canonical copy and repairs the wreckage a
move leaves behind. The move itself is five minutes; the repair is the skill.

Counterpart to `/skills-sync`, which propagates *skills*. Machine-bound by design: local
checkouts, local `gh` auth, absolute `git -C` paths — never assume a cwd.

## Stores

| Store | Path | Role |
|---|---|---|
| per-repo | `C:/Users/micha/.claude/projects/C--Users-micha-<repo>/memory/` | repo-specific domain facts |
| shared | `C:/Users/micha/.claude/projects/_shared/memory/` | one canonical copy of portable judgment |

`_shared/memory/` lives **inside** the memory repo on purpose. That repo's `.gitignore`
ignores everything and re-admits `*/memory/**`, so a sibling directory gets version control
and backup for free. A path outside it (`~/.claude/memory-shared/`) looks equivalent and is
never backed up — verify with `git status`, not by reading the ignore file.

## Selection — by content, never by name or type

Both cheap proxies have been measured wrong:

- **Filename prefix** (`feedback_*`) misses memories typed feedback but named `pattern_*`,
  `project_*` or bare. A pass built on it skipped a large majority of one repo's portable
  rules, including the two that were re-learned elsewhere.
- **The `type:` field** misclassifies in the other direction: durable behavioral rules get
  filed as `project` or `reference`, and genuine domain facts get filed as `feedback`.

Read the `description:` of every candidate and the body of anything you would move. The test
is one question:

> **Would this rule fire in a repo containing none of this repo's code?**

Promote only on a clear yes. A wrongly promoted repo-specific rule pollutes every repo's
index forever; a missed promotion merely preserves the status quo. When genuinely torn,
leave it and say so in the summary.

**Never promote:** domain facts (a schema, a vendor's format, an API's quirks), project
status snapshots, anything naming a person or a deal, or voice memories — those belong to
`/voice-sync` and have their own pipeline.

## Procedure

### 1. Build the manifest

One TSV, `<tier>\t<repo>\t<name>`, so the run is reviewable and re-runnable. Validate every
path resolves and no destination collides **before** moving anything.

### 2. Staleness gate (BLOCKING)

Two distinct checks, and the naive one over-flags:

- **Marker convention** is `SUPERSEDED <date>:` leading the description or body. A bare
  keyword scan hits narrative prose ("the file being retired") and migration names
  (`214_deactivate_superseded_*`) — those are false positives, cleared by reading them.
- **Self-flagged decay.** A memory whose own body says it will go stale ("this is dated and
  will go stale once …") is a time-limited constraint. Promoting one pushes a lapsed rule
  into every repo, which is worse than leaving it. Leave it and flag it for expiry.

### 3. Referrer scan — BEFORE the move, not after (BLOCKING)

**This is the step the skill exists to enforce.** Every promotion silently breaks referrers,
and nothing else catches it. Scan all four repos:

```bash
awk -F'\t' '{print $3".md"}' <manifest> > /tmp/promoted.txt
for r in crumbl-ops command-center wealth-mgmt best-practices; do
  for sub in .claude/skills .claude/hooks .claude/agents .claude/commands CLAUDE.md; do
    p="/c/Users/micha/$r/$sub"; [ -e "$p" ] || continue
    grep -rn -F -f /tmp/promoted.txt "$p" 2>/dev/null | grep -v '/worktrees/'
  done
done
```

Two reference forms exist and both break:

```
absolute   .../C--Users-micha-<repo>/memory/feedback_X.md  ->  .../_shared/memory/feedback_X.md
bare cite  `feedback_X.md`                                 ->  `_shared/feedback_X.md`
```

The absolute form hard-fails on read. The bare cite is the quieter failure: it sends the
session looking in a directory that no longer holds the file. Rewrite both with one regex
whose path prefix is optional, so a bare replace cannot double-prefix a path the same pass
already rewrote.

Scope the rewrite to `.claude/skills`, `.claude/hooks`, `.claude/agents` and `CLAUDE.md`.
A recursive glob over `.claude/` also reaches the in-repo `memory/` snapshot some repos
carry; partially updating a stale mirror is worse than leaving it wholly stale.

### 4. Move, then repair the indexes

`git mv` into `_shared/memory/`. Then:

**Origin index — link-level surgery, never line-level.** Index lines carry two or three
links each:

```
- [Worktree vs main](a.md) / [Verify schema names](b.md) — information_schema FIRST
```

Dropping that line because it mentions a promoted memory orphans one that is staying. Remove
only the promoted `[label](file.md)` spans, rebuild from the survivors, and drop the line
only when nothing survives. Keep a trailing `— note`, but anchor it **after the last link**:
a note sitting mid-line belongs to the link it follows, and a greedy match from the first em
dash swallows every later link.

**Shared index — insert under the existing heading. Never regenerate.** Regenerating from a
manifest erases every earlier pass's entries and annotations.

**Expect a fifth of promoted memories to have no index entry at all.** They exist with no
router, so recall could not reach them from inside their own repo either. Add them; do not
treat their absence as a sign they were unimportant.

### 5. Annotate cross-store wikilinks

A `[[slug]]` carries no path, so every link crossing the new boundary needs its store:
`[[x]]` becomes `[[x]] (_shared)`.

Resolution requires normalizing first, or the audit reports live memories as dangling.
Filenames and frontmatter `name:` values mix `feedback_a_b`, `feedback-a-b` and `a-b`, while
links are usually written bare and hyphenated. Lowercase, hyphens to underscores, strip a
leading `feedback_`/`pattern_`/`reference_`/`project_`, then compare.

Classify and act:

| Class | Action |
|---|---|
| same-store | leave |
| cross-store | annotate with the target's store |
| **skill-ref** — names a `.claude/skills/<name>` | **leave**; annotating a skill as a memory is wrong |
| ambiguous, `_shared` among candidates | `_shared` wins: the link was authored against the copy that moved |
| dangling | **leave**; a forward reference is legal, and a move cannot create one — nothing was deleted |

Substitute per **occurrence**, not per file: a whole-file guard skips every instance whenever
any one of them already carries a gloss. A negative lookahead (`\[\[x\]\](?!\s*\()`) is both
correct and idempotent, since an applied `(store)` is itself a paren.

### 6. Integrity gate — all must pass

- Every link in every index resolves to an existing file.
- No promoted file is still referenced by an origin index.
- No path double-prefixed (`_shared/_shared/`). **Check path shape, not basename existence** —
  a basename check passes no matter how mangled the path is, which is how a `_shared/_shared/`
  run once reported clean.
- Re-running the annotator reports zero cross-store links and makes zero edits.
- Every referrer from step 3 resolves.

### 7. Land it

- Memory repo: `git -C C:/Users/micha/.claude/projects add -A`, commit, push. `-A` is safe
  there — the allowlist cannot reach session transcripts. If it ever stages a path outside a
  `memory/` tree, stop and fix the allowlist.
- Referrer repairs: one PR per affected repo, in a dedicated worktree off `origin/main`.
  Those repos land via PR; only best-practices pushes to main directly.
- Duplicate pairs (the same rule written independently in two repos): cross-link them in the
  shared index under *Duplicate pairs pending merge*. **Do not auto-merge** — merging is
  editorial and belongs in review.

## Tooling traps this procedure has already paid for

- **Write scripts to a file; do not build them in a heredoc.** A quoted heredoc through the
  Bash tool still collapses `\\` to `\`, which has put literal `CR` bytes into an index.
- **Read and write bytes** for any edit that must preserve line endings. Python's
  `write_text` normalizes to `os.linesep` and rewrote whole files as CRLF.
- **`grep` cannot detect CR** here. It returns 0 on a genuine CRLF file, and mis-quoted
  inside `"$(...)"` it matches every line. Use `file`, or `tr -dc '\r' | wc -c`.
- **`sys.stdout.reconfigure(encoding="utf-8")`** at the top of every script, or an em dash or
  arrow in a description kills the run on a cp1252 console.
- **Loop in Python, not bash.** A per-file `grep`/`sed` loop over a few hundred memories times
  out; the same work in one Python process is instant.

## Cadence

On demand. A standing schedule would accrue a backlog between runs, and the cheaper place for
the ongoing case is capture time: when `/wrap-up` writes a `feedback_*` memory, ask whether it
is repo-specific before choosing its store. Run this skill when a repo has accumulated
behavioral memory, when a rule is found to have been learned twice, or after a backfill in a
repo that has never been swept.

Not registered in `AUTOMATION.md` — that registry is for scheduled jobs, and a job with no
cadence has no freshness signal to check.
