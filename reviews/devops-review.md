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

4. **Database & Infrastructure**
   - Are database connections properly pooled and recycled?
   - Are migrations tested before production application?
   - Is there a backup and recovery plan for Cloud SQL?
   - Are indexes adequate for current query patterns? Any missing indexes for new tables?

5. **CI/CD Pipeline**
   - Do builds include type checking and basic validation?
   - Are there tests that run before deploy?
   - Is the build reproducible (pinned dependencies, locked versions)?
   - Are GitHub Actions workflows efficient (caching, parallelism)?

6. **Scaling Readiness**
   - As we add stores (3 → 10+), what breaks first?
   - Are sync jobs parallelized per store or sequential?
   - Are API queries bounded or could they OOM with more data?
   - Are Cloud Run concurrency and memory limits appropriate?

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
