# Data-Quality Checks

Tests prove the code is correct about data it was handed. Data-quality (DQ) checks
ask whether the data itself is right — in production, on a schedule, forever.

They are for **silent** failures: the ones that produce no exception and no stack
trace, just numbers that are wrong and look fine. A transaction attributed to the
wrong household member. A sync that stopped reporting three weeks ago. A re-import
that ran twice. Nothing about any of those raises.

crumbl-ops runs 179 such checks nightly; wealth-mgmt runs 10. The gap between a
check that protects and a check that merely exists is almost entirely below.

## The result contract

Every check returns a dict. Write the contract down once, in a constructor, and
enforce it — the alternative is 286 hand-built dicts and a consumer that guesses.

```python
def dq_result(check: str, passed: bool, *, detail=None, skipped=False, **diagnostics) -> dict:
    """- check    (required) name, WITHOUT any `check_` prefix
       - passed   (required) THE PASS/FAIL KEY IS `passed`, NEVER `status`
       - detail   an ACTIONABLE remediation string — name the fix, not the symptom
       - skipped  could not run (no DB yet, empty window); carries passed=True but
                  is reported separately so "no data" never reads as "healthy"
       - **diagnostics  counts, samples, thresholds — printed on failure
    """
    if check.startswith("check_"):
        raise ValueError(f"{check!r} still has its prefix")
    for reserved in ("check", "passed", "status"):
        if reserved in diagnostics:
            raise ValueError(f"{reserved!r} is not a diagnostic key")
    result = {"check": check, "passed": bool(passed) or skipped}
    ...
```

**Why `status` is called out.** In crumbl-ops the producers were never wrong — all
286 return sites used `passed`. `scripts/dq_preflight.py` read `result["status"]`,
found nothing, and reported every check as green. A deploy gate that could not see
a single failure shipped, and adversarial review caught it, not a test. The bug was
a *consumer* guessing at an unwritten contract, so pin both sides:

```python
def test_consumers_read_passed_not_status():
    for path in (REPO/"scripts"/"dq_preflight.py", REPO/"src"/.../"runner.py"):
        assert 'result["status"]' not in path.read_text()
```

A static AST sweep enforces the producer side across every check at once, offline.
Prefer it to a runtime sweep: running all the checks needs a live DB, so a runtime
test only ever covers the checks that already have fixtures — and the contract's
failure mode is the check nobody exercised.

## Calibrate in both directions

**The single highest-value rule.** A check must be quiet on today's healthy data
*and* loud on the failure it exists for. Most broken checks were only ever tested
against the failure case.

- crumbl-ops shipped `stripe_payout_reconciliation` with 8 passing unit tests and a
  date-window bug that produced 28% false positives in production.
- A 2026-05-08 check flagged healthy baseline noise as a bug — it had never been run
  against a healthy state.

**A false-positive check is worse than no check.** It trains operators to ignore it,
and it looks like coverage on an audit. The 2026-05-16 Stripe window off-by-one
taught everyone to dismiss that check as "Stripe noise".

Calibration is not threshold-tuning until green — it is *reshaping the check* until
both directions hold. Three real examples from wealth-mgmt, all found by running
drafts against the live store:

| Naive check | Why it fired on healthy data | Reshaped as |
|---|---|---|
| duplicate rows: same entity+date+amount+description twice | two identical same-day charges are ordinary; dozens existed in a normal quarter | require clusters of **3+**, which was silent on healthy data |
| feed silent > N days | the quietest accounts were a low-activity savings account and one with almost no history — both legitimately idle | compare each account to **its own** cadence; exempt accounts with too little history to have one |
| every active Plaid item has a sync cursor | investment and loan items use different Plaid endpoints and correctly have none | scope to items holding a credit/depository account |

Write the calibration into the docstring. It is the most perishable knowledge in the
check and the first thing a future editor will otherwise "simplify" away.

### The anomaly may be real data

