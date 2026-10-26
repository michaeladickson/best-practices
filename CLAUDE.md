# CLAUDE.md

> Context for Claude Code agents working on this repo.

## What This Is

Best practices repository — a living catalog of patterns, conventions, and tools extracted from production projects (crumbl-ops, wealth-mgmt, healthpulse). Reference this repo when starting new projects or making architectural decisions.

Also includes the RSS digest tool for ingesting new ideas from AI/engineering blogs.

## Structure

```
best-practices/
  practices/           # Categorized best practice documents
    INDEX.md           # Start here — links to all practices
    architecture/      # FastAPI, DB, Pydantic, resilience, logging, config, testing, mobile
    ai/                # Gemini integration, prompt engineering
    finance/           # AI for finance, investing patterns, payroll
    security/          # Secrets management, auth, rate limiting
    devops/            # Cloud Run, CI/CD
    claude-code/       # CLAUDE.md templates, CLI patterns
    writing/           # voice-memory capture mechanism, email drafting
  reviews/             # Claude-only, diff-scoped review system — see reviews/README.md
    workflow-template.yml  # 6 scheduled types: changes (Mon), data-qa (Thu),
                       #   ai-slop (8th), context-memory (1st), model-hierarchy (15th),
                       #   cto (22nd).
                       #   Consumed by wealth-mgmt; crumbl-ops self-hosts its own
                       #   prompts; command-center has no weekly review workflow.
    pr-review-template.yml # Optional per-PR Claude review (one comment per PR);
                       #   from command-center's gate. Setup in reviews/README.md.
    *-review.md        # Scheduled prompts + on-demand audits (ui, devops, ai-slop, ...)
  digest/              # RSS digest tool (module)
    ai_digest.py       # Main logic
    config/            # feeds.yaml, 3 context files
    requirements.txt   # Python dependencies
  knowledge/           # Learning log
  .claude/hooks/       # Canonical write-time hooks, copied into the other repos
```

## Using Practices

When starting a new project or making a decision, check `practices/INDEX.md` for relevant patterns. Each practice doc includes:
- The pattern with code examples
- Key conventions and gotchas
- Which repos use it (for real-world reference)

## Running the Digest

Three digests, each targeted at a specific repo. Every digest:
- Sends an email to `michael.a.dickson@gmail.com`
- Saves a knowledge file under `data/digest_knowledge/`
- Creates a self-contained GitHub issue in the target repo (local execution only — see below)

### Scheduled execution (local, Friday 6pm ET)

The full pipeline runs locally as Windows Task Scheduler task `CC-WeeklyDigest`,
not in GitHub Actions. Reasons: avoids storing a cross-repo PAT in this public
repo, and uses local `gh` auth to file issues in crumbl-ops and wealth-mgmt (and
failure alerts in command-center).

**Exit status:** 1 only when the run delivered nothing (no digest email and no
practice-doc update). A partial failure (one context down, a blocked practice doc)
exits 0 and is carried by an open `Weekly digest: partial failure` issue in
command-center, commented on each week it recurs. A red task used to mean "one
sub-step failed" 3 weeks in 4 while the emails went out, so it stopped meaning anything.

```powershell
# One-time registration:
powershell -ExecutionPolicy Bypass -File scripts/register_weekly_digest.ps1
```

