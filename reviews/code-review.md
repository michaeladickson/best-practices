FIRST: If review-context.md exists, read it for project context, threat model, and
intentional design decisions. Follow it strictly — do NOT flag intentional decisions.
ALSO: Read existing-issues.md — do NOT report findings already tracked there.
ALSO: If digest-intelligence.md exists, read it for emerging threats and patterns
to check against; skip it silently if it is absent.

---

Perform a comprehensive code review of this codebase. Focus on:

1. **Security** — SQL injection, XSS, auth bypass, secrets exposure, input validation
2. **Data Integrity** — Race conditions, non-atomic operations, missing transactions, duplicate writes, missing unique constraints
3. **Error Handling** — Unhandled exceptions, silent failures, missing error states, AI calls without fallbacks
4. **Performance** — N+1 queries, unbounded data loads, missing indexes, memory leaks, uncached repeated lookups
5. **Code Quality** — Dead code, duplicated logic, missing type safety, unclear naming, functions doing too many things
6. **Resilience** — Missing retry logic on external APIs, no circuit breakers, timeout handling, graceful degradation

Review all source files: Python, TypeScript, SQL (schema + migrations), configuration (YAML, Dockerfiles, CI workflows), and shell scripts.

If nothing is worth fixing, output exactly "No findings this window." and nothing else.

Otherwise, format your findings as a markdown document with:
- A summary that opens with the count, e.g. "5 findings: 1 High, 3 Medium, 1 Low;
  2 pre-existing." Then 1-2 sentences on what matters most.
- Findings grouped by severity (Critical, High, Medium, Low)
- Each finding should have: file, line number, description, suggested fix
- Tag each finding **[Introduced]** or **[Pre-existing]**. In a change review,
  [Pre-existing] means the bug is in code the window's diff did not add or alter:
  you saw it while reading context. Report it, but never as the change's fault.
  In a full-scope review, omit the tag.
- When one bug appears in several places, report it once as a class and list every
  location, so a single fix covers all of them.
- Use markdown checkboxes so items can be tracked

Output ONLY the findings, no title or preamble.
