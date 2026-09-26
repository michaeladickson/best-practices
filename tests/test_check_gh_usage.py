"""Per-workflow attribution in scripts/check_gh_usage.py.

When the week-over-week minutes tripwire fires, the script rebuilds billed
Actions minutes from the runs and jobs APIs and publishes them only if they
tie back to the billing usage API. These tests pin the rules that make the
tie hold, the checks that make a partial read fail loudly, and that the quiet
weekly run never touches the Actions API.

Fixtures copy the real payload shapes (captured 2026-09-26) with synthetic
values: this repo is public, so no spend data or private-repo detail. Three
job shapes decide what a job bills, and each one is real:

  ran on a runner        runner_name "GitHub Actions <id>", group "GitHub Actions"
  skipped                runner_id, runner_name and group all null
  cancelled pre-runner   runner_id 0, runner_name "" (empty, not null)

Skipped and cancelled jobs carry started_at == completed_at, and a past run's
pull_requests list is usually empty even on pull_request events, which is why
PRs are counted by head_branch. No network: gh_json is replaced by a fake that
serves these payloads the way `gh api` does.
"""
import re
import subprocess
import threading
from datetime import date, datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit

import pytest

from scripts import check_gh_usage as ghu

OWNER, NAME = "octo", "example"
REPO = f"{OWNER}/{NAME}"
TODAY = date(2026, 3, 16)
OLDER, NEWER = ghu.wow_weeks(TODAY)  # 3/2..3/8 and 3/9..3/15


