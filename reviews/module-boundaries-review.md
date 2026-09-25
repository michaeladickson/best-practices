FIRST: If review-context.md exists, read it for project context and intentional
design decisions. Follow it strictly — do NOT flag intentional decisions.
ALSO: Read existing-issues.md if present — do NOT report findings already tracked there.

---

Perform a **module boundaries and dependency review** of this repository, as a senior
software architect would when deciding whether the codebase can keep growing without
each change getting slower and riskier. The question: does the structure divide the
system along its real seams, so a change lands in one place, or does every change
touch the same central files? Be calibrated in both directions: name real strengths
with evidence, and do not inflate findings.

**Evidence rule.** Grade from measured structure, not from reading a few files. Part A
is mandatory: compute it from the code and the git history (a short AST script is
enough) and cite the numbers. A boundary that exists only in a README is not a
boundary; one that a test or linter enforces is.

## Part A — Measure the structure

1. **Size and shape.** Lines and module count per top-level package; the largest
   modules and functions; counts over 1,000 lines per module and 100 / 200 lines per
   function. One package holding most of the code is a drawer, not a module.
2. **The import graph.** Resolve intra-project imports (top-level and inside
   functions). Report strongly connected components (import cycles) with their
   members, the highest fan-in modules (the foundations everything depends on) and the
   highest fan-out modules (the orchestrators that depend on everything). A cycle that
   includes the configuration or database layer means the foundation is not a
   foundation.
3. **Function-level imports.** Count imports of project modules inside functions. A
   few are legitimate (heavy optional dependencies, CLI entry points). Hundreds are
   usually cycles being dodged rather than fixed.
4. **Direction of dependency.** A package-to-package edge matrix. Name every edge that
   points the wrong way: domain or service code importing the web layer, low-level
   helpers importing orchestrators, vendor integrations importing each other.
5. **Where data access lives.** Which packages open database connections and run SQL.
   SQL spread through web handlers, schedulers and domain code alike means there is no
   data-access boundary, and a schema change has no single place to land.
6. **Change hotspots from git history** (last ~90 days): most-changed files, and pairs
   of files in *different* packages that change together most often. A file edited in
   a large share of all commits is a merge-conflict magnet; frequent cross-package
   co-change means the boundary between them is drawn in the wrong place.

## Part B — Grade the boundaries (judgment, with evidence)

For each area: current state, grade **Good / Gap / Missing**, concrete fix with
file/path. Count; do not characterize without a number.

1. **Decomposition by domain.** Does the package structure follow the business
   domains (sales, labor, inventory, accounting, forecasting), with each domain's
   rules in one place? Or is there a catch-all package where every domain lives side
   by side?
2. **Layering.** Is there a recognizable direction (entry points → application
   services → domain → data access → infrastructure)? Do web handlers contain business
   rules and SQL? Does anything low import anything high?
3. **Orchestrators.** The modules with the highest fan-out (schedulers, app startup,
   nightly jobs): do they compose small named steps, or are they the place where the
   logic actually lives (one function of thousands of lines)?
4. **Extension points.** When a new check, report, integration or vendor is added, how
   many files change? A central registry every addition must edit, or a list in an
   orchestrator, is a hotspot by construction; registration by convention or a plugin
   interface is not.
5. **One concept, one home.** The same concept implemented more than once: helpers,
   date and timezone logic, money formatting, the same query written in several
   modules, parallel runners or clients for the same system. Count them.
6. **Vendor and integration isolation.** Is each external system (accounting, payroll,
   POS, suppliers) behind one adapter module with an interface the rest of the code
   uses, or do its details (IDs, field names, error shapes) leak into domain code?
7. **Cycles and the foundation.** Are configuration, database access and logging a
   true bottom layer with no upward imports? What does each cycle cost (import-order
   bugs, lazy imports, untestable modules)?
8. **Enforcement.** Are any boundaries enforced by a test or linter (import-linter
   contracts, an AST test, a ratchet on file size or cycles)? Unenforced boundaries
   erode one reasonable-looking import at a time.
9. **Changeability.** From the co-change data: which boundaries force multi-package
   edits for a single feature, and what restructuring would make the common change
   land in one package?

## What separates deliberate from generated

Call these out explicitly, in either direction, with evidence:

- **Generated without understanding:** one package holding most of the code; functions
  of many hundreds of lines; hundreds of function-level imports papering over cycles;
  the same helper or client written several times; a central file edited by most
  commits; web handlers that are also the business logic and the data access.
- **Deliberate and experienced:** a small, acyclic foundation; domain packages with
  narrow public surfaces; orchestrators that read like a table of contents; boundaries
  written as import contracts and checked in CI; hotspots known and being split on
  purpose.

Reference: `reviews/code-review.md` covers per-diff code quality; `reviews/database-review.md`
covers schema and data access performance. Focus here on structure and do not
duplicate their findings.

Format your findings as a markdown document with:
- A three-sentence verdict, calibrated: can this codebase keep growing at its current
  pace without each change getting slower, and what one structural change would help
  most?
- The Part A measurements as a short table (metric → value → what it means).
- A one-line scorecard: count of Good / Gap / Missing across the 9 Part B areas.
- Findings grouped by priority (High / Medium / Low). Cycles in the foundation, a
  catch-all package holding most of the code, and a hotspot file touched by a large
  share of commits rank High.
- Each finding: area, evidence (module, line, measured count), grade, concrete fix, and
  the first refactor step that would start it without a big-bang rewrite.
- Use markdown checkboxes so items can be tracked.

Output ONLY the findings, no title or preamble.
