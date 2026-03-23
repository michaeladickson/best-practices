Perform a comprehensive code review of this codebase. Focus on:

1. **Security** — SQL injection, XSS, auth bypass, secrets exposure, input validation
2. **Data Integrity** — Race conditions, non-atomic operations, missing transactions, duplicate writes, missing unique constraints
3. **Error Handling** — Unhandled exceptions, silent failures, missing error states, AI calls without fallbacks
4. **Performance** — N+1 queries, unbounded data loads, missing indexes, memory leaks, uncached repeated lookups
5. **Code Quality** — Dead code, duplicated logic, missing type safety, unclear naming, functions doing too many things
6. **Resilience** — Missing retry logic on external APIs, no circuit breakers, timeout handling, graceful degradation

Review all source files.

Format your findings as a markdown document with:
- Executive summary (2-3 sentences)
- Findings grouped by severity (Critical, High, Medium, Low)
- Each finding should have: file, line number, description, suggested fix
- Use markdown checkboxes so items can be tracked

Output ONLY the findings, no title or preamble.
