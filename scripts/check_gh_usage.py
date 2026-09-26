"""
scripts/check_gh_usage.py
GitHub spend telemetry + tripwires. Born from the 2026-08-28 usage review:
Copilot auto-review burned 95% of the 1,500-credit monthly quota in five days
before anyone looked, and the Actions free-tier cliff had silently moved from
"never" (June) to day 9 (August). This makes trajectory loud before it bills.

Pulls the enhanced-billing usage API for the current + previous month via
local gh auth (WSL gh needs the "user" scope: `gh auth refresh -s user`),
writes data/gh_usage_report.md (GITIGNORED — spend data never lands in this
public repo; the script is the shareable mechanism), and when a tripwire fires
files an alert issue in command-center (private), or comments the week's
report on the one already open:

  1. Copilot credits projected past the monthly quota
  2. Actions minutes week-over-week growth > 30% (on a non-trivial base)
  3. Month-to-date net (billed) spend past the budget line
  4. Copilot Cloud Agent credits in the last 7 days (each task ~357 credits
     = ~1/4 of the quota; spend should be a decision, not a surprise)

The billing API stops at per-day / per-repo / per-SKU. When tripwire 2 fires,
the script names the workflows behind the jump, read-only from the Actions
API, for each repo that billed ATTRIBUTE_MIN_REPO_MINUTES in either week:

  - Runs: actions/runs?created=<one UTC day>, paginated. A filtered runs
    query stops at 1,000 results, so it lists one day at a time and checks
    each day's total_count against the rows it got.
  - Minutes: actions/runs/{id}/jobs?filter=all (every attempt). A job that got
    a GitHub-hosted runner bills ceil((completed_at - started_at) / 60s); a
    skipped job never gets one and bills 0. Not actions/runs/{id}/timing: it
    reports 0 billable ms for every job.
  - Tie: bucketed by the UTC day each job completed, the minutes are printed
    per day against the billing API, and a repo whose weekly total misses by
    more than TIE_TOLERANCE is withheld from the report, not published.

That costs about one API call per run, so it runs only on the tripwire path
(or with --attribute); the quiet weekly run makes two calls.

Run from repo root: python3 scripts/check_gh_usage.py [--no-issue] [--attribute]
Wired into scripts/run_weekly_digest.sh (best-effort). Exit codes: 0 quiet,
1 alert(s) fired, 2 API/auth failure (wrapper treats any nonzero as WARNING).
"""
import json
import math
import re
import subprocess
import sys
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import TimeoutError as PoolTimeout
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import NamedTuple
from urllib.parse import urlencode

ROOT = Path(__file__).parent.parent
REPORT_PATH = ROOT / "data" / "gh_usage_report.md"

GH_USER = "michaeladickson"
ALERT_REPO = "michaeladickson/command-center"
ISSUE_TITLE = "GH usage tripwire: spend trajectory needs a look"

# Not exposed by the API (the premium_request endpoint returns empty for this
# account). Verified 2026-08 from the billing UI's AI usage report
# (total_monthly_quota). Update when the Copilot plan changes.
CREDIT_QUOTA = 1500.0
NET_BUDGET_USD = 40.0
WOW_GROWTH_ALERT = 0.30
WOW_MIN_BASE_MINUTES = 500.0

# Per-workflow attribution (tripwire 2 only). About one API call per run, so
# two weeks of a busy repo cost a few thousand of the 5,000/hour core limit.
ATTRIBUTE_MIN_REPO_MINUTES = 100.0  # a repo's billed minutes in either week
TIE_TOLERANCE = 0.03                # weekly |attributed - billed| / billed
TIE_SLACK_MINUTES = 5.0             # floor, so a near-empty week can still tie
LOOKBACK_DAYS = 2                   # runs created earlier can finish in-window
GH_WORKERS = 8
GH_CALLS_PER_SEC = 10.0             # secondary rate limit: 900 REST calls/min
GH_CALL_TIMEOUT_S = 60
ATTRIBUTION_BUDGET_S = 480          # the weekly task is killed at 30 minutes
RATE_LIMIT_RESERVE = 200            # calls left for the rest of the weekly run
EVENT_ORDER = ("push", "pull_request", "schedule", "workflow_dispatch", "dynamic")
PR_EVENTS = ("pull_request", "pull_request_target")

