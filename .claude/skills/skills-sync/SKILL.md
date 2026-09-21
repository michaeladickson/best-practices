---
name: skills-sync
description: Weekly cross-repo scan of Claude skill changes across best-practices, crumbl-ops, command-center, and wealth-mgmt. Detects .claude/skills/ commits since the last run, judges which changes are portable patterns vs repo-specific content, and opens one adapted [skills-sync] PR per target repo. Run weekly by the weekly-skills-sync scheduled task, or manually anytime.
user-invocable: true
---

# /skills-sync — Cross-Repo Skills Sync

Skills evolve inside whichever repo the work happened in, and the improvements never travel — wealth-mgmt's `/wrap-up` was a hand-port from command-center, and the worktree-cleanup guard that ate an active session (crumbl-ops#747) had to be re-learned before it reached command-center. This skill is the weekly propagation pass: scan what changed, judge what generalizes, port the *idea* (never the raw text) into each sibling repo as a reviewable PR.

Machine-bound by design (like the weekly digest): it uses the local checkouts and local `gh` auth. All commands use absolute `git -C` paths — never assume a cwd.

## Sync set

| Repo | Local checkout | GitHub | Default branch |
|---|---|---|---|
| best-practices | `C:/Users/micha/best-practices` | `michaeladickson/best-practices` | main |
| crumbl-ops | `C:/Users/micha/crumbl-ops` | `michaeladickson/crumbl-ops` | main |
| command-center | `C:/Users/micha/command-center` | `michaeladickson/command-center` | main |
| wealth-mgmt | `C:/Users/micha/wealth-mgmt` | `michaeladickson/wealth-mgmt` | main |

Every repo is both a source and a target. Scope is `.claude/skills/**` only (extend deliberately if a repo starts keeping portable logic in `.claude/agents/` or `.claude/rules/`).

**Hard rule: never touch the local working trees.** Checkouts are routinely mid-work on feature branches (crumbl-ops usually is). Only ever `git fetch`, read from `origin/main` (`git show`, `git diff A..B`), and build edits in throwaway worktrees under `~/.claude/skills-sync/worktrees/`.

## State

`C:/Users/micha/.claude/skills-sync/state.json`:

```json
{
  "last_run": "YYYY-MM-DD",
  "repos": { "best-practices": "<sha>", "crumbl-ops": "<sha>", "command-center": "<sha>", "wealth-mgmt": "<sha>" }
}
```

- Each SHA is the `origin/main` commit the repo was last scanned through.
- **File missing (first run):** use a 14-day window instead (`git log --since="14 days ago"`), then write current SHAs.
- **Advance rule:** a source repo's SHA advances only when its changes were assessed against *all three* targets (ported, rejected, or deferred-via-issue — all count as assessed). If any target errored (push failed, gh down), leave every affected source SHA where it was and report; next week re-runs and the PR-dedup step below absorbs the overlap.

## Weekly procedure

### 1. Fetch and detect

For each repo: `git -C <checkout> fetch origin --quiet`, record `git rev-parse origin/main`, then list candidate commits:

```bash
git -C <checkout> log --oneline <state-sha>..origin/main -- .claude/skills/
```

**Loop guard:** drop commits whose subject contains `[skills-sync]` — those arrived *from* this process; re-propagating them ping-pongs forever. (A later human edit to a synced skill is a normal commit and propagates normally.)

If no repo has candidate commits: write state (fresh SHAs + `last_run`), report "No skill changes this week", stop.

**But zero candidates is a claim, not a default.** A missing checkout, a failed fetch, or a path typo produces exactly the same empty `git log` as a genuinely quiet week — and writing state on it advances the SHA past commits nobody read, permanently. The state file makes that silent: next week's scan starts after the work it skipped. Before reporting "no changes", confirm every repo in the sync set returned a real `origin/main` SHA in the step above. A repo you could not scan gets named in the summary and **keeps its old SHA**; never fold it into "none".

### 2. Understand each change

For each candidate commit, read the actual diff and the final file state:

```bash
git -C <checkout> show <sha> -- .claude/skills/
git -C <checkout> show origin/main:.claude/skills/<skill>/SKILL.md
```

Cluster commits by skill — you're porting the skill's *net* change for the week, not replaying individual commits.

### 3. Judge portability

For each changed skill × each of the three other repos, read the target's counterpart skill (same name, or same purpose — `start`/`start-morning`, `wrap-up`/`wrap-up-eod` are families) and pick one:

