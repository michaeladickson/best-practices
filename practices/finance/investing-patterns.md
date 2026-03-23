# Investing & Wealth Management Patterns

Patterns for building investment analysis tools and personal wealth management platforms.

## Portfolio Data Architecture

### Multi-Source Aggregation
```
Plaid (brokerage accounts)
  + Manual holdings (CSV — 401k, 529, illiquid)
  + Manual assets (CSV — real estate, vehicles, debt)
  = Unified net worth view
```

**Why CSV for manual data**: Non-dev users (spouse, advisor) can maintain in Excel. App reloads on each run. Schema evolves by adding columns.

### Holdings Enrichment
- Plaid returns positions + securities with pricing
- Manual holdings: specify `price_source` (ticker for live, `manual_price` for illiquid)
- Use yfinance for real-time pricing on tickers
- Fallback tickers when primary fails (e.g., `DX-Y.NYB` → `UUP` proxy)

### Account Types
- Taxable brokerage
- Tax-deferred (401k, Traditional IRA)
- Tax-free (Roth IRA, Roth 401k)
- Education (529 plans)
- Real estate (primary residence, investment properties)
- Debt (mortgage, auto loans — tracked as negative assets)

## Macro Analysis Pipeline

### Data Sources
- **FRED API**: Fed Funds Rate, CPI, Unemployment, GDP, credit spreads
- **yfinance**: S&P 500, Nasdaq, Russell 2000, sector ETFs, commodities, bonds, VIX
- **RSS feeds**: Macro newsletters (The Macro Compass, Kyla Scanlon, Net Interest)

### Investor Profile for AI Context
```python
INVESTOR_PROFILE = """
- Time horizon: 20+ years (accumulation phase)
- Risk tolerance: moderate-aggressive
- Portfolio: 70% equities, 20% real estate, 10% fixed income
- Tax situation: high income, maximize tax-advantaged accounts
- Geographic bias: US-heavy, increasing international
- Key interests: factor investing, tax-loss harvesting, real estate leverage
"""
```

Inject this into every AI analysis prompt — makes advice contextual, not generic.

### Thesis Generation
- Score relevance to investor profile (1-10)
- Categorize: macro shift, sector rotation, risk flag, opportunity
- Include confidence level and time horizon
- Require actionable takeaway, not just commentary

## Spending Analysis

### Lifestyle Categories (Not Bank Categories)
```
TRIPS           → Flights, Hotels, Activities, Dining-on-trip
GOING OUT       → Restaurants, Bars, Entertainment, Events
EVERYDAY DINING → Coffee, Fast food, Delivery, Groceries-prepared
KIDS            → Childcare, Activities, Clothing, Education
FITNESS         → Gym, Classes, Equipment, Supplements
HOME            → Mortgage, Utilities, Maintenance, Furnishing
TRANSPORTATION  → Gas, Car payment, Insurance, Parking, Uber
SHOPPING        → Clothing, Electronics, Amazon, Gifts
SUBSCRIPTIONS   → Software, Streaming, Memberships
HEALTHCARE      → Medical, Dental, Vision, Pharmacy, Insurance
```

**Why lifestyle over bank categories**: "What am I spending on trips?" is a more useful question than "What's in the travel category?" A restaurant charge at Disney is a trip expense, not dining.

### Merchant Context
- Map known merchants to correct categories: "Otf Tenleytown" = Orangetheory Fitness
- Location context helps: charges near home vs. on-trip
- Trip detection: cluster charges by date + location

## Plaid Integration Patterns

### OAuth Flow
1. Create link token (server-side, with redirect URI)
2. Open Plaid Link (client-side)
3. Exchange public token for access token
4. Encrypt and store access token

### Pagination
```python
def get_transactions(access_token, start_date, end_date):
    offset = 0
    all_txns = []
    while True:
        response = client.transactions_get(access_token, start_date, end_date, offset=offset, count=500)
        all_txns.extend(response.transactions)
        if len(all_txns) >= response.total_transactions:
            break
        offset = len(all_txns)
    return all_txns
```

### Institution Quirks
- Some institutions require OAuth redirect (Schwab, Chase)
- Token refresh needed periodically (Plaid handles automatically for most)
- Investment holdings API is separate from transactions API
- Personal finance categories from Plaid's enhanced categorization can supplement AI categorization

## Client-Ready Patterns

For building finance tools for clients:

### Multi-Tenant Considerations
- Separate data by client/entity at the database level
- Per-client configuration (chart of accounts, categories, thresholds)
- Role-based access (owner sees everything, bookkeeper sees assigned entities)
- Audit logging on all financial writes

### Report Generation
- Automate P&L, Balance Sheet, Cash Flow extraction from accounting system
- AI-generated executive summaries comparing period-over-period
- Variance analysis: actual vs. budget/forecast with explanations
- Email delivery on schedule (weekly, monthly)

### Data Quality
- Reconciliation checks: bank balance vs. book balance
- Duplicate detection on transactions and journal entries
- Stale data alerts: flag accounts not synced in N days
- Data lineage: trace any number back to its source

## Where Used

- **wealth-mgmt**: Full implementation (Plaid, spending analysis, macro digest, manual assets)
- **crumbl-ops**: Accounting pipeline, forecasting, multi-store financial reporting