The most expensive version of this mistake is not a mis-tuned threshold — it is
"cleaning up" data that was correct. A cluster of hundreds of identical-looking
rows in one two-month window looked exactly like a duplicated import, and the
obvious remediation was to keep one row per group. Reading the rows first told a
different story: matched waves of charges and reversals with names like
`SECURITY ADJUSTMENT` and `ADJUSTMENT-PURCHASES`, confined to those two months
against a normal dozen-per-month elsewhere. It was a disputed-charge episode, and
the "fix" would have rewritten the period by tens of thousands of dollars.

So, before any dedupe or backfill that deletes rows:

- **Read the rows, not just the counts.** The names and the sign pattern carried
  the entire answer; every aggregate query was consistent with either story.
- **Ask what the delta would be.** If a cleanup moves a financial period by a
  material amount, it is not a cleanup — it is a restatement, and it needs the
  source-of-truth document (a statement, an invoice) rather than a query.
- **Check for a second source before trusting one.** Here there was none: the
  provider feed did not reach back that far, which is exactly why it was
  unresolvable.
- **Scope the check to catch a recurrence, not to report the backlog.** A
  trailing window keeps the check green on known history while still alarming if
  it happens again; the backlog is a separate decision for a human.

The durable fix was not a check at all — it was recording **provenance** on
import (source filename per row), so the same question is answerable next time by
a query instead of an investigation. A check that cannot be resolved when it
fires is only half a check.

## Window and threshold traps

**`timedelta(days=N)` with an inclusive `BETWEEN` spans N+1 days.** Ten crumbl-ops
checks carried this off-by-one. Fix it once, in a canonical helper, not ten times:

```python
def trailing_window(days, *, end=None, floor=None) -> tuple[date, date]:
    """Inclusive [start, end] spanning EXACTLY `days` days. end - start == days - 1.
    `end` defaults to YESTERDAY — today is still accumulating.
    `floor` clamps start UP, so a rolling window never reaches behind the date an
    entity was acquired and flags days you did not own."""
```

Other traps worth a line each:

- **Anchor a baseline to the subject, not to `now`.** A wealth-mgmt draft computed
  each account's cadence from a trailing 180-day window — so an account silent
  *longer* than 180 days had too few recent rows to qualify and dropped out of the
  check entirely. The deader the feed, the less likely it was noticed. Anchor to the
  account's own last transaction instead.
- **New entities generate benign failures on small samples.** Ask what your check
  does in a store's first two weeks, or an account's first month.
- **Know the domain's shape.** Crumbl Sundays are preorder-only, so near-$0 Sunday
  metrics are normal. Stripe pays out Mon–Fri, so a multi-week cross-source window
  over day-of-week-asymmetric data is where off-by-ones hide.

## Registration: derive it, never hand-curate it

