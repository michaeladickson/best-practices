FIRST: If review-context.md exists, read it for project context and intentional
design decisions. Follow it strictly — do NOT flag intentional decisions.
ALSO: Read existing-issues.md if present — do NOT report findings already tracked there.

---

Perform a **tenant isolation review** of this repository, as a senior SaaS platform
engineer would before a second paying customer goes live. The question: can one
tenant's data, configuration, credentials, messages or failures reach another tenant,
and if so, what is the one line of code standing in the way? Be calibrated in both
directions: name real strengths with evidence, and do not inflate findings.

**Evidence rule.** Grade from what the running system does, not from what the design
doc says. Where live read-only access exists (database catalog, cloud IAM, secret and
bucket listings), Part A is mandatory and outranks anything inferred from code. Where it
does not, say so in the scorecard and mark those findings *inferred*.

## Part A — Establish the model, then measure it

1. **Name the isolation model.** Silo (database or project per tenant), bridge (schema
   per tenant), or pool (shared tables with a tenant key and row-level security), or a
   mix. Name the shared layer too: app tier, caches, storage, queues, schedulers,
   outbound channels, third-party credentials. Most leaks happen in the shared layer of
   a silo design, because the silo makes people stop looking.
2. **Inventory tenants as they actually exist.** Databases or schemas present, tenant
   registry rows, deployed services and jobs per tenant, secrets per tenant. Compare
   with the documented list. A tenant that exists in one place and not another is a
   finding.
3. **Where the boundary is enforced.** For each layer, find the exact mechanism: a
   connection string chosen per tenant, a `search_path`, an RLS policy, a mandatory
   scope argument, an IAM condition. Then find every path that bypasses it: direct
   `connect()` calls, scripts, admin tools, background jobs.
4. **Credentials and identity.** Per tenant: which service account runs its workload,
   which secrets it can read, which database roles it can use. Measure it: list the
   grants and look for any principal that can read two tenants' secrets or connect to
   two tenants' databases. Project-wide roles count as access to every tenant.

## Part B — Grade the boundary (static)

For each area: current state, grade **Good / Gap / Missing**, concrete fix with
file/path. Count; do not characterize without a number.

1. **Tenant resolution.** How each request, job run and CLI invocation learns which
   tenant it serves. Is it explicit and required, or defaulted? What happens when it
   is missing: an error, or a silent fall-back to the first or "home" tenant? A
   default tenant is the most common silo leak.
2. **Data access.** Every query path that can reach tenant data without passing through
   the boundary mechanism. In pooled designs, every query that omits the tenant key;
   in silo designs, every connection opened without the tenant's resolver.
3. **Shared application state.** Module-level globals, `lru_cache`/memoization, in-process
   caches, singletons and connection pools keyed without the tenant. A cache keyed on
   `store_id` alone is safe only if store IDs can never collide across tenants: check.
4. **Storage and files.** Bucket and path layout, temp directories, generated reports
   and exports, signed URLs. Is the tenant in the path, and is access checked, or only
   implied by an unguessable name?
5. **Outbound channels.** Email, Slack, SMS, webhooks, notifications: is the recipient
   resolved from the tenant's own configuration, or can a shared default channel or
   address receive another tenant's content? A message to the wrong customer is a
   leak even when the database is perfectly isolated.
6. **Scheduled and background work.** Does each job run per tenant with its own
   identity and configuration, and does a failure or runaway in one tenant's job stay
   there (quotas, rate limits on shared third-party credentials, shared queues)?
7. **Configuration and reference data.** What each tenant inherits from the operator's
   own setup (chart of accounts, rates, templates, store lists). Inherited config is a
   correctness leak: the tenant runs on someone else's numbers. Separate genuinely
   shared reference data from tenant data that was copied by accident.
8. **Operator and admin paths.** Scripts, migrations, backfills and support tools that
   take a tenant argument: do they default to one tenant, and can one run against the
   wrong tenant without a confirmation? Are migrations applied to every tenant, and is
   drift between tenants detected?
9. **Lifecycle.** Per-tenant backup and restore (tested, not assumed), export, deletion,
   and an audit trail of who accessed which tenant's data.

## What separates deliberate from generated

Call these out explicitly, in either direction, with evidence:

- **Generated without understanding:** tenant chosen by a default or an environment
  variable with a fallback; isolation that holds only because every caller remembers a
  filter; the operator's own IDs, addresses or channels hard-coded in shared code;
  "multi-tenant" in the docs with one tenant's assumptions in the code.
- **Deliberate and experienced:** the boundary enforced by one mechanism that fails
  closed (wrong or missing tenant raises); a test that proves a second tenant cannot see
  the first; per-tenant identities and secrets; the shared layer inventoried and each
  item justified.

Reference: `reviews/security-review.md` covers authentication and injection generally;
`reviews/database-review.md` covers schema and performance. Focus here on the tenant
boundary and do not duplicate their findings.

Format your findings as a markdown document with:
- A three-sentence verdict, calibrated: could a second tenant go live safely today, and
  what is the one change that would most reduce cross-tenant risk?
- The Part A model and inventory as a short table (layer → isolation mechanism →
  measured state), with how each item was verified.
- A one-line scorecard: count of Good / Gap / Missing across the 9 Part B areas.
- Findings grouped by priority (High / Medium / Low). Any path by which one tenant's
  data or messages can reach another tenant ranks High, even if it has not happened.
- Each finding: area, evidence (file:line, grant, bucket path, or measured count),
  grade, concrete fix.
- Use markdown checkboxes so items can be tracked.

Output ONLY the findings, no title or preamble.
