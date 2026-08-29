"""
scripts/check_gh_usage.py
GitHub spend telemetry + tripwires. Born from the 2026-08-28 usage review:
Copilot auto-review burned 95% of the 1,500-credit monthly quota in five days
before anyone looked, and the Actions free-tier cliff had silently moved from
"never" (June) to day 9 (August). This makes trajectory loud before it bills.

Pulls the enhanced-billing usage API for the current + previous month via
local gh auth (WSL gh needs the "user" scope: `gh auth refresh -s user`),
writes data/gh_usage_report.md (GITIGNORED — spend data never lands in this
public repo; the script is the shareable mechanism), and files a deduplicated
alert issue in command-center (private) when a tripwire fires:

  1. Copilot credits projected past the monthly quota
  2. Actions minutes week-over-week growth > 30% (on a non-trivial base)
  3. Month-to-date net (billed) spend past the budget line
  4. Copilot Cloud Agent credits in the last 7 days (each task ~357 credits
     = ~1/4 of the quota; spend should be a decision, not a surprise)

API granularity is per-day / per-repo / per-SKU. Workflow-level attribution
is NOT in the API — for that, download the CSV usage report from the billing
UI (the 2026-08-28 analysis pattern).

Run from repo root: python3 scripts/check_gh_usage.py [--no-issue]
Wired into scripts/run_weekly_digest.sh (best-effort). Exit codes: 0 quiet,
1 alert(s) fired, 2 API/auth failure (wrapper treats any nonzero as WARNING).
"""
import json
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

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

# Suggestion crib for alert bodies. Levers live on crumbl-ops#2111.
LEVERS = ("Levers (crumbl-ops#2111): keep the copilot-auto-review ruleset "
          "disabled; coding-agent tasks are ~357 credits each; tests.yml "
          "push-trigger removal; self-hosted runner. Workflow-level "
          "attribution needs the billing-UI CSV export.")


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
        "minutes_by_day": {}, "credits_by_day": {},
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


def build(today: date):
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
    if projected > CREDIT_QUOTA:
        alerts.append(
            f"Copilot credits projected to {projected:,.0f} by month-end "
            f"(quota {CREDIT_QUOTA:,.0f}; used {cur['credits_total']:,.0f} "
            f"through day {days_elapsed}, trailing-7d burn {recent_burn:,.0f}/day). "
            f"Overage bills at $0.01/credit.")

    # 2. Week-over-week Actions minutes growth.
    last7 = window_minutes(cur, prev, today, 7)
    prior7 = window_minutes(cur, prev, today - timedelta(days=7), 7)
    if prior7 > 0 and last7 > WOW_MIN_BASE_MINUTES:
        growth = last7 / prior7 - 1
        if growth > WOW_GROWTH_ALERT:
            alerts.append(
                f"Actions minutes up {growth:.0%} week-over-week "
                f"({prior7:,.0f} -> {last7:,.0f}).")
    else:
        growth = None

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

    return cur, prev, alerts, {
        "projected": projected, "recent_burn": recent_burn,
        "last7": last7, "prior7": prior7, "growth": growth,
        "prev_label": f"{prev_anchor.year}-{prev_anchor.month:02d}",
    }


def render(cur, prev, alerts, ctx, today: date) -> str:
    lines = [
        f"# GitHub Usage Report — {today.isoformat()}",
        "",
        "Local-only (gitignored): spend data stays out of the public repo.",
        "Per-day/per-repo API granularity; workflow attribution needs the",
        "billing-UI CSV export. Regenerated weekly by scripts/check_gh_usage.py.",
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
    return "\n".join(lines) + "\n"


def file_issue(alerts, report_md):
    check = subprocess.run(
        ["gh", "issue", "list", "--repo", ALERT_REPO, "--state", "open",
         "--search", f'"{ISSUE_TITLE}" in:title', "--json", "number"],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check.returncode == 0 and json.loads(check.stdout or "[]"):
        print("Open usage-tripwire issue already exists; not duplicating.")
        return
    body = ("Fired by best-practices scripts/check_gh_usage.py during the "
            "weekly run.\n\n"
            + "\n".join(f"- {a}" for a in alerts)
            + f"\n\n{LEVERS}\n\n---\n\n{report_md}")
    proc = subprocess.run(
        ["gh", "issue", "create", "--repo", ALERT_REPO,
         "--title", ISSUE_TITLE, "--body", body],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode == 0:
        print(f"Filed usage-tripwire issue in {ALERT_REPO}.")
    else:
        print(f"WARNING: could not file issue: {(proc.stderr or '').strip()}",
              file=sys.stderr)


def main():
    today = datetime.now(timezone.utc).date()
    cur, prev, alerts, ctx = build(today)
    report = render(cur, prev, alerts, ctx, today)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(report)
    if alerts:
        if "--no-issue" not in sys.argv:
            file_issue(alerts, report)
        sys.exit(1)


if __name__ == "__main__":
    main()
