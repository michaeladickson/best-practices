# Context & Memory Management

How an agent decides *what to remember, where to put it, and when to read it back*. The goal: reconstruct the right context by **retrieval** (reading a known home) rather than **rediscovery** (re-deriving facts from code or scattered notes) — without paying for that context on every session.

## Memory Tiers

Three places a fact can live, by scope:

| Tier | Home | Scope | Examples |
|---|---|---|---|
| **1 — Session** | the conversation | this session only | what you're mid-way through, a value you just computed |
| **2 — Project** | the repo: `CLAUDE.md`, per-module `CLAUDE.md`, `knowledge/`, `decisions/` | true for *this* repo | agent I/O contracts, domain rules, architectural decisions |
| **3 — Global** | `~/best-practices/practices/` and cross-session memory | true across repos / about the user | build conventions, the user's preferences and profile |

**The tier test** — before storing a fact, ask: *would this be true in another repo?* → Tier 3. *Only here?* → Tier 2. *Only this session?* → don't store it.

## Retrieval Contracts (Sources of Truth)

Every recurring fact gets **one canonical home**. Read that home; don't re-derive the fact from code or copy it into a second file.

- **Name the winner.** When two files describe the same fact, one is authoritative and the other points to it. Maintain a "sources of truth" table (one per repo) so the canonical home for each fact-scope is unambiguous.
- **A per-module `CLAUDE.md` is a retrieval contract.** Read it instead of re-reading the module's code to learn what the module does. Because it stands in for the code, it **must mirror the code** — and when they disagree, *the code is authoritative and the doc is the bug.* A silently drifted doc is worse than no doc, because it is trusted.
- **Point, don't restate.** A non-canonical mention of a fact should link to the home, not duplicate the content. Duplication is what drifts.

Worked example (from a production hub repo): a `Sources of Truth` table maps *people* → a contacts file, *deal participants* → a domain knowledge file, *agent I/O* → that agent's `CLAUDE.md` (code-authoritative), *layout & conventions* → a file-map doc, *past choices* → the decision journal, *cross-session user facts* → memory.

## Context Budget

Context splits into **always-loaded** (paid every session) and **load-on-demand** (paid only when needed):

- **Always-loaded** — root `CLAUDE.md`, the memory *index*. Keep these a **names-and-pointers index**: orientation, not detail.
- **Load-on-demand** — file maps, domain knowledge, decision records, per-module docs. Detail lives here; a pointer from the always-loaded layer makes it discoverable.

The asymmetry drives the rule: a paragraph in root `CLAUDE.md` is paid in every future session whether or not it's relevant; the same paragraph in a load-on-demand file costs nothing until something needs it. **Push detail down; keep the top layer lean.**

## Cross-Boundary Duplication Is Allowed

The anti-duplication rule applies *within* a load context, not across. Cross-session memory may legitimately restate a repo fact, because memory loads when a *different* repo is active and this repo's docs are not in context. The test isn't "does this string appear twice?" — it's "can these two copies be in context at the same time and disagree?" If they can never co-occur, the duplication is safe and often necessary.

## Avoiding Fragmentation

The failure mode a retrieval contract prevents is *two homes for one fact that drift apart*. So:

- **Don't create a second "where things live" doc.** Extend the canonical one. A new `SOURCES.md` beside an existing file-map doc just adds a surface that can disagree.
- **Corrections already have homes** — behavioral feedback → cross-session memory; architectural choices → the decision journal; a domain hypothesis that failed → demote it in `hypotheses.md`. A dedicated `ERRORS.md` fragments these.
- **Staleness** — let time-sensitive entries carry an inline date so freshness is visible; don't add a manual "last verified" header to every file (upkeep burden, and git history already records change time). Status *snapshots* (a `PROJECT_STATUS.md`) can be staleness-checked by mtime; stable reference facts can't — age ≠ wrong.

## Decision Journal

Choices that outlive today's task go in `decisions/YYYY-MM-DD-{topic}.md` (see [CLAUDE.md Structure](claude-md-structure.md)). Each record: Decision / Context / Alternatives Considered / Reasoning / Trade-offs. `Supersedes:` / `Superseded-by:` headers chain related records into a grep-able audit trail. **Grep the journal before making a similar choice** — it's the institutional memory that keeps you from re-litigating settled questions.

## Provenance

When surfaced context is **AI-generated** (a model-written summary, a classification), mark it where it's shown, so a reader can tell synthesis from ground truth and knows to verify before acting. Raw data and AI synthesis should stay visually distinguishable.

## Enforcement (the frontier)

None of the above is self-enforcing — docs drift from code silently. The maturity endpoint is an audit/maintenance agent that detects drift: *deterministically* for status snapshots (issues referenced in a status file that are now closed; file mtime), and via an *AI pass* for semantic drift (a per-module `CLAUDE.md` whose described inputs no longer match its code). Until that exists, drift is caught only when a human or agent happens to read both sides.

## Where Used

- **command-center** — `knowledge/FILE_MAP.md` "Sources of Truth" table; per-agent `CLAUDE.md` retrieval contracts (code-authoritative); `decisions/` journal; three-tier memory (session / repo `knowledge/` / global practices + cross-session memory); maintenance agent does deterministic status-drift detection (semantic doc/code drift detection is roadmapped).
- The memory-tier model and "tier test" apply to any repo with a root `CLAUDE.md` and a shared global practices catalog.
