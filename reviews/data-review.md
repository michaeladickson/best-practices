FIRST: If review-context.md exists, read it for project context, threat model, and
intentional design decisions. Follow it strictly — do NOT flag intentional decisions.
ALSO: Read existing-issues.md — do NOT report findings already tracked there.
ALSO: If digest-intelligence.md exists, read it for emerging threats and patterns
to check against; skip it silently if it is absent.

---

Perform a comprehensive data integrity, database engineering, and financial reconciliation review of this codebase. You are a senior data engineer validating that data pipelines, database schema, and financial data produce accurate, timely results.

Review all source files related to data processing, forecasting, database schema, and reporting.

Check for:

1. **Pipeline Reliability**
   - Are nightly sync jobs idempotent? Can they be safely re-run?
   - Are there silent failure modes where data stops flowing but no alert fires?
   - Are error handling and retry patterns adequate for calls to the project's external data APIs?
   - Is there monitoring for data freshness? (Does anything fail loud when the primary feed stops writing?)

2. **Forecast Accuracy**
   - Are model outputs validated against actuals anywhere in the code?
   - Are there accuracy metrics being tracked (MAPE, bias, hit rate)?
   - Are there hardcoded constants or magic numbers that should be data-driven?
   - Could stale cached data silently produce wrong forecasts?

3. **Data Consistency**
   - Do different consumers of the same fact read the same source of truth?
   - Are there duplicate computation paths that could diverge?
   - Are date ranges, timezone handling, and DOW conventions consistent across modules?
   - Are materialized views / caches refreshed appropriately?

4. **Financial Accuracy & Reconciliation**
   - Do ledger postings tie to their system of record and to any verified baselines or filed figures? The repo's review-context.md names the specific tie-outs.
   - Do independent paths that should agree actually reconcile (an aggregate against its row sums, snapshots against flows, one side of a transfer against the other)?
   - Are there records with a zero or NULL amount that should carry value (a missed upstream update)?
   - Are there unbalanced journal entries (debits != credits)?
   - Are projections using the correct trailing windows, and are domain constants current?
   - Could rounding or type conversion introduce systematic bias?

5. **Data Quality**
   - Are there NULL handling gaps that could produce wrong aggregations?
   - Are unique constraints and dedup logic sufficient to prevent double-counting?
   - Are there orphaned records or referential integrity gaps?
   - Are derived-table chains (source → aggregate → cache) consistent, or can a stage go stale silently?
   - Are entity lookups keyed on stable IDs rather than display names that an upstream system can rename?

6. **Webhook & External Sync Integrity**
   - Are there half-open records (e.g. start without end) older than the expected completion window? That usually means a dropped webhook/event.
   - Does a gap-fill or reconciliation path exist for missed external events, and does it have a sane fallback?
   - Are there records whose duration or amount is zero while their completion is set (corrupt data)?
   - Are there periods where an entity's volume falls well below its own historical norm for that weekday (missing events, even though records exist)?

7. **Schema Changes in This Diff** (whole-schema health is `database-review.md`, run on demand)
   - Does a new or altered table have a primary key, a UNIQUE constraint on its natural or external key, and foreign keys for its `*_id` columns?
   - Is new money stored as `numeric` (never `real`/`double precision`), new instants as `timestamptz`, new business dates as `date`?
   - Does a new query filter or join on a column no index leads with, on a table that is large or growing?
   - Does the diff drop or rename a column that code still reads?
   - Does the diff add a second table, feed or derived copy for a fact that already has a home?

8. **Data Feed Efficiency**
   - Are there API calls fetching data that's already available from another call?
   - Are there row-by-row INSERT loops that could use batch executemany for better throughput?
   - Are there nightly syncs re-fetching reference data that has not changed?
   - Are there API calls that could use a date range instead of one-call-per-day?
   - Is the trailing window for order/data syncs wider than necessary?
   - Are API calls parallelized or batched across entities where the API allows?

9. **Migrations in This Diff** (migration discipline as a whole is `database-review.md`)
   - Is each new migration idempotent and safe to re-run?
   - Is it lock-safe on a large table (`CREATE INDEX CONCURRENTLY`, no rewrite under an exclusive lock, a `lock_timeout`)?
   - Does it edit an already-applied migration instead of adding a new one?

10. **API Integration Health**
    - Are API response schemas being validated or just assumed correct?
    - Are auth tokens being refreshed before expiry (not after failure)?
    - Are API call counts tracked per sync run to detect creep?
    - Are there new fields in API responses we're not capturing (check raw_json for unused fields)?
    - Are date/timezone formats consistent across all API integrations?

11. **Report Accuracy** (dashboards, digests, CLI rollups: whatever the repo presents)
    - Do presented figures match the queries they summarize?
    - Are there client-side or duplicate calculations that could diverge from the source of truth?
    - Are empty states handled (no data ≠ zero), and is a value the source omitted kept as missing rather than read as 0?

Format your findings as a markdown document with:
- Executive summary (2-3 sentences on overall data health)
- Findings grouped by severity (Critical, High, Medium, Low)
- Each finding should have: file, line number, description, impact on data accuracy, suggested fix
- Use markdown checkboxes so items can be tracked
- End with "Data Health Score" — percentage of data pipelines that are reliable and accurate

Output ONLY the findings, no title or preamble.
