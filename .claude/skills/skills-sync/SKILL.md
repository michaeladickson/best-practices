---
name: skills-sync
description: Weekly cross-repo scan of Claude skill changes across best-practices, crumbl-ops, command-center, and wealth-mgmt. Detects .claude/skills/ commits since the last run, judges which changes are portable patterns vs repo-specific content, and opens one adapted [skills-sync] PR per target repo. Run weekly by the weekly-skills-sync scheduled task, or manually anytime.
user_invocable: true
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

### 5. Close out

1. Remove all sync worktrees (`worktree remove --force` + `worktree prune` in each repo touched).
2. Write `state.json`: the SHAs recorded in step 1 for every fully-assessed source, `last_run` = today.
3. Summary, terse:

```
Skills sync YYYY-MM-DD.
Changes: <repo> N commits / M skills, ...  (or "none")
PRs: <repo>#<n> — <gist>, ...  (or "none needed")
Issues: <repo>#<n>, ...  (or none)
Skipped/errors: ...  (state not advanced for: ...)
```

## Manual runs

- `/skills-sync` in a best-practices session runs the same procedure on demand (state file keeps it incremental).
- "Full reconcile": on explicit request only — ignore state, compare all four repos' *current* skills for accumulated drift, and propose ports. Bigger job, same rubric and PR conventions.
