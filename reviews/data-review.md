Perform a comprehensive data integrity and analytics review of this codebase. You are a senior data engineer validating that data pipelines, forecasts, and dashboards produce accurate, timely results.

Review all source files related to data processing, forecasting, and reporting.

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

4. **Financial Accuracy**
   - Do P&L calculations match QBO actuals?
   - Are revenue/cost projections using the correct trailing windows?
   - Are payroll tax multipliers, upcharge values, and other constants current?
   - Could rounding or type conversion introduce systematic bias?

5. **Data Quality**
   - Are there NULL handling gaps that could produce wrong aggregations?
   - Are unique constraints and dedup logic sufficient to prevent double-counting?
   - Are there orphaned records or referential integrity gaps?
   - Is the cookie_forecasts → forecast_daily_revenue → labor_cache chain consistent?

6. **Webhook & External Sync Integrity**
   - Are there WIW time entries with NULL end_time older than 12 hours? This indicates a dropped Zapier webhook for the clock-out event. Run: `SELECT store_id, work_date, COUNT(*) FROM wiw_time_entries WHERE end_time IS NULL AND start_time < NOW() - INTERVAL '12 hours' GROUP BY store_id, work_date ORDER BY work_date DESC`
   - Does the gap-fill function `detect_and_fill_missing_clockouts()` in `wiw_sync.py` exist and handle the fallback to scheduled shift end times?
   - Are there time entries where length_hours = 0 but end_time is set (corrupt data)?
   - Are there days where total labor hours are significantly below historical DOW average for a store (suggests missing punches even if entries exist)?

6. **Dashboard Accuracy**
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
