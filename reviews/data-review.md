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
   - Is the cookie_forecasts → forecast_daily_revenue → labor_cache chain consistent?
   - Are cookie lookups using `crumbl_cookie_id` (stable UUID) and NOT cookie names? Name-based lookups break when Crumbl renames cookies.

6. **Webhook & External Sync Integrity**
   - Are there WIW time entries with NULL end_time older than 12 hours? This indicates a dropped Zapier webhook for the clock-out event.
   - Does the gap-fill function `detect_and_fill_missing_clockouts()` in `wiw_sync.py` exist and handle the fallback to scheduled shift end times?
   - Are there time entries where length_hours = 0 but end_time is set (corrupt data)?
   - Are there days where total labor hours are significantly below historical DOW average for a store (suggests missing punches even if entries exist)?

7. **Database Schema Health**
   - Are there tables that exist in the DB but are never referenced in any Python code?
   - Are there API routes or sync functions querying tables that no longer exist (dropped by migrations)?
   - Are there columns that are always NULL or always the same value (dead columns)?
   - Are code references to dropped columns still present? (e.g., `net_sales`, `avg_order_value`, `desserts_sold` were removed from `store_daily_metrics` — verify no code still reads them)
   - Are there missing indexes on columns used in WHERE/JOIN clauses?
   - Are there tables being populated by multiple independent data feeds with overlapping data?
   - Are there physical tables that could be replaced by views over source-of-truth tables?
   - Are there derived tables that can't be re-created from source tables (data only exists in derived form)?

8. **Data Feed Efficiency**
   - Are there API calls fetching data that's already available from another call?
   - Are there row-by-row INSERT loops that could use batch executemany for better throughput?
   - Are there nightly syncs re-fetching unchanged data (e.g., recipe details for cookies already in the DB)?
   - Are there API calls that could use a date range instead of one-call-per-day?
   - Is the trailing window for order/data syncs wider than necessary?
   - Are API calls parallelized across stores where possible?

9. **Schema Evolution & Migration Hygiene**
   - Are migration files applied in sorted order and idempotent (safe to re-run)?
   - Are there CREATE TABLE statements in schema.sql that conflict with migration-created tables?
   - Are foreign key relationships correctly defined for all ID reference columns?
   - Are UNIQUE constraints on all tables to prevent duplicates on re-runs?
   - Are there tables still using patterns from an older architecture?

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