The wrapper at `scripts/run_weekly_digest.sh`:
1. Pulls `gemini-api-key` and `smtp-password` from GCP Secret Manager (project `hybrid-elysium-471814-p2`)
2. Runs both digests (crumbl-ops, wealth-mgmt) via WSL bash. The command-center context was retired 2026-09-21: its idea issues closed with no action in most weeks, so each run only created a triage chore
3. Creates GitHub issues in target repos using local `gh` auth
4. Auto-updates the living practice docs from the same week's articles (`python -m digest.practice_updater`) — see below
5. Commits and pushes the new knowledge files + any practice-doc updates back to `origin/main` (two separate `[automated]` commits)
6. Telemetry (best-effort, never fails the run): regenerates `data/feed_report.md` (per-feed yield + freshness), runs `digest/citation_discovery.py` (proposes feed candidates as GitHub issues when a domain is cited in ≥3 articles by ≥2 feeds — human approves by editing feeds.yaml), `scripts/check_heartbeats.py` (unified dead-man's tell for all scheduled jobs; files an issue on staleness), and `digest/model_pricing.py` (OpenRouter price watch, plus the Gemini API deprecations page: files an issue when a `gemini-2.5-*` shutdown date changes, and a "page unreadable" issue when the page cannot be read). Also pulls evaluation verdicts from closed digest issues into `data/digest_feedback/` so rejected ideas aren't re-proposed (runs pre-analysis, per context).

### Auto-updating the living practice docs

Each weekly run also feeds the week's archived articles to `digest/practice_updater.py`,
which **auto-edits** the living practice docs in place:
- `practices/claude-code/context-memory-management.md`
- `practices/claude-code/code-review-and-ai-slop.md`
- `practices/ai-safety/agent-action-safety.md`
- `practices/ai/llm-evaluation.md`
- `practices/claude-code/model-hierarchy-delegation.md`

Config is `digest/config/practice-docs.yaml` (topic, scope, keyword prefilter, required
anchors). Guardrails, since this also edits the anti-slop doc itself:
- **Dedup ledger** `data/practice_updates/incorporated.json` — a source article is never
  integrated into the same doc twice.
- **Two-stage LLM** — one extraction across all docs routes each genuinely-new candidate
  to exactly one doc (per-doc extraction wrote the same idea into two docs), then each
  doc integrates its own. An unparseable extraction blocks the run rather than marking
  the week's articles seen.
- **Structural validation before write** — H1 + required anchors (`## Sources`,
  `## Where Used`) must survive and length must stay in bounds, else the write is
  rejected and the doc is left untouched (retries next week). Git history is the backstop.
- **Practice titles capped at 12 words** (`MAX_PRACTICE_TITLE_WORDS`) — both prompts
  ask for the short hand-written register and the validator rejects any edit that adds
  a longer one. New-only, so a pre-existing long title never blocks a run. Of the 151
  found on 2026-09-20, 2 remained on 2026-10-21 and were shortened by hand that day;
  `_overlong_titles()` over the five docs reads 0.
- **At most 3 new practices per run** (`MAX_CANDIDATES_PER_RUN`), high confidence first.
  The prompt's "most weeks yield 0-3" was ignored every week; the 2026-10-23 run added 23,
  and 19 were cut by hand on 2026-10-26. The validator also rejects a newly repeated
  `### N.` practice number (that run left 5, 6 and 7 twice in agent-action-safety.md).
- Most weeks change nothing. Review the `[automated]` practice commits like any other diff.

### Thin feed entries are read from the article

Scoring and practice extraction both judge a post by its `content_preview`. When an
in-window entry has under 200 characters of text (Google Cloud Blog and Hugging Face
send none; the Hacker News feed sends only links and points), `_fetch_feeds` fetches
the article page (`digest/article_text.py`, standard library only) and stores the
text in the archive, so both stages and the second context see it. A site that
refuses scripts (OpenAI, CFO Dive answer 403) keeps its feed preview and is flagged
`article_fetch_failed` so the run does not retry it. Capped at `MAX_ARTICLE_FETCHES`
(100) per feed pass.

### One-off inputs (digest inbox)

Drop a video transcript, pasted article, or PDF-as-text into `data/digest_inbox/`
(gitignored — content may be copyrighted or private) as a `.md` with frontmatter
`title:` and `source_url:` (optional `date:`, `source:`, `category:`). The next
digest run scores it alongside feed posts for every context; the wrapper moves it
to `processed/` after every context succeeds. The archive dedups by `source_url`.
Citation-discovery issues that end "no feed — check manually" route here too.

### Manual / dev runs

```bash
cd /path/to/best-practices
pip install -r digest/requirements.txt

# Dry-run any context
python -m digest --context digest/config/context-crumbl-ops.yaml --dry-run
python -m digest --context digest/config/context-wealth-mgmt.yaml --dry-run

# Preview the practice-doc auto-update (shows diffs, writes nothing, touches no ledger)
python -m digest.practice_updater --dry-run

# Or run the full local pipeline manually
bash scripts/run_weekly_digest.sh
```

The GitHub Actions workflow (`.github/workflows/weekly-digests.yml`) remains
for manual dispatch fallback (e.g., re-running a failed digest from any
machine). It sends email + commits knowledge files and practice-doc updates,
but does NOT create issues — that part requires the local `gh` auth.

## Weekly Skills Sync

Skills evolve inside individual repos and the improvements never used to travel.
[`.claude/skills/skills-sync/SKILL.md`](.claude/skills/skills-sync/SKILL.md) is the weekly
propagation pass: it scans `.claude/skills/**` on `origin/main` across the four repos, judges
portable mechanism vs repo-specific content, and opens at most one adapted `[skills-sync]` PR
per target repo — never pushing to main, never touching a local working tree, never
generalizing private-repo detail into this public one. `[skills-sync]` commits are excluded
from future scans (ping-pong guard). Run `/skills-sync` for an on-demand pass, or ask for a
"full reconcile" to compare all four repos ignoring state.

Cadence, freshness signal, kill criteria, and rebuild-on-a-new-machine steps for this and for
every other standing job live in [`AUTOMATION.md`](AUTOMATION.md) — one row per job, checked
weekly by `scripts/check_heartbeats.py`. Read it before adding, changing, or diagnosing any
scheduled work, and add a row when you add a job: a job that exists but is not registered
there dies silently (the WM-WeeklyDigest lesson).

## Write-time hooks

Review catches slop after it is written; a hook catches it while the model is still in
the turn that wrote it. `.claude/hooks/lint_on_write.py` is the canonical copy, with
`test_lint_on_write.py` beside it (`python3 -m pytest .claude/hooks -q`).

- **What:** PostToolUse on Edit/Write of a `.py` file. Runs `ruff --select F,E9` on the
  file now and at `HEAD`, and exit-2s only on violations the edit *introduced*: invented
  names (F821), leftover imports (F401), dead variables (F841), shadowed defs (F811).
- **New-only, by multiset, not by changed line.** Three repos carry an F backlog, so a
  whole-file lint would nag on every edit. Filtering by changed lines misses an import
  whose last use was just deleted. Violations are matched on `(code, message)` with line
  numbers normalised out, so shifts are silent and a genuinely new instance still fires.
- **Loud-but-harmless failure:** no ruff, or a path the interpreter cannot see, produces
  one non-blocking notice per session rather than a gate that silently does not exist.
- **Installed in:** best-practices, crumbl-ops, command-center, wealth-mgmt, each with an
  identical copy wired in `.claude/settings.json`. Change the canonical copy first, then
  re-copy. `/skills-sync` step 5 compares blob ids weekly and reports drift.
- **The test fails under CI if ruff is missing, rather than skipping.** A skipped suite is
  a green check that tested nothing; wealth-mgmt's CI installs only its runtime lock, so
  it carries an explicit pinned `pip install ruff` step for this.

`.claude/hooks/closing_keyword_gate.py` is the second canonical hook, with
`test_closing_keyword_gate.py` beside it (same pytest command).

- **What:** PreToolUse on Bash and PowerShell. On `gh pr create`, `edit` and `merge` it
  blocks (exit 2) a close/fix/resolve word within two words of an OPEN issue's number,
  in any form GitHub honours (`#N`, `owner/repo#N`, the issue URL). A merge reads the
  PR's title, body, every commit and the merge commit GitHub will write; a branch ending
  `-fixes` beside a title starting `#N:` closed an issue that way. A reference into
  another repo always counts.
- **Deliberate close:** a line of its own, `Closes #N`. Anything else that should close
  an issue is rewritten, not excused.
- **Fails closed:** a gate that cannot read the PR or the open issues blocks with the
  reason. It reads every `gh pr` command in a chain, the `cd` before it, shell variables
  assigned in the same command, and the raw text where a heredoc body survives.
- **Installed in:** best-practices and wealth-mgmt (its test under `tests/`). Not yet in
  crumbl-ops or command-center; each gets its own PR, and crumbl-ops already runs merge
  gates as PreToolUse (`check_pr_merge_draft.py`), so check the order there. Same sync as `lint_on_write.py`: change the canonical copy
  first, then re-copy; `/skills-sync` step 5 pairs both files.
- **In a worktree session the live hook is the MAIN checkout's copy**, since
  `$CLAUDE_PROJECT_DIR` resolves there. A hook change takes effect only after merge and
  pull into the main checkout.

## Configuration

- `digest/config/feeds.yaml` — All RSS feed sources
- `digest/config/context-crumbl-ops.yaml` — Crumbl-ops digest (target: `michaeladickson/crumbl-ops`)
- `digest/config/context-wealth-mgmt.yaml` — Wealth-mgmt digest (target: `michaeladickson/wealth-mgmt`)
- `digest/config/practice-docs.yaml` — Living docs the weekly run auto-edits (topic, scope, keyword prefilter, required anchors)
- Secrets: pulled from GCP Secret Manager at runtime; no `.env` in this public repo

## Key Conventions

- Always use GEMINI_API_KEY, not Vertex AI (avoids gcloud reauth issues)
- Anything drafted to be sent or published as Michael follows the PRIVATE master voice
  memory at command-center `knowledge/voice/master.md`. This repo holds only the
  mechanism (`practices/writing/voice-memory.md`): `/wrap-up` captures draft-edit deltas
  as `feedback_voice_*` memories; command-center `/voice-sync` reconciles them monthly.
  Voice content itself never lands in this public repo.
- Practices docs should be actionable with code examples, not vague descriptions
- Each practice includes "Where Used" section linking to source repos
- Keep practices up to date as repos evolve

## Learning

Track knowledge in `knowledge/INDEX.md` → category files. The full memory model —
tiers, retrieval contracts, anti-fragmentation, and staleness — lives in
[`practices/claude-code/context-memory-management.md`](practices/claude-code/context-memory-management.md).
Key rules:

- **Corrections route to their home, not a catch-all log.** Behavioral feedback →
  cross-session memory; architectural choices → the `decisions/` journal; a failed
  domain hypothesis → demote it in the relevant `hypotheses.md`. A catch-all
  *corrections* log fragments these. This does not condemn a scoped error log:
  crumbl-ops `knowledge/ERRORS.md` holds only deterministic infra/code failures and
  carries a graduation rule in its header, which is a different artifact and fine.
- **Don't date-stamp everything.** Let genuinely time-sensitive entries carry an inline
  date; rely on git history for change time. Status *snapshots* can be staleness-checked
  by mtime, but stable reference facts can't — age ≠ wrong.
- **Flag contradictions.** When new evidence contradicts an established rule, surface it
  to the user rather than silently following the old rule; if confirmed, demote the rule
  where it lives.
