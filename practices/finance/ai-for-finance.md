# AI for Finance & CFO Operations

Patterns for applying AI to financial operations, accounting, and CFO workflows. Drawn from crumbl-ops (franchise accounting) and wealth-mgmt (personal investing), plus emerging industry practices.

## Automated Accounting Pipeline

### Invoice Processing (PDF → Books)
```
Gmail inbox → PDF download → AI extraction → Validation → QBO bill posting
```

**Key steps:**
1. **Fetch**: Poll Gmail for invoices from known vendors (Sysco, US Foods, franchising)
2. **Parse**: Table-based PDF extraction (not OCR-only — use layout structure)
3. **Map**: Vendor-specific line item → QBO account mapping via vendor registry
4. **Validate**: Check totals match, flag discrepancies, require human review above threshold
5. **Post**: Create QBO bill + vendor credits atomically

**Lessons learned:**
- Each vendor PDF has different layout — need per-vendor parsers, not a generic one
- Always store raw PDFs in cloud storage for audit trail
- Idempotent posting: check for existing bill by vendor + invoice number before creating

### Journal Entry Automation
```
Daily sales data → JE builder → Balance check → QBO posting
```

- Build balanced debit/credit entries programmatically
- **Never post unbalanced JEs** — builder should refuse and alert
- Use idempotency tags: `"system | store | date"` to prevent duplicate JEs
- Time-of-day matters: Stripe settlement data doesn't finalize until mid-morning

### Month-End Accruals
- Automate recurring accruals (franchising fees, labor estimates, revenue checks)
- Compare actual vs. accrual, flag material variances
- Generate reconciliation reports for review

## AI-Powered Classification

### Transaction Categorization
- Batch transactions through Gemini with household/business context
- Use lifestyle-oriented categories (trips, going-out, kids) not bank categories
- Cache results by transaction ID — most transactions recur
- Validate AI output against valid category pairs
- Rule-based fallback when AI fails

### Email Triage
- Classify incoming emails by category + priority + sentiment
- Route to appropriate workflow (invoice processing, customer response, etc.)
- Generate draft responses with tier-specific tone

## Demand Forecasting

### Feature Engineering
- Historical sales by product, day-of-week, seasonality
- Weather data (Open-Meteo: temperature, precipitation, wind)
- Search trends (Google Trends brand volume)
- Local events (sports schedules, holidays)
- Menu rotation effects (new vs returning products)

### Model Stack
- LightGBM for demand prediction (cookie-level daily forecasts)
- Hand-tuned baseline for comparison (Jaccard similarity between weeks)
- Accuracy tracking: MAPE, MAE, bias by store and product
- Bottom-up revenue: demand x price → monthly revenue projections

## Financial Data Aggregation

### Multi-Source Net Worth
```
Plaid accounts + Manual assets (CSV) + Investment holdings → Unified view
```

- Aggregate across all linked institutions
- Enrich with institution names and account types
- Handle partial failures gracefully (one source down ≠ no data)
- Cache market data with 1-hour TTL

### Macro Analysis
- Pull indicators from FRED (Fed Funds, CPI, unemployment, GDP)
- Fetch market data via yfinance (indices, sector ETFs)
- Build investor profile context for AI analysis
- Generate actionable theses, not generic market commentary

## Compliance & Audit Considerations

- **Audit trail**: Store raw source data (PDFs, API responses, snapshots) separately from processed data
- **Idempotency**: Every financial write should be safely re-runnable
- **Balance checks**: Never post unbalanced entries; alert and halt
- **Segregation**: Per-entity books (each franchise store = separate QBO realm)
- **Retention**: Raw data archives should outlive the processed views

## Where Used

- **crumbl-ops**: Full accounting pipeline (invoices, JEs, month-end, payroll, forecasting)
- **wealth-mgmt**: Transaction categorization, macro analysis, net worth aggregation
