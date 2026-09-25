FIRST: If review-context.md exists, read it for project context, threat model, and
intentional design decisions. Follow it strictly — do NOT flag intentional decisions.
ALSO: Read existing-issues.md — do NOT report findings already tracked there.
ALSO: Read digest-intelligence.md for emerging threats and patterns to check against.

---

Perform a comprehensive data integrity, database engineering, and financial reconciliation review of this codebase. You are a senior data engineer validating that data pipelines, database schema, and financial data produce accurate, timely results.

Review all source files related to data processing, forecasting, database schema, and reporting.

Check for:

1. **Pipeline Reliability**
   - Are nightly sync jobs idempotent? Can they be safely re-run?
   - Are there silent failure modes where data stops flowing but no alert fires?
   - Are error handling and retry patterns adequate for external API calls (Crumbl, QBO, WIW)?
   - Is there monitoring for data freshness? (e.g., alert if daily_sales hasn't updated by noon)

2. **Forecast Accuracy**
   - Are model outputs validated against actuals anywhere in the code?
   - Are there accuracy metrics being tracked (MAPE, bias, hit rate)?
   - Are there hardcoded constants or magic numbers that should be data-driven?
   - Could stale cached data silently produce wrong forecasts?

3. **Data Consistency**
   - Do different consumers (Labor, Financials, Dashboard) read the same source of truth?
   - Are there duplicate computation paths that could diverge?
   - Are date ranges, timezone handling, and DOW conventions consistent across modules?
   - Are materialized views / caches refreshed appropriately?

4. **Financial Accuracy & Reconciliation**
   - Do P&L calculations match QBO actuals?
   - Does SUM(orders.collected_amount) match daily_sales for the past week? Any drift indicates API formula or timezone issues.
   - Are there orders with collected_amount = 0 that should have revenue (missed Financial API update)?
   - Are refund amounts in order_refunds matching actual Stripe refunds?
   - Are there unbalanced JEs (debits != credits) posted this week?
   - Are Stripe clearing JEs posted within 3 days of the sales JE?
   - Are marketplace orders (DoorDash, UberEats, GrubHub) reconciled against platform reports?
   - Are revenue/cost projections using the correct trailing windows?
   - Are payroll tax multipliers, upcharge values, and other constants current?
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
   - Are there time entries where length_hours = 0 but end_time is set (corrupt data)?
   - Are there days where total labor hours are significantly below historical DOW average for a store (suggests missing punches even if entries exist)?

7. **Schema Changes in This Diff** (whole-schema health is `database-review.md`, run on demand)
   - Does a new or altered table have a primary key, a UNIQUE constraint on its natural or external key, and foreign keys for its `*_id` columns?
   - Is new money stored as `numeric` (never `real`/`double precision`), new instants as `timestamptz`, new business dates as `date`?
   - Does a new query filter or join on a column no index leads with, on a table that is large or growing?
   - Does the diff drop or rename a column that code still reads?
   - Does the diff add a second table, feed or derived copy for a fact that already has a home?

8. **Data Feed Efficiency**
   - Are there API calls fetching data that's already available from another call?
   - Are there row-by-row INSERT loops that could use batch executemany for better throughput?
   - Are there nightly syncs re-fetching unchanged data (e.g., recipe details for cookies already in the DB)?
   - Are there API calls that could use a date range instead of one-call-per-day?
   - Is the trailing window for order/data syncs wider than necessary?
   - Are API calls parallelized across stores where possible?

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

11. **Dashboard Accuracy**
    - Do frontend charts/metrics match backend queries?
    - Are there client-side calculations that could diverge from server-side?
    - Are empty states handled (no data ≠ zero)?

Format your findings as a markdown document with:
- Executive summary (2-3 sentences on overall data health)
- Findings grouped by severity (Critical, High, Medium, Low)
- Each finding should have: file, line number, description, impact on data accuracy, suggested fix
- Use markdown checkboxes so items can be tracked
- End with "Data Health Score" — percentage of data pipelines that are reliable and accurate

Output ONLY the findings, no title or preamble.