- **Port** — the change is a mechanism that generalizes: a verification step, an ordering fix, a destructive-step guard, a summary format that reads better, a session-hygiene rule, frontmatter/registration conventions. Rewrite it in the target skill's voice, structure, and domain vocabulary. Never paste source text; never carry over paths, issue numbers, people, vendors, or domain terms.
- **Already present** — target has the equivalent. Say so in the PR body only if it's interesting.
- **Not applicable** — the change is repo-specific content (payroll steps, portfolio math, store rosters) or contradicts how the target repo works. When in doubt, this is the answer — list it under "Considered, not ported" instead of forcing an edit. A wrong port costs more than a missed one.
- **Issue instead of PR** — the pattern is right but the edit is too big or presumptuous to write confidently (e.g., target has no counterpart skill and creating one needs domain judgment). File a `[skills-sync]` issue in the target describing the pattern and linking the source commit. Creating a missing counterpart skill directly is allowed only when it's small, generic, and obviously useful.

Extra rules:

- **Public-repo guard:** best-practices is PUBLIC. Nothing from the private repos' skills may land here unless fully generalized — no business names, dollar amounts, people, vendors, internal URLs, or anything that smells like operational detail.
- **Per-repo conventions:** skim the target's CLAUDE.md and one existing skill before editing. command-center keeps `.claude/skills/INDEX.md` — update it when adding a skill there. Write LF and let each repo's `.gitattributes` normalize (the CRLF/exit-127 scar).
- **Keep PRs reviewable:** one PR per target per run, minimal diffs. In a monster week (>~25 changed skill files from one source), port the highest-impact handful and file one issue in each affected target listing the rest — the trail preserved in the issue lets state still advance.

### 4. Apply — one PR per target repo

Dedup first: `gh pr list -R michaeladickson/<repo> --state open --search "[skills-sync]"`. If an open sync PR exists, push this week's commits onto **its existing branch** instead of opening a second PR; also skip any source commit already listed in an open PR's "Source commits covered" section.

**Merge `origin/main` into that branch before you edit it.** A sync branch is cut from `origin/main` on the day it was opened, so the file this week's port belongs in may not exist on it yet — the 2026-09-07 branch had no `start/SKILL.md` at all, because `/start` was created two days after it. Splicing into a file that isn't there fails loudly; the worse case is editing a stale copy and silently reverting whatever main has since landed in it. Merge, confirm the merge was clean, then port. Update the PR body's "Source commits covered" to cover both runs, and say in the body that two runs are stacked and why.

