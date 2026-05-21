FIRST: If review-context.md exists, read it for project context and intentional
design decisions. Follow it strictly — do NOT flag intentional decisions.
ALSO: Read existing-issues.md if present — do NOT report findings already tracked there.

---

Perform an **AI-slop & code-review self-assessment** of this repository. The goal is
to find where AI-generated code (this repo is built largely with Claude Code) can ship
hidden technical debt, and where the review process would fail to catch it. Slop is
code that looks finished and passes a glance but carries deferred cost — review and
maintenance, not generation, is where that cost lands.

Do two things:

**Part A — Process audit.** Inspect how AI-authored changes get reviewed and verified.
Look at `.github/workflows/`, the review prompts in use, CI config, `CLAUDE.md` (root
+ per-module), `AGENTS.md` if present, test setup, and any contributing/PR docs.

**Part B — Code spot-check.** Sample recent changes (use git history — recent commits,
large diffs, files changed most often) and inspect the actual code for slop signatures.

Assess against each area below. For each: state the current state, grade it
**Good / Gap / Missing**, and give a concrete fix with the file/path.

1. **Spec discipline** — Are non-trivial changes specified (target files, expected
   I/O, constraints, done-criteria) before the agent codes, or are vague prompts the
   norm? Is there anything (PR template, CLAUDE.md guidance) that enforces it?

2. **Reasoning defense** — Is there a step where the agent must explain *why* (design
   choices, alternatives ruled out, uncertainties), or does code merge with no
   recorded reasoning?

3. **Real-environment validation** — Do changes get run/tested/deployed to a real or
   ephemeral environment before trust, or is "looks done" / green-unit-tests enough?
   Is there a validation loop (CI, AGENTS.md, smoke tests)? Could an agent's *claim*
   of success pass unverified?

4. **AI-code-review checklist** — Is there an explicit checklist covering readability,
   maintainability, architectural fit, hidden complexity, hallucinated APIs, and blast
   radius — beyond the generic code review? Spot-check: do recent diffs show
   over-engineering, parallel-pattern reinvention, or unowned complexity?

5. **Automated review gate** — Is there a second-model/agent review (dual-model, like
   best-practices `reviews/`) before merge, and is a human accountable for the merge
   decision? Or is automated/self-review the only gate?

6. **Destructive-action gating** — Can an agent run migrations, deletes, prod writes,
   or money movement without a human gate? Is operational/destructive context
   externalized into CLAUDE.md / knowledge/ so the agent knows what's load-bearing?
   (This is the highest-severity area — weight it accordingly.)

7. **Diff size & scope** — Are AI changes kept small and single-concern, or do large
   multi-file diffs land that are too big to review properly?

8. **Self-correction spirals** — Any signs in history of the model looping/re-fixing
   (churn commits, repeated reverts on the same lines)? Is there guidance to rewind +
   re-spec rather than argue in-context?

9. **Cleanup-tax telemetry** — Is rework tracked at all (revert rate, hot-fixes or
   refactors shortly after merge of AI-authored code), or is velocity the only signal?

Reference standard: `best-practices/practices/claude-code/code-review-and-ai-slop.md`
(and the general `reviews/code-review.md`, which this complements — don't duplicate its
generic findings; focus on the AI-specific failure modes).

Format your findings as a markdown document with:
- A one-line scorecard: count of Good / Gap / Missing across the 9 areas.
- Findings grouped by priority (High, Medium, Low) — destructive-action and validation
  gaps rank High.
- Each finding: area number + name, current state, grade, concrete fix with file/path,
  and (for Part B findings) the commit/file that prompted it.
- Use markdown checkboxes so items can be tracked.

Output ONLY the findings, no title or preamble.
