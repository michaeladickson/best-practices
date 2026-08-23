"""
scripts/check_heartbeats.py
Unified dead-man's tell for every scheduled job, so a silent death becomes a
loud one. The WM-WeeklyDigest incident (exit 127 on every run for two weeks,
invisible because nobody looked) is the tuition this pays back.

Each check reads a freshness signal and compares against a max age:
  - file_mtime:     newest mtime of a file or glob
  - json_last_run:  a "last_run" ISO date inside a JSON state file (or the
                    newest across a glob of them)

Statuses: OK / STALE / PENDING (state has never existed — a job that hasn't
had its first run yet, e.g. monthly-backward-pass before Sep 1).

When anything is STALE, opens a GitHub issue in this repo (skipped if an open
heartbeat issue already exists — no weekly duplicates) and exits 1.

Run from repo root: python scripts/check_heartbeats.py [--no-issue]
Wired into scripts/run_weekly_digest.sh; safe to run manually anytime.

To add a job: append to CHECKS. Keep max_age comfortably above the cadence
(weekly job -> 9d) so a single late run doesn't page.
"""
import glob
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()
ROOT = Path(__file__).parent.parent

CHECKS = [
    {
        "name": "CC-WeeklyDigest (Fri 6pm)",
        "type": "file_mtime",
        "path": str(ROOT / "data" / "feed_archive" / "posts.json"),
        "max_age_days": 9,
    },
    {
        "name": "weekly-skills-sync (Mon 8am)",
        "type": "json_last_run",
        "path": str(HOME / ".claude" / "skills-sync" / "state.json"),
        "max_age_days": 9,
    },
    {
        "name": "monthly-backward-pass (1st, 8am)",
        "type": "json_last_run",
        "path": str(HOME / ".claude" / "backward-pass" / "*.json"),
        "max_age_days": 40,
    },
]

REPO = "michaeladickson/best-practices"
ISSUE_TITLE = "Heartbeat: scheduled job(s) stale"


def _newest_mtime(pattern: str):
    paths = glob.glob(pattern)
    if not paths:
        return None
    return max(Path(p).stat().st_mtime for p in paths)


def _newest_last_run(pattern: str):
    newest = None
    for p in glob.glob(pattern):
        try:
            with open(p, encoding="utf-8") as f:
                raw = json.load(f).get("last_run")
            if not raw:
                continue
            ts = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if newest is None or ts > newest:
                newest = ts
        except (json.JSONDecodeError, ValueError, OSError):
            continue
    return newest.timestamp() if newest else None


def run_checks():
    now = datetime.now(timezone.utc).timestamp()
    results = []
    for check in CHECKS:
        ts = (_newest_mtime(check["path"]) if check["type"] == "file_mtime"
              else _newest_last_run(check["path"]))
        if ts is None:
            results.append((check["name"], "PENDING", "no state yet (never run?)"))
            continue
        age_days = (now - ts) / 86400
        status = "STALE" if age_days > check["max_age_days"] else "OK"
        results.append((check["name"], status,
                        f"last signal {age_days:.1f}d ago (max {check['max_age_days']}d)"))
    return results


def file_issue(stale_rows):
    check = subprocess.run(
        ["gh", "issue", "list", "--repo", REPO, "--state", "open",
         "--search", f'"{ISSUE_TITLE}" in:title', "--json", "number"],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check.returncode == 0 and json.loads(check.stdout or "[]"):
        print("Open heartbeat issue already exists; not duplicating.")
        return
    body = ("Detected by scripts/check_heartbeats.py during the weekly run.\n\n"
            + "\n".join(f"- **{n}** — {d}" for n, _, d in stale_rows)
            + "\n\nA stale heartbeat means the job has silently stopped firing "
              "(the WM-WeeklyDigest failure mode). Check the job's own logs/state, "
              "fix, then close this issue.")
    subprocess.run(["gh", "issue", "create", "--repo", REPO,
                    "--title", ISSUE_TITLE, "--body", body],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
    print("Filed heartbeat issue.")


def main():
    results = run_checks()
    width = max(len(n) for n, _, _ in results)
    for name, status, detail in results:
        print(f"{name:<{width}}  {status:<8} {detail}")
    stale = [r for r in results if r[1] == "STALE"]
    if stale:
        if "--no-issue" not in sys.argv:
            file_issue(stale)
        sys.exit(1)


if __name__ == "__main__":
    main()
