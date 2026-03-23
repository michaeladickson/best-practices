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
- Include a prioritized test recommendations section at the end

Output ONLY the findings, no title or preamble.