**Report the age of any sync PR you find open.** This skill opens PRs into three repos and has never looked back at whether they landed — an open PR reads as healthy by definition, and green CI never alarms on one that has simply stopped moving (command-center#415: 14 days, ~450 lines unlanded, ten wrap-ups each calling it "in flight"). Ask for the age and merge state at dedup time, and name anything quiet 7+ days or `CONFLICTING` on the summary's `PRs:` line rather than silently stacking another week of commits onto it:

```bash
gh pr list -R michaeladickson/<repo> --state open --search "[skills-sync]" \
  --json number,updatedAt,mergeable
```

Otherwise, for each target with ≥1 port:

```bash
git -C <checkout> worktree add C:/Users/micha/.claude/skills-sync/worktrees/<repo> -b claude/skills-sync-YYYY-MM-DD origin/main
# edit skills in that worktree
git -C <worktree> commit ...   # subject ends with [skills-sync]
git -C <worktree> push -u origin claude/skills-sync-YYYY-MM-DD
gh pr create -R michaeladickson/<repo> ...
git -C <checkout> worktree remove --force <worktree> && git -C <checkout> worktree prune
```

Commit identity: `-c user.name=michaeladickson -c user.email=michael.a.dickson@gmail.com`, body ends with the `Co-Authored-By: Claude <model> <noreply@anthropic.com>` trailer. Never push to any repo's main.

PR title: `Skills sync YYYY-MM-DD: <one-line gist> [skills-sync]`. Body template:

```markdown
Weekly cross-repo skills sync (best-practices /skills-sync).

Source commits covered:
- <repo>@<short-sha> — <subject>

### Ported
- `<skill>`: <what changed and why it applies here, 1–2 lines>

### Considered, not ported
- <repo>@<short-sha> `<skill>`: <one-line reason>

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

"Source commits covered" is the dedup key for future runs — always list every assessed commit, even when everything landed in "not ported".

### 5. Frontmatter lint — every run, including a quiet week

Runs whether or not step 1 found candidate commits. It checks what is *on disk now*, not
what changed, because both failures it catches are silent and arrive by being copied.

```bash
python - <<'EOF'
import glob, io, os, yaml
OK = {"name","description","when_to_use","argument-hint","arguments",
      "disable-model-invocation","user-invocable","allowed-tools","disallowed-tools",
      "model","effort","context","agent","background","hooks","paths","shell",
      "metadata","license","compatibility"}
for r in ["C:/Users/micha/best-practices","C:/Users/micha/crumbl-ops",
          "C:/Users/micha/command-center","C:/Users/micha/wealth-mgmt"]:
    for f in glob.glob(os.path.join(r,".claude","skills","**","SKILL.md"), recursive=True):
        s = io.open(f, encoding="utf-8", errors="replace").read()
        if not s.startswith("---"):
            print("NO FRONTMATTER", f); continue
        try:
            d = yaml.safe_load(s.split("---",2)[1]) or {}
        except Exception as e:
            print("INVALID YAML  ", f, "--", str(e).splitlines()[0]); continue
        for k in d:
            if k not in OK:
                print("UNKNOWN KEY   ", f, "--", k)
EOF
```

**`INVALID YAML`** is almost always an unquoted `: ` inside a long `description:`. The
harness parser is lenient enough that the skill still loads — crumbl-ops `start-morning`
has been invalid since it was written and appears in 82 transcripts — so nothing visibly
breaks, and that is the problem: the file is one parser change away from silently
disappearing, and a strict reader (this lint, a plugin packager, any future tooling) sees
a skill with no name and no description. Fix by quoting the whole value.

**`UNKNOWN KEY`** is a field the harness does not read. Measured 2026-09-20: official
Anthropic skills use `user-invocable` (8) and `disable-model-invocation` (12) and never
the underscore spelling, while all four of these repos use `user_invocable` in 100 files
and the hyphenated form in none. That particular key is inert and harmless, because
user-invocability is the default and `: true` is what everyone meant anyway.

It is still worth reporting, because the cost is not in the key that is wrong today. It
is in the habit: the same underscore reflex applied to `disable-model-invocation` gives a
skill the model invokes anyway, and applied to `allowed-tools` gives one that runs with
every tool. Both fail open, and neither prints anything. Report unknown keys with the
field the author probably meant; do not mass-rename inert ones — churn across 100 files
for no behavior change is worse than the finding. The policy is grandfathering, not
tolerance: a **new or edited** skill uses the documented spelling (`wait-what` is the
reference), and the inert keys already in place stay until the file is being touched for
another reason. An unknown key on a skill whose diff you are already reviewing in step 2
is a free fix; one sitting untouched is not worth a PR of its own.

**Hook drift.** `.claude/hooks/lint_on_write.py` and its test are meant to be
byte-identical to the canonical copies in best-practices. Compare them on `origin/main`:

```bash
C=$(MSYS_NO_PATHCONV=1 git -C C:/Users/micha/best-practices rev-parse --verify -q origin/main:.claude/hooks/lint_on_write.py)
for r in crumbl-ops command-center wealth-mgmt; do
  H=$(MSYS_NO_PATHCONV=1 git -C C:/Users/micha/$r rev-parse --verify -q origin/main:.claude/hooks/lint_on_write.py 2>/dev/null)
  if   [ -z "$H" ];      then echo "hook absent $r"
  elif [ "$H" = "$C" ]; then echo "hook ok     $r"
  else                       echo "HOOK DRIFT  $r"; fi
done
```

`--verify -q` matters: without it `rev-parse` echoes its argument back when the path is
absent, so an uninstalled repo reads as DRIFT instead of `absent`. Blob ids compare content after git's line-ending normalization, so a CRLF working copy
is not drift. A copy that differs is either a local fix that belongs in the canonical
file or a stale copy; port in whichever direction is right, as a normal `[skills-sync]`
change. `absent` before the install PRs merge is expected, not drift.

Report both classes, and any hook drift, in the step 6 summary under `Lint:`. Do not auto-fix: these live in
other repos and go out as a normal `[skills-sync]` PR like any other port, or as an issue
when there is nothing else to send that repo.

### 6. Close out

1. Remove all sync worktrees (`worktree remove --force` + `worktree prune` in each repo touched).
2. Write `state.json`: the SHAs recorded in step 1 for every fully-assessed source, `last_run` = today.
3. Summary, terse:

```
Skills sync YYYY-MM-DD.
Changes: <repo> N commits / M skills, ...  (or "none")
PRs: <repo>#<n> — <gist>, ...  (or "none needed")
Issues: <repo>#<n>, ...  (or none)
Lint: <n> invalid YAML, <n> unknown keys  (or "clean")
Skipped/errors: ...  (state not advanced for: ...)
```

## Manual runs

- `/skills-sync` in a best-practices session runs the same procedure on demand (state file keeps it incremental).
- "Full reconcile": on explicit request only — ignore state, compare all four repos' *current* skills for accumulated drift, and propose ports. Bigger job, same rubric and PR conventions.
