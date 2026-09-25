On-demand audit prompt — not in the scheduled rotation since 2026-07-26; paste into a session or dispatch manually.

FIRST: If review-context.md exists, read it for project context, threat model, and
intentional design decisions. Follow it strictly — do NOT flag intentional decisions.
ALSO: Read existing-issues.md — do NOT report findings already tracked there.
ALSO: Read digest-intelligence.md for emerging threats and patterns to check against.

---

Perform a comprehensive DevOps and infrastructure review of this codebase. You are a senior SRE evaluating deployment reliability, monitoring coverage, and operational readiness.

Review all source files, configuration files, Dockerfiles, CI/CD workflows, and deployment scripts.

Check for:

1. **Deployment Reliability**
   - Can deployments be rolled back safely?
   - Are there health checks that catch bad deploys before traffic is routed?
   - Is the deployment process documented and repeatable?
   - Are there race conditions between sync jobs and API deployments?

2. **Secret & Credential Management**
   - Are secrets properly managed via Secret Manager (not env vars or .env files)?
   - Are OAuth tokens auto-refreshed or do they require manual intervention?
   - Is there a rotation schedule for API keys and service account credentials?
   - Could an expired token cause silent data loss?

3. **Monitoring & Alerting**
   - What breaks without anyone knowing? Identify blind spots.
   - Are nightly sync failures alerted on? How quickly?
   - Is there monitoring for data freshness (e.g., last successful daily_sales sync)?
   - Are Cloud Run cold start times, error rates, and latency tracked?

4. **Database Operations** (schema, indexing, pooling and migration discipline are
   `database-review.md`; do not duplicate them here)
   - Are automated backups enabled on the instance, verified from its live config rather than the docs?
   - Has a restore been rehearsed, and how long did it take? Per tenant, if tenants share an instance?
   - Is point-in-time recovery on, and is the instance tier sized for its database?

5. **CI/CD Pipeline**
   - Do builds include type checking and basic validation?
   - Are there tests that run before deploy?
   - Is the build reproducible (pinned dependencies, locked versions)?
   - Are GitHub Actions workflows efficient (caching, parallelism)?

6. **Scaling Readiness**
   - The platform currently supports 3 stores with 7 more under contract (10+ by mid-2026). What breaks first?
   - Are sync jobs parallelized per store or sequential?
   - Are API queries bounded or could they OOM with more data?
   - Are Cloud Run concurrency and memory limits appropriate?
   - Are there hardcoded store lists or assumptions about store count?

7. **Cost Management**
   - Are Cloud Run instances scaling to zero when idle?
   - Is the Cloud SQL connection pool sized correctly (not holding unnecessary idle connections)?
   - Are there unnecessary Cloud Storage operations (e.g., old GCS upload patterns)?
   - Are nightly sync durations trending up? Could indicate inefficient queries or API call creep.
   - Are there failed Cloud Run job executions that ran full duration before failing (wasted compute)?
   - Are there external API calls that could be cached or batched to reduce volume?
   - Is the Cloud SQL tier appropriate for current usage (not over-provisioned)?

Format your findings as a markdown document with:
- Executive summary (2-3 sentences on operational readiness)
- Findings grouped by severity (Critical, High, Medium, Low)
- Each finding should have: file or config, description, blast radius (what breaks if this fails), suggested fix
- Use markdown checkboxes so items can be tracked
- End with "Operational Readiness Score" — Red/Yellow/Green with justification

Output ONLY the findings, no title or preamble.
