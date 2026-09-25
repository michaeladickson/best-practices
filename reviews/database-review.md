FIRST: If review-context.md exists, read it for project context and intentional
design decisions. Follow it strictly — do NOT flag intentional decisions.
ALSO: Read existing-issues.md if present — do NOT report findings already tracked there.

---

Perform a **database structure and performance review** of this repository, as a senior
PostgreSQL engineer would: someone who has run production Postgres for years and has
seen what "it works" hides. The question to answer is not "does the schema run" but
"would an experienced DB engineer sign off on it, or read it as generated without
understanding?" Be calibrated in both directions: name real strengths with evidence,
and do not inflate or pad findings.

**Evidence rule.** Grade from measurements, not impressions. A schema file shows what
was declared; the database's own statistics show what actually happens. Where live
read-only access exists, Part A is mandatory and outranks anything inferred from code.
Where it does not, say so in the scorecard and mark every performance finding as
*inferred*.

## Part A — Live evidence (read-only)

Connect with a read-only session (`default_transaction_read_only=on`) and a statement
timeout. Never print the connection string. Record when statistics were last reset
(`pg_stat_database.stats_reset`); every count below is "since then".

1. **Where the reads go.** From `pg_stat_user_tables`: the largest tables by total
   size, and for each table over ~10k rows, `seq_scan`, `seq_tup_read`, `idx_scan`.
   A large table with thousands of sequential scans, each reading most of the table,
   is the single most useful performance finding a review can produce. Then look at
   that table's indexes: an index exists but is not used means the queries filter on
   something it does not lead with, or wrap the column in a function or cast.
2. **Query-level visibility.** Is `pg_stat_statements` installed? Is
   `log_min_duration_statement` set? Is `track_io_timing` on? If none are, nobody can
   name the slow queries, and that is a finding in itself: performance is unmeasured,
   not good.
3. **Cache hit ratio** from `pg_statio_user_tables` (heap and index). Under ~0.99 for
   an OLTP workload, compare database size with `shared_buffers` and the instance
   memory before blaming queries.
4. **Index hygiene.** Unused non-unique indexes (`idx_scan = 0`); duplicate indexes
   with an identical key (often a plain index re-created beside a UNIQUE constraint
   that already provides it); prefix-redundant indexes (`(a)` beside `(a, b)`); foreign
   keys whose columns lead no index. On a large, write-heavy table, count its indexes:
   each one is paid on every insert and update.
5. **Guard rails in server settings.** Server-default `statement_timeout` and
   `idle_in_transaction_session_timeout` (check `source`, not the value your own
   session set); `max_connections` against the application's real peak.
6. **Vacuum health.** Tables with a dead-tuple ratio above ~20%, and large tables
   whose last autovacuum is weeks old.
7. **Debris.** Tables without a primary key; backup or dated copies
   (`*_bak_*`, `*_old`, `*_YYYYMMDD`) left in the production schema.

## Part B — Structure and access (static)

For each area: current state, grade **Good / Gap / Missing**, concrete fix with
file/path. Count; do not characterize without a number.

1. **Types that match the data.** Money in `numeric` with a declared scale, never
   `real`/`double precision` (a `real` holds about 7 significant digits: $123,456.78
   does not survive a round trip). Instants in `timestamptz`; business dates in `date`,
   not text. JSON only where the shape is genuinely open, not as a place to hide
   relational data.
2. **Keys and constraints.** A primary key on every table. A UNIQUE constraint on every
   natural or external identifier, so re-syncs cannot duplicate rows. Foreign keys
   where relationships exist: compare the FK count with the number of `*_id` columns
   pointing at another table. NOT NULL and CHECK constraints for invariants the code
   otherwise assumes silently.
3. **Modeling.** One home per fact: the same quantity stored in several tables with no
   rule for which wins is how two reports disagree. Naming consistency. Derived or
   summary tables: what refreshes them, and what detects when they drift from source.
   Time-series tables large enough to warrant partitioning or a retention policy.
4. **Migration discipline.** Transactional and idempotent migrations; lock-safe changes
   on large tables (`CREATE INDEX CONCURRENTLY`, no table rewrite under an exclusive
   lock during business hours, a `lock_timeout` so a blocked `ALTER` fails instead of
   queuing every query behind it); whether the schema can be rebuilt from source and
   migrations are exercised anywhere before production; how drift between the
   migration history and the live schema is detected. Count the fix-up migrations (renames, re-adds, drops of earlier
   work): a high share is the clearest sign of schema changes made without a design.
5. **Connections and transactions.** Pooling appropriate to the runtime (serverless
   instances multiply connections); what happens when the pool is exhausted (queue or
   500?) and whether request concurrency exceeds pool size; where transactions begin
   and end; long-running transactions in batch jobs, and transactions held open across
   network or LLM calls; idempotent writes (`ON CONFLICT` on a real natural key).
   Read the connection wrapper's exit path: a failed `commit()` that is logged and
   swallowed turns "unknown" into "success". Look for session-level `SET` (not
   `SET LOCAL`) on pooled connections, which leaks into the next borrower.
6. **Query patterns.** Queries inside loops (N+1); row-by-row inserts where a batch
   (`execute_values`, `COPY`) belongs; unbounded reads of growing tables; aggregation
   done in application code that belongs in SQL; filters that defeat an index
   (functions or casts on an indexed column, a leading column skipped).
7. **Safety.** Values interpolated into SQL strings (f-strings, `%` formatting,
   concatenation) rather than bound parameters; identifiers composed without a safe
   quoting helper.
8. **Correctness hazards.** Business-date arithmetic on UTC timestamps (a store's day
   is local): count `CURRENT_DATE` / `now()::date` in SQL when the session timezone is
   UTC; float arithmetic on money in application code; concurrent jobs writing the
   same rows.
9. **Tests against a real database.** Do tests run the actual SQL against Postgres, or
   mock the connection? Is any query plan or query count pinned by a test?

## What separates deliberate from generated

Call these out explicitly, in either direction, with evidence:

- **Generated without understanding:** indexes re-created beside the UNIQUE
  constraints that already provide them; clusters of overlapping indexes on one table;
  float money on some tables and numeric on their siblings; backup tables left in the
  production schema; fix-up migrations far outnumbering design changes; the same
  helper or query written several times; conventions documented but not applied.
- **Deliberate and experienced:** natural keys enforced with UNIQUE and used in
  `ON CONFLICT`; conventions written down and followed; migrations with a hygiene gate;
  a documented reason for each denormalization; performance claims backed by a
  measurement.

Reference standard: `best-practices/practices/architecture/database-patterns.md`.
This complements `reviews/data-review.md` (pipeline freshness, reconciliation,
financial accuracy); focus here on schema design and database performance, and don't
duplicate its findings.

Format your findings as a markdown document with:
- A three-sentence verdict, calibrated (no superlatives): would a senior DB engineer
  sign off, and what is the one change that would most move that answer?
- The Part A evidence as a short table (metric → value → what it means), with the
  statistics-reset date.
- A one-line scorecard: count of Good / Gap / Missing across the 9 Part B areas.
- Findings grouped by priority (High / Medium / Low). Money stored as float, missing
  natural-key uniqueness, and a large table scanned sequentially at volume rank High.
- Each finding: area, evidence (file:line, table name, or the measured number), grade,
  concrete fix, and the migration or query that would implement it.
- Use markdown checkboxes so items can be tracked.

Output ONLY the findings, no title or preamble.
