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
had its first run yet, e.g. monthly-backward-pass before Sep 1) / UNREADABLE
(a state file exists but holds no readable last_run).

UNREADABLE is not PENDING. The 2026-11-09 skills-sync run wrote state.json with
a UTF-8 byte order mark, json.load rejected it, and the job read "no state yet
(never run?)": a tell that could never go STALE. State files are read with
utf-8-sig, and one that still cannot be read alerts like a stale job.

When anything is STALE or UNREADABLE, opens a GitHub issue in this repo
(skipped if an open heartbeat issue already exists — no weekly duplicates) and
exits 1.

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
    # Written only on a good read, so a page that keeps failing goes stale here
    # even if its "page unreadable" issue could not be filed.
    {
        "name": "Gemini deprecations watch (inside weekly run)",
        "type": "file_mtime",
        "path": str(ROOT / "data" / "model_deprecations.json"),
        "max_age_days": 9,
    },
    {
        "name": "Vertex retirement watch (inside weekly run)",
        "type": "file_mtime",
        "path": str(ROOT / "data" / "vertex_model_versions.json"),
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
    # Quarterly depth reviews of crumbl-ops, one state file each so a single dead
    # review is not hidden by the others (a newest-of-glob check would be).
    *({
        "name": f"depth-review-{r} (quarterly)",
        "type": "json_last_run",
        "path": str(HOME / ".claude" / "depth-reviews" / f"{r}.json"),
        "max_age_days": 100,
    } for r in ("database", "tenant-isolation", "module-boundaries", "failure-modes")),
]

REPO = "michaeladickson/best-practices"
ISSUE_TITLE = "Heartbeat: scheduled job(s) stale"


def _newest_mtime(pattern: str):
    paths = glob.glob(pattern)
    if not paths:
        return None
    return max(Path(p).stat().st_mtime for p in paths)


def _newest_last_run(pattern: str):
    """(newest last_run as a timestamp or None, [(path, why) for each file that
    exists but gives no readable last_run])."""
    newest, unreadable = None, []
    for p in glob.glob(pattern):
        try:
            # utf-8-sig: PowerShell 5.1 writes UTF-8 with a byte order mark.
            with open(p, encoding="utf-8-sig") as f:
                raw = json.load(f).get("last_run")
            if not raw:
                raise ValueError("no last_run")
            ts = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if newest is None or ts > newest:
                newest = ts
        except (json.JSONDecodeError, ValueError, OSError, AttributeError) as e:
            unreadable.append((p, f"{type(e).__name__}: {e}"[:120]))
    return (newest.timestamp() if newest else None), unreadable


def run_checks():
    now = datetime.now(timezone.utc).timestamp()
    results = []
    for check in CHECKS:
        if check["type"] == "file_mtime":
            ts, unreadable = _newest_mtime(check["path"]), []
        else:
            ts, unreadable = _newest_last_run(check["path"])
        if unreadable:
            path, why = unreadable[0]
            results.append((check["name"], "UNREADABLE", f"{path}: {why}"))
            continue
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
              "(the WM-WeeklyDigest failure mode). An unreadable one means its state "
              "file exists but this check cannot read it, so it could not go stale "
              "either. Check the job's own logs/state, fix, then close this issue.")
    subprocess.run(["gh", "issue", "create", "--repo", REPO,
                    "--title", ISSUE_TITLE, "--body", body],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
    print("Filed heartbeat issue.")


def main():
    results = run_checks()
    width = max(len(n) for n, _, _ in results)
    for name, status, detail in results:
        print(f"{name:<{width}}  {status:<10} {detail}")
    stale = [r for r in results if r[1] in ("STALE", "UNREADABLE")]
    if stale:
        if "--no-issue" not in sys.argv:
            file_issue(stale)
        sys.exit(1)


if __name__ == "__main__":
    main()
