# Payroll Testing

Financial calculations require higher precision and more thorough testing than typical application code. Rounding errors, edge cases around overtime boundaries, and tip distribution logic can result in real payroll discrepancies.

## Use Decimal, Not Float

All monetary calculations must use `Decimal` with explicit `ROUND_HALF_UP` rounding. Python's built-in `round()` uses banker's rounding (`ROUND_HALF_EVEN`), which produces unexpected results for payroll:

```python
from decimal import Decimal, ROUND_HALF_UP

# CORRECT — Decimal with explicit rounding
hourly_rate = Decimal("15.50")
hours = Decimal("38.75")
gross = (hourly_rate * hours).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
# Result: Decimal('600.63')

# WRONG — float arithmetic with round()
hourly_rate = 15.50
hours = 38.75
gross = round(hourly_rate * hours, 2)
# May produce incorrect results due to float representation
```

### Why It Matters

```python
# round() uses ROUND_HALF_EVEN (banker's rounding)
round(2.5)    # 2  (rounds to even)
round(3.5)    # 4  (rounds to even)

# Decimal ROUND_HALF_UP matches payroll expectations
Decimal("2.5").quantize(Decimal("1"), rounding=ROUND_HALF_UP)  # 3
Decimal("3.5").quantize(Decimal("1"), rounding=ROUND_HALF_UP)  # 4
```

## Overtime Edge Cases

### Weekly Boundary

Employees working across a pay period boundary can have OT in one week but not the other. Test both weeks independently:

```python
def test_ot_split_across_weeks():
    """Week 1: 45 hours (5 OT), Week 2: 35 hours (0 OT)."""
    entries = [
        # Week 1: Mon-Fri, 9 hours/day = 45 hours
        make_entry("2026-03-16", hours=Decimal("9")),  # Mon
        make_entry("2026-03-17", hours=Decimal("9")),
        make_entry("2026-03-18", hours=Decimal("9")),
        make_entry("2026-03-19", hours=Decimal("9")),
        make_entry("2026-03-20", hours=Decimal("9")),
        # Week 2: Mon-Fri, 7 hours/day = 35 hours
        make_entry("2026-03-23", hours=Decimal("7")),
        make_entry("2026-03-24", hours=Decimal("7")),
        make_entry("2026-03-25", hours=Decimal("7")),
        make_entry("2026-03-26", hours=Decimal("7")),
        make_entry("2026-03-27", hours=Decimal("7")),
    ]
    result = calculate_payroll(entries, rate=Decimal("15.00"))
    assert result.regular_hours == Decimal("75")
    assert result.ot_hours == Decimal("5")
    assert result.ot_pay == Decimal("5") * Decimal("15.00") * Decimal("1.5")
```

### Multi-Position Rates

When an employee works multiple positions at different rates, OT applies to the blended rate (or highest rate, depending on state law):

```python
def test_multi_position_ot():
    """Crew at $13, shift lead at $16, 42 total hours."""
    entries = [
        make_entry(position="crew", hours=Decimal("30"), rate=Decimal("13.00")),
        make_entry(position="shift_lead", hours=Decimal("12"), rate=Decimal("16.00")),
    ]
    result = calculate_payroll(entries)
    # Blended rate = (30*13 + 12*16) / 42 = $13.857...
    # OT (2 hours) at 1.5x blended rate
    assert result.ot_hours == Decimal("2")
```

### Partial Weeks

New hires or terminations mid-week must still calculate OT correctly for the partial week:

```python
def test_partial_week_no_false_ot():
    """Employee works Wed-Sat only, 10 hrs/day = 40 hrs, no OT."""
    entries = [make_entry(day, hours=Decimal("10")) for day in wed_to_sat]
    result = calculate_payroll(entries, rate=Decimal("14.00"))
    assert result.ot_hours == Decimal("0")
```

## Tip Distribution

Tips are distributed proportionally by hours worked. Managers are excluded from the tip pool:

```python
def test_tip_distribution():
    """Tips split proportionally by hours, managers excluded."""
    employees = [
        {"id": "emp1", "hours": Decimal("30"), "is_manager": False},
        {"id": "emp2", "hours": Decimal("20"), "is_manager": False},
        {"id": "emp3", "hours": Decimal("40"), "is_manager": True},  # excluded
    ]
    total_tips = Decimal("500.00")
    dist = distribute_tips(employees, total_tips)

    # Only emp1 + emp2 in pool (50 hours total)
    assert dist["emp1"] == Decimal("300.00")  # 30/50 * 500
    assert dist["emp2"] == Decimal("200.00")  # 20/50 * 500
    assert "emp3" not in dist
```

### Tip Rounding

When tip splits produce remainders, assign the extra penny to the employee with the most hours:

```python
def test_tip_rounding_remainder():
    """$100 split 3 ways = $33.33 + $33.33 + $33.34."""
    employees = [
        {"id": "a", "hours": Decimal("10"), "is_manager": False},
        {"id": "b", "hours": Decimal("10"), "is_manager": False},
        {"id": "c", "hours": Decimal("10"), "is_manager": False},
    ]
    dist = distribute_tips(employees, Decimal("100.00"))
    total = sum(dist.values())
    assert total == Decimal("100.00")  # Must sum exactly
```

## Validation Before Go-Live

Always test payroll calculations against known good outputs before processing real payroll:

```python
def test_against_known_payroll():
    """Compare engine output to a manually verified pay period."""
    known = load_known_payroll("2026-03-01_to_2026-03-14.json")
    computed = run_payroll(known.time_entries, known.rates, known.tips)

    for emp_id, expected in known.expected_pay.items():
        actual = computed[emp_id]
        assert actual.gross == expected.gross, (
            f"{emp_id}: expected {expected.gross}, got {actual.gross}"
        )
        assert actual.ot_pay == expected.ot_pay
        assert actual.tip_amount == expected.tip_amount
```

Keep at least two known-good pay periods as test fixtures. When the payroll engine changes, re-verify against these fixtures before deploying.

## Where Used

- **crumbl-ops**: `src/ops/payroll.py` (payroll engine), `tests/test_payroll.py` (payroll test suite)
