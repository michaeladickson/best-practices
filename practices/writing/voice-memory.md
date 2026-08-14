# Personal Voice Memory — Capture and Reconciliation

> The standardized mechanism for keeping one master record of a person's writing voice
> and feeding it from every repo where drafting happens. This doc is the pattern; the
> content lives elsewhere. Michael's master voice memory is PRIVATE and lives in
> command-center at `knowledge/voice/master.md`. Nothing from it belongs in this public
> repo, de-identified or not: public repos carry mechanisms, not personal content.

## The problem

Drafts written in the user's voice degrade because feedback fragments. A correction made
in one session lands in that repo's memory, a style note lands in a gitignored handoff
file, a third lesson stays buried in a session transcript, and no drafting session ever
sees all three. The fix is one canonical master plus two standing flows: capture at the
moment feedback happens, reconcile on a schedule.

## Architecture

| Piece | Home | Cadence |
|---|---|---|
| **Master voice memory** | one PRIVATE repo file (Michael: command-center `knowledge/voice/master.md`) | edited only by reconciliation |
| **Capture** | `feedback_voice_*.md` files in each project's session-memory directory, written by every repo's `/wrap-up` | at session end, or immediately when the edit happens |
| **Reconciliation** | `/voice-sync` skill in the master's repo, run by a monthly scheduled task | monthly |
| **Loading** | pointer + core excerpt in `~/.claude/CLAUDE.md`, read before any drafting | every session |

## Capture convention

When the user edits, corrects, or rewrites a draft the session produced:

- Diff the last AI version against the user's final one. Ignore factual/content edits;
  keep style deltas: cuts, word choice, greeting/sign-off, structure, punctuation,
  register.
- Write one file per distinct delta to the CURRENT project's memory directory
  (`~/.claude/projects/<project>/memory/`): `feedback_voice_<slug>.md`, standard memory
  frontmatter (`name`, `description`, `metadata.type: feedback`). Body: the rule, the
  user's words (one line), one before/after pair. Add the MEMORY.md index line.
- Do NOT edit the master directly from a capture session. Capture locally, reconcile
  centrally: it keeps arbitrary sessions from pushing to the master's repo and gives the
  monthly pass a chance to dedup and spot contradictions.
- An unedited draft the user explicitly approved can be captured as a confirming
  example; mere non-edits are not signal.

The filename prefix is the contract: reconciliation finds captures by globbing
`projects/*/memory/feedback_voice_*.md`, so the prefix matters more than the body shape.

## Reconciliation rules

The monthly pass (Michael: command-center `/voice-sync`) folds captures into the master:

- **Merge over append.** A delta covered by an existing rule strengthens that rule or
  refreshes its example; never append a near-duplicate.
- **Contradictions get flagged, not averaged.** Put both versions in the PR body for the
  user to confirm which wins, then demote the loser in the master. Never silently keep
  both.
- **Absorbed captures get stamped** (`Absorbed: YYYY-MM-DD`) and left in place as the
  provenance trail; the stamp is what makes re-runs idempotent.
- **Size cap.** The master loads at drafting time; hold it under ~250 lines by merging.
- **Spoken is not written.** Call transcripts inform what the user thinks, never how
  they write; transcript cadence must not drive written-voice rules.
- **PR per run, never a push to main.** The master is the user's voice; every change to
  it deserves a reviewable diff.
- **State + dead-man's tell.** `last_run` in a state file; if it goes stale past the
  cadence (~35 days for monthly), the scheduled task has died silently: say so. The
  task itself lives in app storage, not git; rebuilding a machine means recreating it.

## The public-repo boundary

The lesson that shaped this layout (2026-08-13): a de-identified profile is still
personal content, and a public repo's git history is forever. So the split is by
artifact class, not by scrubbing effort. Public repo (this one): the mechanism, the
capture step in `/wrap-up`, this doc. Private repo: the master, the registers, the
named examples, the reconciliation skill. The same line skills-sync draws for skill
content applies to voice content.

## Related but distinct

- [email-drafting.md](email-drafting.md): drafting process and prompt mechanics (the
  range-as-floor rule, no-summary-in-prompt, live A/B verification). Process, not voice.
- Machine-brief personas (crumbl-ops `knowledge/weekly-brief-feedback.md`,
  `knowledge/digest-feedback.md`): the voice a PRODUCT adopts when writing TO the user.
  Those stay with their products and their own feedback loops; the master is only for
  prose sent AS the user.
- Cross-session behavioral memory: how Claude works WITH the user in sessions. Different
  audience, same capture instinct.

## Where Used

- **command-center**: master (`knowledge/voice/master.md`), `/voice-sync` skill, monthly
  scheduled task `monthly-voice-sync`.
- **best-practices, crumbl-ops, command-center, wealth-mgmt**: capture step in each
  repo's `/wrap-up` (propagated by skills-sync from this repo's wrap-up).
- **`~/.claude/CLAUDE.md`**: the loading pointer + core excerpt every session sees.
