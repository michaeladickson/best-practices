Perform a comprehensive QA review of this codebase. Focus on:

1. **Happy Path Coverage** — Verify all API routes have proper request/response handling and validation
2. **Edge Cases** — Empty data, null values, boundary values, large datasets, unicode/special characters
3. **Data Integrity** — Non-atomic operations, optimistic updates without rollback, SQL concerns, missing constraints
4. **Multi-Tenant Scenarios** — Tenant/store filtering, cross-tenant access prevention, new tenant onboarding gaps
5. **Error Handling** — Backend error responses, silent frontend failures, timeout handling, network retry
6. **Date & Timezone** — Client vs server time, day-of-week mismatches, month/year boundaries, DST transitions
7. **Concurrency** — Backend race conditions (double writes, stale reads), frontend race conditions (stale closures, unmounted updates)
8. **Auth & Authorization** — Authentication checks on every route, authorization gaps between roles, password security, token expiry
9. **External API Failures** — What happens when third-party APIs return errors or timeouts
10. **Idempotency** — Can operations be safely retried? Are sync jobs idempotent?

Review all source files.

Format your findings as a markdown document with:
- Executive summary with severity counts table
- Findings grouped by category with severity levels (Critical, High, Medium, Low)
- Each finding should have: file, line number, description, suggested fix
- Use markdown checkboxes so items can be tracked

## Test Script Generation

After identifying findings, generate actual runnable test scripts for the top 5 highest-priority gaps. Write them in the appropriate test framework:
- Python: pytest (place in `tests/` directory)
- TypeScript: vitest (place in `frontend/src/test/` directory)

For each test:
- File path where the test should live
- Full test code (not pseudocode — runnable as-is)
- What it validates and why it matters
- Mark as `## Generated Test: <name>`

Focus test generation on:
1. Financial calculations (forecast accuracy, labor targets, P&L math)
2. Data pipeline integrity (sync idempotency, dedup correctness)
3. API contract validation (response shapes, error handling)
4. Edge cases from findings above

Include the test code in fenced code blocks with the correct language tag.

Output ONLY the findings and test scripts, no title or preamble.