def at(day: date, hh: int = 12, mm: int = 0, ss: int = 0) -> str:
    return datetime(day.year, day.month, day.day, hh, mm, ss,
                    tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def plus(stamp: str, seconds: int) -> str:
    t = datetime.fromisoformat(stamp.replace("Z", "+00:00")) + timedelta(seconds=seconds)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def run(run_id, created, *, path=".github/workflows/ci.yml", name="CI",
        event="pull_request", branch="feature/a", updated=None, attempt=1):
    """One element of actions/runs .workflow_runs, with the real key set."""
    api = f"https://api.github.com/repos/{REPO}/actions/runs/{run_id}"
    return {
        "id": run_id, "name": name, "node_id": f"WFR_{run_id}",
        "head_branch": branch, "head_sha": "0" * 40, "path": path,
        "display_title": "synthetic", "run_number": run_id, "event": event,
        "status": "completed", "conclusion": "success", "workflow_id": 1,
        "check_suite_id": run_id, "check_suite_node_id": f"CS_{run_id}",
        "url": api, "html_url": f"https://github.com/{REPO}/actions/runs/{run_id}",
        "pull_requests": [], "created_at": created,
        "updated_at": updated or created, "actor": {}, "run_attempt": attempt,
        "referenced_workflows": [], "run_started_at": created,
        "triggering_actor": {}, "jobs_url": f"{api}/jobs",
        "logs_url": f"{api}/logs", "check_suite_url": f"{api}/check-suite",
        "artifacts_url": f"{api}/artifacts", "cancel_url": f"{api}/cancel",
        "rerun_url": f"{api}/rerun", "previous_attempt_url": None,
        "workflow_url": f"https://api.github.com/repos/{REPO}/actions/workflows/1",
        "head_commit": {}, "repository": {}, "head_repository": {},
    }


def job(job_id, run_id, started, seconds, *, shape="hosted", attempt=1):
    """One element of actions/runs/{id}/jobs .jobs, with the real key set.
    shape: hosted | skipped | cancelled (before a runner) | self-hosted. The
    self-hosted values are not captured (no such runner exists); what the code
    keys on is the "self-hosted" label GitHub gives every such runner."""
    ran = shape in ("hosted", "self-hosted")
    runner = {
        "hosted": (1000000001, "GitHub Actions 1000000001", 0, "GitHub Actions"),
        "self-hosted": (7, "build-box", 1, "Default"),
        "skipped": (None, None, None, None),
        "cancelled": (0, "", 0, ""),
    }[shape]
    api = f"https://api.github.com/repos/{REPO}/actions/jobs/{job_id}"
    return {
        "id": job_id, "run_id": run_id, "workflow_name": "CI",
        "head_branch": "feature/a",
        "run_url": f"https://api.github.com/repos/{REPO}/actions/runs/{run_id}",
        "run_attempt": attempt, "node_id": f"CR_{job_id}", "head_sha": "0" * 40,
        "url": api, "html_url": f"https://github.com/{REPO}/actions/runs/{run_id}/job/{job_id}",
        "status": "completed",
        "conclusion": {"skipped": "skipped", "cancelled": "cancelled"}.get(shape, "success"),
        "created_at": started, "started_at": started,
        "completed_at": plus(started, seconds if ran else 0),
        "name": "test",
        "steps": [{"name": "Set up job", "status": "completed", "conclusion": "success",
                   "number": 1, "started_at": started, "completed_at": started}] if ran else [],
        "check_run_url": f"https://api.github.com/repos/{REPO}/check-runs/{job_id}",
        "labels": ["self-hosted", "linux"] if shape == "self-hosted" else ["ubuntu-latest"],
        "runner_id": runner[0], "runner_name": runner[1],
        "runner_group_id": runner[2], "runner_group_name": runner[3],
    }


def usage(day: date, minutes: float, repo: str = NAME):
    """One billing usage item (users/{u}/settings/billing/usage), real key set."""
    return {"date": f"{day.isoformat()}T00:00:00Z", "product": "actions",
            "sku": "Actions Linux", "quantity": float(minutes), "unitType": "Minutes",
            "pricePerUnit": 0.006, "grossAmount": minutes * 0.006,
            "discountAmount": minutes * 0.006, "netAmount": 0.0,
            "repositoryName": repo}


class FakeGitHub:
    """Serves the runs, jobs and rate_limit endpoints from fixtures, paging
    the way the API does. Records every path it is asked for."""

    def __init__(self, runs=(), jobs=None, remaining=5000):
        self.runs, self.jobs, self.remaining = list(runs), jobs or {}, remaining
        self.calls, self.lock = [], threading.Lock()

    def __call__(self, path):
        with self.lock:
            self.calls.append(path)
        if path == "rate_limit":
            return {"resources": {"core": {"limit": 5000, "remaining": self.remaining,
                                           "reset": 1773630000, "used": 0}}}
        url = urlsplit(path)
        q = parse_qs(url.query)
        page, per_page = int(q["page"][0]), int(q["per_page"][0])
        m = re.fullmatch(rf"repos/{REPO}/actions/runs/(\d+)/jobs", url.path)
        if m:
            assert q["filter"] == ["all"], "re-run attempts bill too"
            key, rows = "jobs", self.jobs.get(int(m.group(1)), [])
        else:
            assert url.path == f"repos/{REPO}/actions/runs", path
            lo, hi = q["created"][0].split("..")
            key = "workflow_runs"
            rows = sorted((r for r in self.runs if lo <= r["created_at"] <= hi),
                          key=lambda r: r["created_at"], reverse=True)
        return {"total_count": self.total(rows),
                key: rows[(page - 1) * per_page:page * per_page]}

    def total(self, rows):
        return len(rows)

    def job_calls(self):
        return [c for c in self.calls if "/jobs?" in c]


@pytest.fixture(autouse=True)
def _synthetic_owner(monkeypatch):
    monkeypatch.setattr(ghu, "GH_USER", OWNER)


# --- What one job bills ------------------------------------------------------

@pytest.mark.parametrize("seconds, billed", [(1, 1), (60, 1), (61, 2), (250, 5)])
def test_a_job_bills_its_runner_time_rounded_up_to_the_minute(seconds, billed):
    assert ghu.billed_minutes(job(1, 1, at(OLDER[0]), seconds)) == billed


@pytest.mark.parametrize("shape", ["skipped", "cancelled", "self-hosted"])
def test_jobs_without_a_hosted_runner_bill_nothing(shape):
    assert ghu.billed_minutes(job(1, 1, at(OLDER[0]), 600, shape=shape)) == 0


# --- Bucketing ---------------------------------------------------------------

def test_minutes_land_on_the_day_the_job_completed_runs_on_the_day_created():
    last_older, first_newer = OLDER[-1], NEWER[0]
    r = run(1, at(last_older, 23, 58))
    flows, by_day = ghu.attribute(
        [r], {1: [job(10, 1, at(last_older, 23, 58), 300)]}, OLDER, NEWER)
    ci = flows[".github/workflows/ci.yml"]
    assert (ci["older"]["runs"], ci["older"]["minutes"]) == (1, 0)
    assert (ci["newer"]["runs"], ci["newer"]["minutes"]) == (0, 5)
    assert by_day == {first_newer: 5}


def test_a_run_from_before_the_window_adds_minutes_but_not_a_run():
    eve = OLDER[0] - timedelta(days=1)
    flows, by_day = ghu.attribute(
        [run(1, at(eve, 23, 50))], {1: [job(10, 1, at(eve, 23, 50), 1800)]},
        OLDER, NEWER)
    assert flows[".github/workflows/ci.yml"]["older"]["runs"] == 0
    assert by_day == {OLDER[0]: 30}


def test_jobs_finishing_after_the_window_are_left_out():
    r = run(1, at(NEWER[-1], 23, 55))
    flows, by_day = ghu.attribute(
        [r], {1: [job(10, 1, at(NEWER[-1], 23, 55), 900)]}, OLDER, NEWER)
    assert flows[".github/workflows/ci.yml"]["newer"]["runs"] == 1
    assert by_day == {}


def test_every_attempt_of_a_rerun_bills():
    started = at(NEWER[2], 2, 0)
    jobs = [job(10, 1, started, 0, shape="cancelled", attempt=1),
            job(11, 1, plus(started, 600), 200, attempt=2)]
    _, by_day = ghu.attribute([run(1, started, attempt=2)], {1: jobs}, OLDER, NEWER)
    assert by_day == {NEWER[2]: 4}


def test_trigger_split_and_runs_per_pr_branch():
    runs = [run(1, at(NEWER[0], 9), branch="feature/a"),
            run(2, at(NEWER[0], 10), branch="feature/a"),
            run(3, at(NEWER[1], 9), branch="feature/a"),
            run(4, at(NEWER[1], 10), branch="feature/b"),
            run(5, at(NEWER[2]), event="workflow_dispatch", branch="main")]
    jobs = {i: [job(i * 10, i, at(NEWER[0]), 600)] for i in range(1, 6)}
    flows, _ = ghu.attribute(runs, jobs, OLDER, NEWER)
    ci = flows[".github/workflows/ci.yml"]
    assert ci["newer"]["events"] == {"pull_request": [4, 40], "workflow_dispatch": [1, 10]}
    assert ghu._events_cell(ci) == ("pull_request 0/0 -> 4/40; "
                                    "workflow_dispatch 0/0 -> 1/10")
    assert ghu._per_branch_cell(ci) == "- -> 2.00 (0 -> 2 branches)"


# --- Listing: a partial read must fail, never publish -------------------------

def test_day_listing_pages_through_every_run(monkeypatch):
    fake = FakeGitHub([run(i, at(OLDER[0], 0, i // 60, i % 60)) for i in range(137)])
    monkeypatch.setattr(ghu, "gh_json", fake)
    listed = ghu.list_day_runs(REPO, OLDER[0])
    assert sorted(r["id"] for r in listed) == list(range(137))
    assert len(fake.calls) == 2


def test_day_listing_fails_when_rows_go_missing(monkeypatch):
    fake = FakeGitHub([run(i, at(OLDER[0], 1, i)) for i in range(37)])
    fake.total = lambda rows: len(rows) + 3
    monkeypatch.setattr(ghu, "gh_json", fake)
    with pytest.raises(ghu.GhError, match="total_count 40 but 37 came back"):
        ghu.list_day_runs(REPO, OLDER[0])


def test_day_listing_fails_past_the_1000_result_cap(monkeypatch):
    runs = [run(i, at(OLDER[0], i // 3600 % 24, i // 60 % 60, i % 60))
            for i in range(1200)]
    monkeypatch.setattr(ghu, "gh_json", FakeGitHub(runs))
    with pytest.raises(ghu.GhError, match="past the 1,000-result cap"):
        ghu.list_day_runs(REPO, OLDER[0])


# --- End to end through build(): tie, publish, withhold -----------------------

def scenario(extra_billed=None):
    """A repo whose PR workflow doubles its runs per branch week over week.

    Billed minutes per day are the test's own statement of what GitHub bills
    (each job's minutes written out by hand), not a re-run of the code's rule.
    """
    runs, jobs, billed = [], {}, {}
    ids = iter(range(1, 100000))

    def add(created, seconds, bills, *, shape="hosted", **kw):
        rid = next(ids)
        runs.append(run(rid, created, **kw))
        jobs[rid] = [job(rid * 10, rid, created, seconds, shape=shape)]
        done = datetime.fromisoformat(plus(created, seconds).replace("Z", "+00:00")).date()
        billed[done] = billed.get(done, 0) + bills
        return rid

    for i, day in enumerate(OLDER + NEWER):
        per_branch = 2 if day in OLDER else 4
        for n in range(per_branch):  # 30-minute CI job, one branch per day
            add(at(day, 9 + n), 1800, 30, branch=f"feature/{i}")
        add(at(day, 3), 180, 3, path=".github/workflows/nightly.yml",
            name="Nightly", event="schedule", branch="main")
        if day in NEWER:  # a 10-second status job on every push bills a minute
            for n in range(per_branch):
                add(at(day, 9 + n, 1), 10, 1, path=".github/workflows/status.yml",
                    name="Status", branch=f"feature/{i}")
        add(at(day, 20), 0, 0, shape="skipped", path=".github/workflows/deploy.yml",
            name="Deploy", event="push", branch="main")
    # Created before the window, finishing inside it: minutes count, the run
    # does not. And a run finishing today, whose minutes neither side counts.
    eve = OLDER[0] - timedelta(days=1)
    add(at(eve, 23, 50), 1800, 30, branch="feature/eve",
        updated=plus(at(eve, 23, 50), 1800))
    add(at(NEWER[-1], 23, 55), 900, 15, path=".github/workflows/nightly.yml",
        name="Nightly", event="schedule", branch="main")
    for day, extra in (extra_billed or {}).items():
        billed[day] = billed.get(day, 0) + extra
    items = [usage(d, m) for d, m in billed.items() if d.month == TODAY.month]
    return items, runs, jobs


def run_build(monkeypatch, items, fake, attribute_anyway=False):
    monkeypatch.setattr(ghu, "fetch_month", lambda y, m: items if m == TODAY.month else [])
    monkeypatch.setattr(ghu, "gh_json", fake)
    cur, prev, alerts, ctx = ghu.build(TODAY, attribute_anyway=attribute_anyway)
    return alerts, ctx, ghu.render(cur, prev, alerts, ctx, TODAY)


def test_jump_is_attributed_per_workflow_and_ties(monkeypatch, capsys):
    items, runs, jobs = scenario()
    alerts, ctx, report = run_build(monkeypatch, items, FakeGitHub(runs, jobs))

    assert any("week-over-week" in a for a in alerts)
    (res,) = ctx["attribution"]["repos"]
    assert res["status"] == "ok"
    # Older: 7 x (2 x 30 + 3) + 30 from the run created the evening before.
    # Newer: 7 x (4 x 30 + 3 + 4); the run finishing today counts nowhere.
    assert (res["ties"]["older"].attributed, res["ties"]["older"].billed) == (471, 471)
    assert (res["ties"]["newer"].attributed, res["ties"]["newer"].billed) == (889, 889)

    table = report.split("## Actions minutes by workflow")[1]
    assert ("| CI (`ci.yml`) | 14 -> 28 | 450 -> 840 | +390 | pull_request "
            "| 2.00 -> 4.00 (7 -> 7 branches) |") in table
    assert "| Status (`status.yml`) | 0 -> 28 | 0 -> 28 | +28 |" in table
    assert "| Nightly (`nightly.yml`) | 7 -> 8 | 21 -> 21 | +0 | schedule |  |" in table
    assert "| Deploy (`deploy.yml`) | 7 -> 7 | 0 -> 0 | +0 | push |  |" in table
    assert "| **Total** | 28 -> 71 | 471 -> 889 | +418 | | |" in table
    assert ("By trigger (minutes): pull_request 450 -> 868 (+418); "
            "schedule 21 -> 21 (+0). PR branches with runs: 7 -> 7; "
            "pull_request minutes per branch: 64.3 -> 124.0.") in table
    assert "Ties to the billing usage API: older week 471 of 471" in table

    printed = capsys.readouterr().out
    assert f"  {OLDER[0]}      93        93      +0" in printed  # 60 + 3 + 30 from the eve
    assert "newer week: 889 vs 889 (+0.0%): ties" in printed


def test_attribution_that_does_not_tie_is_withheld(monkeypatch, capsys):
    items, runs, jobs = scenario(extra_billed={NEWER[3]: 60})  # 60 unexplained
    _, ctx, report = run_build(monkeypatch, items, FakeGitHub(runs, jobs))

    assert ctx["attribution"]["repos"][0]["status"] == "withheld"
    assert "Withheld: the attribution does not tie" in report
    assert "| Workflow |" not in report
    assert "OFF, attribution withheld" in capsys.readouterr().out


def test_quiet_week_never_calls_the_actions_api(monkeypatch):
    items = [usage(d, 100) for d in OLDER + NEWER]
    fake = FakeGitHub()
    alerts, ctx, report = run_build(monkeypatch, items, fake)
    assert not alerts and ctx["attribution"] is None
    assert fake.calls == []
    assert "## Actions minutes by workflow" not in report


def test_low_rate_limit_skips_before_reading_jobs(monkeypatch):
    items, runs, jobs = scenario()
    fake = FakeGitHub(runs, jobs, remaining=150)
    _, ctx, report = run_build(monkeypatch, items, fake)
    assert "150 are left" in ctx["attribution"]["skipped"]
    assert fake.job_calls() == []
    assert "Not attributed: reading jobs needs about" in report


def test_a_failed_listing_is_reported_not_published(monkeypatch):
    items, runs, jobs = scenario()
    fake = FakeGitHub(runs, jobs)

    def flaky(path):
        if NEWER[3].isoformat() in path and "/jobs" not in path:
            raise ghu.GhError(f"gh api {path}: HTTP 502")
        return fake(path)

    _, ctx, report = run_build(monkeypatch, items, flaky)
    (res,) = ctx["attribution"]["repos"]
    assert res["status"] == "failed" and "1 of 16 day listings failed" in res["reason"]
    assert "| Workflow |" not in report


def test_attribute_flag_runs_it_without_the_tripwire(monkeypatch):
    items = [usage(d, 100) for d in OLDER + NEWER]
    _, ctx, _ = run_build(monkeypatch, items, FakeGitHub(), attribute_anyway=True)
    (res,) = ctx["attribution"]["repos"]
    assert res["status"] == "withheld"  # 700 billed a week, nothing listed


# --- gh wrapper -----------------------------------------------------------------

def test_gh_json_retries_a_502_and_fails_fast_on_a_404(monkeypatch):
    replies = [(1, "", "gh: Server Error (HTTP 502)"), (0, '{"ok": true}', ""),
               (1, "", "gh: Not Found (HTTP 404)"), (0, '{"never": "reached"}', "")]
    monkeypatch.setattr(ghu.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(
        a[0], *replies.pop(0)))
    monkeypatch.setattr(ghu.time, "sleep", lambda s: None)
    assert ghu.gh_json("repos/x/y") == {"ok": True}
    with pytest.raises(ghu.GhError, match="HTTP 404"):
        ghu.gh_json("repos/x/y")
    assert len(replies) == 1
