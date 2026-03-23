# Payroll & Labor Patterns

Patterns for building payroll engines, labor cost tracking, and time management integrations.

## Payroll Engine

### Core Requirements
- **Pay period**: Biweekly (most common for hourly + salaried)
- **Overtime**: Follow state law (Kentucky: weekly OT after 40 hours, no daily OT)
- **Tips**: Track and distribute (tip pool vs individual)
- **Integrity checks**: Hours balance, pay rates validated, no negative pay

### Calculation Flow
```
Time entries (from WIW or manual)
  → Group by employee + pay period
  → Calculate regular hours, OT hours
  → Apply pay rates by position
  → Add tip distribution
  → Run integrity checks
  → Generate payroll summary
  → Export to CSV / post to accounting
```

### Overtime Rules
- State-specific (not federal-only)
- Kentucky: OT = hours > 40 in a workweek
- California: OT = hours > 8/day AND > 40/week (double time > 12/day)
- Always verify current state law — rules change

### Multi-Position Handling
- Employee may work multiple positions (shift lead + crew)
- Different pay rates per position
- OT calculated on blended rate or highest rate (state-dependent)
- Track position per time entry, not per employee

## Time & Attendance Integration

### When I Work (WIW) Pattern
- Sync time entries via API or webhook
- Employee + position mapping to internal IDs
- Handle timezone differences (store local time vs UTC)
- Detect schedule vs actual variances

### Data Model
```sql
time_entries (
  employee_id, position_id, store_id,
  clock_in TIMESTAMPTZ, clock_out TIMESTAMPTZ,
  regular_hours DECIMAL, ot_hours DECIMAL,
  tips DECIMAL,
  source TEXT  -- 'wiw', 'manual', 'imported'
)
```

## Labor Cost Analysis

### Metrics
- Labor as % of revenue (by store, by day, by week)
- Cost per labor hour
- Overtime ratio (OT hours / total hours)
- Schedule efficiency (actual vs scheduled hours)

### Forecasting Labor Needs
- Historical demand × labor-per-unit = staffing forecast
- Adjust for day-of-week patterns
- Account for training hours for new hires

## Where Used

- **crumbl-ops**: Full payroll engine with KY OT law, WIW integration, multi-store
