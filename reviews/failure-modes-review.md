FIRST: If review-context.md exists, read it for project context and intentional
design decisions. Follow it strictly — do NOT flag intentional decisions.
ALSO: Read existing-issues.md if present — do NOT report findings already tracked there.

---

Perform a **failure-modes review** of this system, as a senior site reliability engineer
would: someone who assumes every dependency will fail and asks what happens next. The
question is not "is there retry logic" but "when X is down for an hour, or a day, or
returns wrong data, what does the business see, how soon does a human know, and what
repairs itself?" Be calibrated in both directions: name real strengths with evidence,
and do not inflate findings.

**Evidence rule.** Grade from what the running system records, not from what the code
intends. Where live read-only access exists (job execution history, scheduler state,
alert policies, notification channels, error logs, backup configuration, the app's own
failure tables), Part A is mandatory and outranks anything inferred from code. The
past is evidence too: the incident log and post-mortems are the best test set a review
can have.

## Part A — Inventory and measure

1. **Dependency inventory.** Every external system the product depends on: data
   sources (POS, accounting, payroll, banking, suppliers), platform services
   (database, object storage, secrets, scheduler), outbound channels (email, chat,
   SMS), and model APIs. For each: what calls it, how often, and what business
   output depends on it.
2. **Run history.** For each scheduled job: executions in the last 30 days, how many
   failed, how many timed out, the longest gap between successful runs. A job that
   "succeeds" while its steps fail is worse than one that fails loudly: find out which
   kind each job is.
3. **Detection.** List every alert that exists: monitoring policies, uptime checks,
   log-based alerts, the app's own health or data-quality checks. For each: what
   condition fires it, where it goes, and whether it has ever fired. Then measure
   error volume in the logs over the last week against how many alerts fired.
4. **Recovery posture.** Backup configuration and point-in-time recovery read from the
   live instance (not the docs); the last rehearsed restore; how failed work is retried
   or backfilled; which operations are idempotent.
5. **Incident replay.** For each incident in the log or post-mortems from the last
   ~90 days: how long between onset and detection, who detected it (a human, a
   customer, an alert, a check), and **would it be detected today, by what, and how
   fast?** An incident class with no automated detector today is the most important
   thing this review can find.

## Part B — Grade the failure handling (static and live)

For each area: current state, grade **Good / Gap / Missing**, concrete fix with
file/path. Count; do not characterize without a number.

1. **Timeouts.** Every outbound call has a bounded timeout (HTTP, database, model APIs,
   subprocesses). An unbounded call turns a slow dependency into a hung job.
2. **Retries.** Retries only on retryable errors, with backoff and a cap; never on
   non-idempotent writes without an idempotency key. Watch for retry-inside-retry
   multiplication.
3. **Partial failure.** One failing store, org, vendor or step: does it stop the rest,
   or is it isolated and reported? Is a partial run distinguishable from a full one?
4. **Silent failure.** Paths where an error is caught, logged and forgotten; empty
   results treated as "nothing to do"; a job that exits 0 after its data stopped
   flowing. Data freshness checks: does anything alert when a table stops updating?
5. **Wrong data, not missing data.** A dependency that returns plausible but wrong
   data (a changed field, a partial page, a timezone shift) is the failure retries
   cannot fix. What validates inputs and outputs against invariants (reconciliation,
   totals, row counts versus yesterday)?
6. **Idempotency and repair.** Can every job be re-run safely for a past date? Is
   there a backfill path, and is it the same code as the nightly or a separate script?
7. **Alert quality.** Do alerts reach a human who will act, on a channel they watch?
   Noise ratio: alerts that fire and are ignored train people to ignore the real one.
   Is there a dead-man's switch for the alerting itself?
8. **Blast radius and shared limits.** Shared credentials, rate limits and quotas
   across stores, orgs or jobs; one runaway consumer exhausting a shared limit; a
   single database or instance whose failure takes everything down.
9. **Degraded operation.** When a source is down, does the product show stale data
   labeled as stale, or show nothing, or show wrong numbers as if fresh?

## What separates deliberate from generated

Call these out explicitly, in either direction, with evidence:

- **Generated without understanding:** bare `except` blocks that log and continue;
  retry decorators on everything including writes; timeouts on some clients and not
  others; alerts defined but routed nowhere; a "health check" that checks the process,
  not the data; post-mortems whose action items never became a detector.
- **Deliberate and experienced:** each incident class turned into an automated check
  that would have caught it; failures isolated per unit and reported as partial;
  freshness monitored per source; alerting that is itself monitored; a rehearsed
  restore with a measured time.

Reference: `reviews/data-review.md` covers pipeline freshness and reconciliation in
the week's diff; `reviews/devops-review.md` covers deployment and secrets. Focus here
on the system's behavior under failure, and do not duplicate their findings.

Format your findings as a markdown document with:
- A three-sentence verdict, calibrated: if the most important dependency failed
  tonight, when would a human find out, and what one change would shorten that most?
- The Part A dependency inventory as a table (dependency → what depends on it → timeout /
  retry / isolation → detection → measured failures in 30 days).
- The incident replay as a table (incident → detected by, after how long → detected
  today by what, how fast).
- A one-line scorecard: count of Good / Gap / Missing across the 9 Part B areas.
- Findings grouped by priority (High / Medium / Low). An incident class that would
  still go undetected today, and any silent-failure path on money or payroll data,
  rank High.
- Each finding: area, evidence (file:line, job name, measured count), grade, concrete fix.
- Use markdown checkboxes so items can be tracked.

Output ONLY the findings, no title or preamble.