An unregistered check never runs. A hand-maintained list of which checks are enrolled
in which gate *will* drift — crumbl-ops lost two checks (#959, #1069) from its deploy
gate for weeks that way.

Put enrollment **on the check**, and derive membership by scanning:

```python
def preflight(scope: str):            # scope: store | conn | system
    """Tag a check for the deploy-time pre-flight gate. The gate DERIVES its list
    by scanning for this tag — enrollment lives next to the check, not in a list
    somewhere else that drifts."""
    def _tag(fn):
        fn._preflight_scope = scope
        return fn
    return _tag
```

Then a test that no check can escape the registry:

```python
def test_every_check_is_registered():
    defined = {n for n in dir(module) if n.startswith("check_")}
    missing = defined - {n for m, n in runner.CHECKS if m == module_name}
    assert not missing, f"{sorted(missing)} will never run"
```

crumbl-ops keeps 177 of 179 checks live this way — the two exceptions are a
deliberately disabled check with a documented upstream API bug, and a parameterized
helper its wrapper calls.

**If you keep two registries with different shapes, say so loudly in both.** crumbl-ops
moved global checks from literal `results.append(...)` lines to a name-tuple so each
could run inside per-check exception isolation. The authoring skill still described the
old shape for eight months; following it would have placed a new check *outside* the
isolation and reintroduced the cascade the change fixed.

## The write-path coverage gate

Registration ensures a check that exists runs. This ensures the check **exists** — it
fails a change that touches a canonical write path with no backstopping check:

```python
RULES = [{
    "name": "remittance-driven BillPayments",
    "paths": ["src/qbo/remittance*.py"],
    "tables": ["bill_payments"],
    "requires": ["check_remittances_held", "check_billpayment_bank_reconciliation"],
}]
# Satisfied if ANY ONE required check both EXISTS and is REGISTERED.
```

Waivers must expire, or they are just permanent holes:

```python
# dq-waiver: <reason>
# dq-waiver-expires: 2026-09-01
```

An expired or malformed waiver does not waive. Ship order matters: **the check lands
before or in the same PR as the change it backstops.** "Filed as future work" is a TODO
with a compliance veneer — crumbl-ops traced a balance-sheet imbalance directly to a
deferred prevention item from a prior post-mortem.

## Isolation: one broken check must not blind the rest

Run every check in its own try/except and record a raise as a *failed result naming the
check*, not a dead run:

```python
for name in CHECKS:
    try:
        results.append(globals()[name](conn))
    except Exception as e:
        log.error("dq_check_raised", check=name, error=str(e))
        if name not in NO_CONN:
            conn.rollback()   # ← the part everyone forgets
        results.append({"check": name, "passed": False, "error": f"{type(e).__name__}: {e}"})
```

**The rollback is not optional when checks share a connection.** A SQL error — the most
common kind, typically an `UndefinedColumn` from a migration not yet applied in prod —
leaves the transaction in `InFailedSqlTransaction`. Without a rollback, every subsequent
check dies with "current transaction is aborted", turning one schema drift into ~60
cascade failures and burying the real one. It is safe because DQ checks are read-only.

Resolve check functions from module globals at **call** time, not import time. Holding
function objects in the registry silently defeats `monkeypatch.setattr(runner, "check_x",
stub)` — the tuple keeps the original reference and the real check runs against a fake
connection.

## Validate against production, and snapshot it

A green unit test with a mocked connection never executes the SQL string, so a column
rename ships green. Two backstops:

```bash
python scripts/verify_dq.py <check> <store>              # run against real data
python scripts/verify_dq.py <check> <store> --snapshot   # freeze it as a replayable fixture
```

Paste that output in the commit — including a healthy-state run. And add an EXPLAIN
test for any check whose unit test mocks the connection, so the SQL is at least parsed
and planned against the real schema.

## Know your alert path

A check that writes to a log nobody reads is not a check. Trace the path from failure to
a human before you ship, and write it in the docstring.

- In crumbl-ops the nightly `check_data_quality()` call is **log-only**; the alerting path
  is the morning digest's separate `check_all()` re-run, which files a GitHub issue.
- **A check watching held/persistent state must check the state column itself.** A digest
  line that ages out after ~30 hours silently stops alerting while the bad state persists.
- **A check must be self-sufficient** — never depend on another sync step having run first.

## Anti-patterns

- **A failure path that only logs.** It counts as deferred, not done.
- **A check that only backstops what it actually counts.** Naming a check after an
  invariant it does not measure is worse than no check.
- **Tuning a threshold until the check is green.** That is deleting the check slowly.
- **`ruff check --fix` on a module whose registry resolves names dynamically.** Ruff sees
  ~90 imports as unused and removes them; every check then dies on a `KeyError`.

## Where Used

- **crumbl-ops** — 179 checks across 8 domain modules (`src/ops/data_quality/`), 177
  registered and running nightly. `@preflight` derived deploy gate, `verify_dq_coverage.py`
  write-path gate with expiring waivers, snapshot fixtures in `tests/fixtures/dq_checks/`,
  authoring guidance in the `dq-check` skill.
- **wealth-mgmt** — 11 checks (`src/quality/`) over budget.db and investments.db: owner
  scoping, orphan transactions, categorization coverage, duplicate clusters, cadence-relative
  sync staleness, import provenance, and deterministic-ID idempotency.
  `python -m src.quality.cli check`.
- **command-center** — the four `cron_maintenance_*` jobs (doc drift, status drift, path
  integrity, memory consolidation) are DQ checks over a knowledge repo rather than a
  database; they predate this pattern and are not yet registry- or gate-backed.