# Appended to alert bodies. Mechanisms rather than a list of settings: the
# list this replaced (2026-08) had been worked through a month later, and the
# growth by then came from runs per PR, which it never mentioned.
LEVERS = ("Levers: each push to a PR re-runs its pull_request workflows, so "
          "fix-up pushes and re-review rounds multiply runs per PR, and every "
          "job that gets a runner bills at least a minute (a 10-second status "
          "job bills 1). A self-hosted runner lowers the price of a minute, not "
          "the number of runs.")


def fetch_month(year: int, month: int):
    """Usage items for one month via gh (local auth). None on failure."""
    proc = subprocess.run(
        ["gh", "api", f"/users/{GH_USER}/settings/billing/usage"
         f"?year={year}&month={month}"],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        msg = (proc.stderr or "").strip()
        print(f"ERROR: usage API fetch failed for {year}-{month:02d}: {msg}",
              file=sys.stderr)
        if "user" in msg and "scope" in msg:
            print("Hint: the WSL gh token needs the user scope: "
                  "gh auth refresh -h github.com -s user", file=sys.stderr)
        return None
    try:
        return json.loads(proc.stdout).get("usageItems", [])
    except json.JSONDecodeError:
        print("ERROR: usage API returned non-JSON", file=sys.stderr)
        return None


def _day(item) -> date:
    return datetime.fromisoformat(
        item["date"].replace("Z", "+00:00")).astimezone(timezone.utc).date()


def summarize(items, today: date):
    """Aggregate one month's items (only days strictly before `today`)."""
    out = {
        "minutes_by_repo": {}, "net_by_repo": {}, "gross_by_repo": {},
        "minutes_by_day": {}, "minutes_by_repo_day": {}, "credits_by_day": {},
        "credits_total": 0.0, "credits_agent_by_day": {},
        "net_total": 0.0, "gross_total": 0.0, "first_billed_day": None,
    }
    for it in items:
        d = _day(it)
        if d >= today:  # partial day; skip for stable dailies
            continue
        out["net_total"] += it["netAmount"]
        out["gross_total"] += it["grossAmount"]
        repo = it.get("repositoryName") or "(account)"
        if it["unitType"] == "Minutes":
            out["minutes_by_repo"][repo] = out["minutes_by_repo"].get(repo, 0) + it["quantity"]
            out["minutes_by_day"][d] = out["minutes_by_day"].get(d, 0) + it["quantity"]
            repo_days = out["minutes_by_repo_day"].setdefault(repo, {})
            repo_days[d] = repo_days.get(d, 0) + it["quantity"]
            if it["netAmount"] > 0 and (out["first_billed_day"] is None
                                        or d < out["first_billed_day"]):
                out["first_billed_day"] = d
        if it["product"] == "copilot":
            out["credits_total"] += it["quantity"]
            out["credits_by_day"][d] = out["credits_by_day"].get(d, 0) + it["quantity"]
            if it["sku"] == "Copilot Cloud Agent":
                out["credits_agent_by_day"][d] = (
                    out["credits_agent_by_day"].get(d, 0) + it["quantity"])
        out["net_by_repo"][repo] = out["net_by_repo"].get(repo, 0) + it["netAmount"]
        out["gross_by_repo"][repo] = out["gross_by_repo"].get(repo, 0) + it["grossAmount"]
    return out


def window_minutes(cur, prev, end: date, days: int):
    """Total Actions minutes for the `days`-day window ending the day before
    `end`, drawing from both months' daily tallies."""
    total = 0.0
    for i in range(1, days + 1):
        d = end - timedelta(days=i)
        total += cur["minutes_by_day"].get(d, 0) + prev["minutes_by_day"].get(d, 0)
    return total


def wow_weeks(today: date):
    """The UTC days the week-over-week tripwire compares: (older, newer)."""
    newer = [today - timedelta(days=i) for i in range(7, 0, -1)]
    return [d - timedelta(days=7) for d in newer], newer


# --- Per-workflow attribution (Actions API, read-only) ----------------------

class GhError(RuntimeError):
    """An Actions API read failed or came back incomplete."""


class _Pacer:
    """Spaces calls across worker threads, so a burst stays under GitHub's
    secondary rate limit however fast gh returns."""

    def __init__(self, per_sec: float):
        self.gap = 1.0 / per_sec
        self.lock = threading.Lock()
        self.next = 0.0

    def wait(self):
        with self.lock:
            now = time.monotonic()
            slot = max(now, self.next)
            self.next = slot + self.gap
        time.sleep(slot - now)


_PACER = _Pacer(GH_CALLS_PER_SEC)
_ABORT = threading.Event()  # set when the attribution budget runs out
_TRANSIENT = re.compile(r"HTTP 5\d\d|secondary rate limit|timeout|timed out|"
                        r"connection reset|unexpected EOF", re.I)


def gh_json(path: str):
    """GET one API path through gh and parse it. Retries 5xx, secondary rate
    limits and network drops; any other failure raises GhError at once."""
    err = ""
    for attempt in range(3):
        if attempt:
            time.sleep(60 if "secondary rate limit" in err else 5 * attempt)
        if _ABORT.is_set():
            raise GhError(f"gh api {path}: abandoned, attribution budget spent")
        _PACER.wait()
        try:
            proc = subprocess.run(
                ["gh", "api", path], capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=GH_CALL_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            err = f"timed out after {GH_CALL_TIMEOUT_S}s"
            continue
        if proc.returncode == 0:
            try:
                return json.loads(proc.stdout)
            except json.JSONDecodeError:
                err = "non-JSON response"
                continue
        err = (proc.stderr or "").strip()
        if not _TRANSIENT.search(err):
            break
    raise GhError(f"gh api {path}: {err[:200]}")


def rate_remaining():
    """(calls left, reset time) on the core REST limit. Reading it is free."""
    try:
        core = gh_json("rate_limit")["resources"]["core"]
        return core["remaining"], datetime.fromtimestamp(core["reset"], timezone.utc)
    except (GhError, KeyError, TypeError):
        return None, None


def _ts(stamp: str) -> datetime:
    return datetime.fromisoformat(stamp.replace("Z", "+00:00"))


def _pages(path: str, key: str, what: str):
    """Every row of a paginated list endpoint, checked against total_count."""
    rows, total = {}, 0
    for page in range(1, 11):  # 10 x 100: a filtered runs query stops at 1,000
        data = gh_json(f"{path}&per_page=100&page={page}")
        total, batch = data["total_count"], data[key]
        rows.update((row["id"], row) for row in batch)
        if len(batch) < 100 or len(rows) >= total:
            break
    if len(rows) != total:
        cap = " (past the 1,000-result cap)" if total > 1000 else ""
        raise GhError(f"{what}: total_count {total:,} but {len(rows):,} "
                      f"came back{cap}")
    return list(rows.values())


def list_day_runs(repo: str, day: date):
    """Every run created on one UTC day. A day per query keeps each under the
    1,000-result cap, and _pages fails loudly on a day that is not."""
    span = f"{day.isoformat()}T00:00:00Z..{day.isoformat()}T23:59:59Z"
    return _pages(f"repos/{repo}/actions/runs?" + urlencode({"created": span}),
                  "workflow_runs", f"{repo} runs created {day}")


def list_run_jobs(repo: str, run_id: int):
    """Jobs from every attempt of one run: a re-run bills again."""
    return _pages(f"repos/{repo}/actions/runs/{run_id}/jobs?filter=all",
                  "jobs", f"{repo} run {run_id} jobs")


def billed_minutes(job) -> int:
    """What one job bills: its runner time rounded up to the whole minute. A
    skipped job never gets a runner, and a self-hosted runner is free."""
    if (not job.get("runner_name") or not job.get("started_at")
            or not job.get("completed_at")
            or "self-hosted" in (job.get("labels") or [])):
        return 0
    seconds = (_ts(job["completed_at"]) - _ts(job["started_at"])).total_seconds()
    return max(0, math.ceil(seconds / 60))


def _week():
    return {"runs": 0, "minutes": 0, "events": {}, "pr_runs": 0, "branches": set()}


def attribute(runs, jobs_by_run, older, newer):
    """Per-workflow runs and billed minutes for two 7-day windows.

    A run counts in the week it was created. Its minutes land on the UTC day
    each job completed, which is how the billing API books them, so a run
    created before the window can still add minutes inside it. Returns
    ({workflow path: {"name", "older", "newer"}}, {day: minutes}).
    """
    week_of = dict.fromkeys(older, "older") | dict.fromkeys(newer, "newer")
    flows, by_day = {}, defaultdict(int)
    for run in sorted(runs, key=lambda r: r["created_at"]):
        flow = flows.setdefault(run["path"], {"older": _week(), "newer": _week()})
        flow["name"] = run["name"]  # the newest run's name wins a rename
        event = run["event"]
        week = week_of.get(_ts(run["created_at"]).date())
        if week:
            stats = flow[week]
            stats["runs"] += 1
            stats["events"].setdefault(event, [0, 0])[0] += 1
            if event in PR_EVENTS:
                stats["pr_runs"] += 1
                stats["branches"].add(run["head_branch"])
        for job in jobs_by_run.get(run["id"], ()):
            minutes = billed_minutes(job)
            if not minutes:
                continue
            day = _ts(job["completed_at"]).date()
            week = week_of.get(day)
            if week:
                by_day[day] += minutes
                flow[week]["minutes"] += minutes
                flow[week]["events"].setdefault(event, [0, 0])[1] += minutes
    return flows, dict(by_day)


class Tie(NamedTuple):
    rows: list        # (day, attributed, billed) per UTC day
    attributed: int
    billed: float
    ok: bool          # weekly total within tolerance


def tie(by_day, billed_by_day, days) -> Tie:
    """Attributed vs billed minutes over `days`."""
    rows = [(d, by_day.get(d, 0), billed_by_day.get(d, 0.0)) for d in days]
    attributed = sum(r[1] for r in rows)
    billed = sum(r[2] for r in rows)
    ok = abs(attributed - billed) <= max(TIE_TOLERANCE * billed, TIE_SLACK_MINUTES)
    return Tie(rows, attributed, billed, ok)


def _pct(attributed, billed) -> str:
    return f"{(attributed - billed) / billed:+.1%}" if billed else "n/a"


def print_tie(repo: str, ties):
    """The per-day tie, for the run log."""
    print(f"Tie to the billing usage API, {repo} "
          "(minutes per UTC day: attributed, billed, difference):")
    for label in ("older", "newer"):
        rows, attributed, billed, ok = ties[label]
        for d, a, b in rows:
            print(f"  {d}  {a:>6,}  {b:>8,.0f}  {a - b:>+6,.0f}")
        print(f"  {label} week: {attributed:,} vs {billed:,.0f} "
              f"({_pct(attributed, billed)}): "
              + ("ties" if ok else "OFF, attribution withheld"))


def _pool(fn, tasks, deadline: float, label: str):
    """fn(*task) for every task on GH_WORKERS threads, until the deadline.
    Returns ({task: result}, {task: error}); a task not done in time is an
    error, so nothing downstream mistakes a partial read for a whole one."""
    results, errors = {}, {}
    pool = ThreadPoolExecutor(max_workers=GH_WORKERS)
    futures = {pool.submit(fn, *task): task for task in tasks}
    try:
        timeout = max(0.0, deadline - time.monotonic())
        for n, fut in enumerate(as_completed(futures, timeout=timeout), 1):
            try:
                results[futures[fut]] = fut.result()
            except Exception as e:  # recorded per task and reported upstream
                errors[futures[fut]] = f"{type(e).__name__}: {e}"
            if n % 500 == 0:
                print(f"  {label}: {n:,} of {len(tasks):,}", flush=True)
    except PoolTimeout:
        _ABORT.set()
        for task in tasks:
            if task not in results and task not in errors:
                errors[task] = f"not read within the {ATTRIBUTION_BUDGET_S}s budget"
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    return results, errors


def attribute_jump(cur, prev, today: date):
    """Name the workflows behind the week-over-week minutes change, per repo,
    for the same UTC days window_minutes compares. Prints the per-day tie."""
    older, newer = wow_weeks(today)
    billed = defaultdict(dict)
    for month in (prev, cur):
        for repo, days in month["minutes_by_repo_day"].items():
            billed[repo].update(days)

    def week(repo, days):
        return sum(billed[repo].get(d, 0.0) for d in days)

    repos = sorted(
        (r for r in billed if r != "(account)"
         and max(week(r, older), week(r, newer)) >= ATTRIBUTE_MIN_REPO_MINUTES),
        key=lambda r: week(r, newer) - week(r, older), reverse=True)
    out = {"older": older, "newer": newer, "repos": [], "skipped": None}
    if not repos:
        out["skipped"] = (f"no repo billed {ATTRIBUTE_MIN_REPO_MINUTES:,.0f} "
                          "or more minutes in either week")
        return out

    _ABORT.clear()
    deadline = time.monotonic() + ATTRIBUTION_BUDGET_S
    list_days = [older[0] - timedelta(days=i)
                 for i in range(LOOKBACK_DAYS, 0, -1)] + older + newer
    print(f"Attributing Actions minutes for {', '.join(repos)}: listing runs "
          f"one UTC day at a time, {list_days[0]} to {list_days[-1]}", flush=True)
    listed, list_errors = _pool(
        lambda repo, day: list_day_runs(f"{GH_USER}/{repo}", day),
        [(r, d) for r in repos for d in list_days], deadline, "day listings")

    start = datetime.combine(older[0], datetime.min.time(), timezone.utc)
    runs, failed = {}, {}
    for repo in repos:
        errs = [e for (r, _), e in list_errors.items() if r == repo]
        if errs:
            failed[repo] = (f"{len(errs)} of {len(list_days)} day listings "
                            f"failed; first: {errs[0]}")
            continue
        # A run last updated before the window finished before it too.
        runs[repo] = [run for d in list_days for run in listed[(repo, d)]
                      if _ts(run["updated_at"]) >= start]

    calls = sum(len(v) for v in runs.values())
    left, reset = rate_remaining()
    if left is not None and calls + RATE_LIMIT_RESERVE > left:
        out["skipped"] = (f"reading jobs needs about {calls:,} API calls and "
                          f"{left:,} are left until {reset:%H:%M} UTC")
        return out
    print(f"Reading jobs for {calls:,} runs ("
          + (f"{left:,}" if left is not None else "unknown")
          + " API calls left)", flush=True)
    jobs, job_errors = _pool(
        lambda repo, run_id: list_run_jobs(f"{GH_USER}/{repo}", run_id),
        [(r, run["id"]) for r, repo_runs in runs.items() for run in repo_runs],
        deadline, "job listings")

    for repo in repos:
        if repo in failed:
            out["repos"].append({"repo": repo, "status": "failed",
                                 "reason": failed[repo]})
            continue
        errs = [e for (r, _), e in job_errors.items() if r == repo]
        if errs:
            out["repos"].append({
                "repo": repo, "status": "failed",
                "reason": (f"{len(errs):,} of {len(runs[repo]):,} job listings "
                           f"failed; first: {errs[0]}")})
            continue
        flows, by_day = attribute(
            runs[repo], {rid: j for (r, rid), j in jobs.items() if r == repo},
            older, newer)
        ties = {"older": tie(by_day, billed[repo], older),
                "newer": tie(by_day, billed[repo], newer)}
        print_tie(repo, ties)
        ok = ties["older"].ok and ties["newer"].ok
        out["repos"].append({"repo": repo, "status": "ok" if ok else "withheld",
                             "flows": flows, "ties": ties})
    return out


def build(today: date, attribute_anyway: bool = False):
    cur_items = fetch_month(today.year, today.month)
    prev_anchor = today.replace(day=1) - timedelta(days=1)
    prev_items = fetch_month(prev_anchor.year, prev_anchor.month)
    if cur_items is None or prev_items is None:
        sys.exit(2)
    cur = summarize(cur_items, today)
    prev = summarize(prev_items, today)

    alerts = []

    # 1. Copilot credit projection (from days with any credit activity).
    days_elapsed = max(1, today.day - 1)
    days_in_month = ((today.replace(day=28) + timedelta(days=4)).replace(day=1)
                     - timedelta(days=1)).day
    recent_burn = sum(cur["credits_by_day"].get(today - timedelta(days=i), 0)
                      for i in range(1, 8)) / 7
    projected = cur["credits_total"] + recent_burn * (days_in_month - days_elapsed)
    # Trajectory, not history: an overage already incurred with no burn in the
    # last 7 days is a sunk cost that was alerted when it happened. Without the
    # burn check this re-fires every week to month-end on an overage that
    # stopped growing days ago.
    if projected > CREDIT_QUOTA and recent_burn > 0:
        alerts.append(
            f"Copilot credits projected to {projected:,.0f} by month-end "
            f"(quota {CREDIT_QUOTA:,.0f}; used {cur['credits_total']:,.0f} "
            f"through day {days_elapsed}, trailing-7d burn {recent_burn:,.0f}/day). "
            f"Overage bills at $0.01/credit.")

    # 2. Week-over-week Actions minutes growth.
    last7 = window_minutes(cur, prev, today, 7)
    prior7 = window_minutes(cur, prev, today - timedelta(days=7), 7)
    growth = None
    if prior7 > 0 and last7 > WOW_MIN_BASE_MINUTES:
        growth = last7 / prior7 - 1
    wow_fired = growth is not None and growth > WOW_GROWTH_ALERT
    if wow_fired:
        alerts.append(
            f"Actions minutes up {growth:.0%} week-over-week "
            f"({prior7:,.0f} -> {last7:,.0f}).")

    # 3. Month-to-date billed spend.
    if cur["net_total"] > NET_BUDGET_USD:
        alerts.append(f"Month-to-date billed spend ${cur['net_total']:,.2f} "
                      f"exceeds the ${NET_BUDGET_USD:,.0f} budget line.")

    # 4. Cloud Agent activity in the last 7 days.
    agent7 = sum(cur["credits_agent_by_day"].get(today - timedelta(days=i), 0)
                 for i in range(1, 8))
    if agent7 > 0:
        alerts.append(f"Copilot Cloud Agent drew {agent7:,.0f} credits in the "
                      f"last 7 days (~357/task, ~1/4 of the monthly quota each).")

    # Only when minutes jumped: the quiet weekly run stays at two API calls.
    attribution = None
    if wow_fired or attribute_anyway:
        try:
            attribution = attribute_jump(cur, prev, today)
        except Exception as e:  # enrichment only; it must never cost the alert
            older, newer = wow_weeks(today)
            attribution = {"older": older, "newer": newer, "repos": [],
                           "skipped": f"attribution failed ({type(e).__name__}: {e})"}

    return cur, prev, alerts, {
        "projected": projected, "recent_burn": recent_burn,
        "last7": last7, "prior7": prior7, "growth": growth,
        "prev_label": f"{prev_anchor.year}-{prev_anchor.month:02d}",
        "attribution": attribution,
    }


def _event_order(event: str):
    return (EVENT_ORDER.index(event) if event in EVENT_ORDER else len(EVENT_ORDER),
            event)


def _events_cell(flow) -> str:
    """Trigger split. One trigger needs no numbers (the Runs and Minutes
    columns are the split); several get runs/minutes per week each."""
    o, n = flow["older"]["events"], flow["newer"]["events"]
    events = sorted(set(o) | set(n), key=_event_order)
    if len(events) <= 1:
        return "".join(events)
    zero = [0, 0]
    return "; ".join(
        f"{e} {o.get(e, zero)[0]:,}/{o.get(e, zero)[1]:,} -> "
        f"{n.get(e, zero)[0]:,}/{n.get(e, zero)[1]:,}" for e in events)


def _per_branch(stats) -> str:
    if not stats["branches"]:
        return "-"
    return f"{stats['pr_runs'] / len(stats['branches']):.2f}"


def _per_branch_cell(flow) -> str:
    o, n = flow["older"], flow["newer"]
    if not (o["pr_runs"] or n["pr_runs"]):
        return ""
    return (f"{_per_branch(o)} -> {_per_branch(n)} "
            f"({len(o['branches']):,} -> {len(n['branches']):,} branches)")


def _workflow_label(path: str, name: str) -> str:
    name = name.replace("|", "\\|")
    if path.startswith(".github/workflows/"):
        return f"{name} (`{path.rsplit('/', 1)[-1]}`)"
    return name


def _workflow_table(flows) -> list:
    rows = [f for f in flows.items()
            if any(f[1][w][k] for w in ("older", "newer") for k in ("runs", "minutes"))]
    rows.sort(key=lambda pf: (pf[1]["newer"]["minutes"] - pf[1]["older"]["minutes"],
                              pf[1]["newer"]["minutes"]), reverse=True)
    lines = ["| Workflow | Runs | Minutes | Change (min) | Triggers (runs/min) "
             "| Runs per PR branch |",
             "|---|---|---|---|---|---|"]
    for path, f in rows:
        o, n = f["older"], f["newer"]
        lines.append(
            f"| {_workflow_label(path, f['name'])} | {o['runs']:,} -> {n['runs']:,} "
            f"| {o['minutes']:,} -> {n['minutes']:,} "
            f"| {n['minutes'] - o['minutes']:+,} | {_events_cell(f)} "
            f"| {_per_branch_cell(f)} |")
    tot = {w: [sum(f[w][k] for _, f in rows) for k in ("runs", "minutes")]
           for w in ("older", "newer")}
    lines.append(
        f"| **Total** | {tot['older'][0]:,} -> {tot['newer'][0]:,} "
        f"| {tot['older'][1]:,} -> {tot['newer'][1]:,} "
        f"| {tot['newer'][1] - tot['older'][1]:+,} | | |")
    return lines


def _trigger_line(flows) -> str:
    """Minutes by trigger across the repo, plus minutes per PR branch: the
    split between more PRs and more runs per PR."""
    minutes = defaultdict(lambda: [0, 0])
    branches = [set(), set()]
    for f in flows.values():
        for i, w in enumerate(("older", "newer")):
            for event, (_, m) in f[w]["events"].items():
                minutes[event][i] += m
            branches[i] |= f[w]["branches"]
    parts = [f"{e} {o:,} -> {n:,} ({n - o:+,})"
             for e, (o, n) in sorted(minutes.items(), key=lambda kv: _event_order(kv[0]))
             if o or n]
    line = "By trigger (minutes): " + "; ".join(parts) + "."
    if branches[0] or branches[1]:
        pr = [sum(minutes[e][i] for e in PR_EVENTS if e in minutes) for i in (0, 1)]
        per = [f"{pr[i] / len(branches[i]):.1f}" if branches[i] else "-" for i in (0, 1)]
        line += (f" PR branches with runs: {len(branches[0]):,} -> "
                 f"{len(branches[1]):,}; pull_request minutes per branch: "
                 f"{per[0]} -> {per[1]}.")
    return line


def render_attribution(attr) -> list:
    older, newer = attr["older"], attr["newer"]
    lines = ["", "## Actions minutes by workflow", "",
             f"Week-over-week windows: {older[0]}..{older[-1]} -> "
             f"{newer[0]}..{newer[-1]} (UTC days). Runs count in the week they "
             "were created; minutes on the day each job finished, as the "
             "billing API books them. Runs per PR branch is pull_request runs "
             "over the distinct head branches they ran on.", ""]
    if attr["skipped"]:
        return lines + [f"Not attributed: {attr['skipped']}."]
    for res in attr["repos"]:
        if res["status"] == "failed":
            lines += [f"### {res['repo']}", "", f"Not attributed: {res['reason']}.", ""]
            continue
        a_old, b_old = res["ties"]["older"].attributed, res["ties"]["older"].billed
        a_new, b_new = res["ties"]["newer"].attributed, res["ties"]["newer"].billed
        lines += [f"### {res['repo']}: {b_old:,.0f} -> {b_new:,.0f} billed minutes "
                  f"({b_new - b_old:+,.0f})", ""]
        if res["status"] == "withheld":
            lines += ["Withheld: the attribution does not tie to the billing usage "
                      f"API (older week {a_old:,} attributed vs {b_old:,.0f} billed, "
                      f"newer week {a_new:,} vs {b_new:,.0f}; per-day tie in the "
                      "run log).", ""]
            continue
        lines += _workflow_table(res["flows"])
        lines += ["", _trigger_line(res["flows"]), "",
                  f"Ties to the billing usage API: older week {a_old:,} of "
                  f"{b_old:,.0f} billed minutes, newer week {a_new:,} of "
                  f"{b_new:,.0f} (per-day tie in the run log).", ""]
    return lines


def render(cur, prev, alerts, ctx, today: date) -> str:
    lines = [
        f"# GitHub Usage Report — {today.isoformat()}",
        "",
        "Local-only (gitignored): spend data stays out of the public repo.",
        "Per-day/per-repo from the billing API; a per-workflow table from the",
        "Actions API is added when the week-over-week minutes tripwire fires.",
        "Regenerated weekly by scripts/check_gh_usage.py.",
        "",
        f"## Month to date (through {today - timedelta(days=1)})",
        "",
        f"- Actions minutes: **{sum(cur['minutes_by_repo'].values()):,.0f}**"
        f" (prev month {ctx['prev_label']} full: {sum(prev['minutes_by_repo'].values()):,.0f})",
        f"- Billed (net): **${cur['net_total']:,.2f}** · gross ${cur['gross_total']:,.2f}"
        f" (prev month billed: ${prev['net_total']:,.2f})",
        f"- Free-tier cliff: "
        + (f"**{cur['first_billed_day']}**" if cur["first_billed_day"] else "not reached"),
        f"- Copilot credits: **{cur['credits_total']:,.0f} / {CREDIT_QUOTA:,.0f}**"
        f" · trailing-7d {ctx['recent_burn']:,.0f}/day · month-end projection"
        f" {ctx['projected']:,.0f}",
        f"- Actions minutes WoW: {ctx['prior7']:,.0f} -> {ctx['last7']:,.0f}"
        + (f" ({ctx['growth']:+.0%})" if ctx["growth"] is not None else ""),
        "",
        "## By repo (minutes / gross / net)",
        "",
        "| Repo | Minutes | Gross | Net |",
        "|---|---|---|---|",
    ]
    for repo in sorted(cur["gross_by_repo"], key=cur["gross_by_repo"].get,
                       reverse=True):
        lines.append(f"| {repo} | {cur['minutes_by_repo'].get(repo, 0):,.0f} "
                     f"| ${cur['gross_by_repo'][repo]:,.2f} "
                     f"| ${cur['net_by_repo'][repo]:,.2f} |")
    lines += ["", "## Tripwires", ""]
    lines += [f"- ⚠️ {a}" for a in alerts] if alerts else ["- none fired"]
    if alerts:
        lines += ["", LEVERS]
    if ctx.get("attribution"):
        lines += render_attribution(ctx["attribution"])
    return "\n".join(lines) + "\n"


def file_issue(alerts, report_md, today: date):
    """Open the alert issue, or comment this week's report on the open one.

    It used to stay silent while an issue was open, and one stays open for
    weeks while the cause is worked on, so every later week's per-workflow
    table reached only the gitignored local report. The date marker keeps a
    same-day re-run from posting twice.
    """
    marker = f"<!-- check_gh_usage {today.isoformat()} -->"
    check = subprocess.run(
        ["gh", "issue", "list", "--repo", ALERT_REPO, "--state", "open",
         "--search", f'"{ISSUE_TITLE}" in:title',
         "--json", "number,title,body,comments"],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    # The search matches words, not the title; only an exact title is ours.
    found = [i for i in (json.loads(check.stdout or "[]") if check.returncode == 0 else [])
             if i["title"] == ISSUE_TITLE]
    if found:
        issue = found[0]["number"]
        posted = [found[0]["body"]] + [c["body"] for c in found[0]["comments"]]
        if any(marker in text for text in posted):
            print(f"{ALERT_REPO}#{issue} already has the {today} report.")
            return
        cmd = ["gh", "issue", "comment", str(issue), "--repo", ALERT_REPO]
        body = f"{marker}\nStill firing in the {today} weekly run.\n\n{report_md}"
        done = f"Commented this week's report on {ALERT_REPO}#{issue}."
    else:
        cmd = ["gh", "issue", "create", "--repo", ALERT_REPO, "--title", ISSUE_TITLE]
        body = (f"{marker}\nFired by best-practices scripts/check_gh_usage.py "
                "during the weekly run.\n\n"
                + "\n".join(f"- {a}" for a in alerts)
                + f"\n\n{LEVERS}\n\n---\n\n{report_md}")
        done = f"Filed usage-tripwire issue in {ALERT_REPO}."
    proc = subprocess.run(
        cmd + ["--body-file", "-"], input=body,
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode == 0:
        print(done)
    else:
        print(f"WARNING: could not write to {ALERT_REPO}: "
              f"{(proc.stderr or '').strip()}", file=sys.stderr)


def main():
    today = datetime.now(timezone.utc).date()
    cur, prev, alerts, ctx = build(today, attribute_anyway="--attribute" in sys.argv)
    report = render(cur, prev, alerts, ctx, today)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(report)
    if alerts:
        if "--no-issue" not in sys.argv:
            file_issue(alerts, report, today)
        sys.exit(1)


if __name__ == "__main__":
    main()
