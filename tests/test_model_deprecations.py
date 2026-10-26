"""The Gemini deprecations-page watch in digest/model_pricing.py (#32).

The two outcomes that matter: a watched row gaining a shutdown date files an
issue, and a page that cannot be read is reported as unreadable rather than as
"nothing announced". No network: the page is a fixture shaped like the real
one (h2 per family, a Model / Release date / Shutdown date / Recommended
replacement header row, single-cell "Preview models" divider rows).
"""
import json

import pytest

from digest import model_pricing as mp

NO_DATE = mp.NO_SHUTDOWN_DATE


def _page(rows, header=("Model", "Release date", "Shutdown date", "Recommended replacement")):
    head = "".join(f"<th>{h}</th>" for h in header)
    body = "".join(
        "<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return (f"<html><body><h2>Gemini 2.5 Flash models</h2><table><tr>{head}</tr>"
            f"<tr><td colspan='4'>Preview models</td></tr>{body}</table></body></html>")


BASE_ROWS = [
    ("gemini-2.5-flash", "June 17, 2025", NO_DATE, ""),
    ("gemini-2.5-pro", "June 17, 2025", NO_DATE, ""),
    ("gemini-2.5-flash-lite", "July 22, 2025", NO_DATE, ""),
    ("gemini-2.5-flash-preview-05-20", "May 20, 2025", "November 18, 2025", "gemini-3.6-flash"),
    ("gemini-3.8-flash", "September 2, 2026", NO_DATE, ""),
]


@pytest.fixture(autouse=True)
def _small_page_ok(monkeypatch):
    monkeypatch.setattr(mp, "MIN_PAGE_ROWS", 3)


def _snapshot(rows):
    return {"fetched_at": "2026-10-23 22:00 UTC", "models": mp.watched(mp.parse_deprecations(_page(rows)))}


def test_parse_reads_shutdown_by_header_and_skips_dividers():
    rows = mp.parse_deprecations(_page(BASE_ROWS))
    assert rows["gemini-2.5-flash"]["shutdown"] == NO_DATE
    assert rows["gemini-2.5-flash-preview-05-20"]["replacement"] == "gemini-3.6-flash"
    assert "Preview models" not in rows
    assert set(mp.watched(rows)) == {m for m, *_ in BASE_ROWS if m.startswith("gemini-2.5-")}


def test_parse_follows_a_reordered_shutdown_column():
    header = ("Model", "Shutdown date", "Release date", "Recommended replacement")
    rows = [(m, s, r, rep) for m, r, s, rep in BASE_ROWS]
    assert mp.parse_deprecations(_page(rows, header))["gemini-2.5-flash-preview-05-20"][
        "shutdown"] == "November 18, 2025"


@pytest.mark.parametrize("page, why", [
    ("<html><body>Something went wrong</body></html>", "no table"),
    (_page(BASE_ROWS, header=("Model", "Release date", "Retirement", "Replacement")), "no table"),
    (_page(BASE_ROWS[:1]), "rows parsed"),
    (_page([r for r in BASE_ROWS if r[0] != "gemini-2.5-flash"]), "not on the page"),
])
def test_unrecognisable_page_raises_instead_of_reading_as_quiet(page, why):
    with pytest.raises(mp.PageUnreadable, match=why):
        mp.parse_deprecations(page)


def test_in_use_model_gaining_a_date_is_reported():
    old = _snapshot(BASE_ROWS)
    new_rows = [("gemini-2.5-flash", "June 17, 2025", "June 17, 2027", "gemini-3.5-flash-lite"),
                *BASE_ROWS[1:]]
    changes = mp.diff_deprecations(old, mp.watched(mp.parse_deprecations(_page(new_rows))))
    assert changes == ['**gemini-2.5-flash** shutdown date "No shutdown date announced" -> '
                       '"June 17, 2027" (replacement: gemini-3.5-flash-lite)']


def test_new_rows_report_only_when_dated_and_baseline_reports_nothing():
    old = _snapshot(BASE_ROWS)
    new_rows = [*BASE_ROWS,
                ("gemini-2.5-flash-tts", "May 20, 2025", "November 17, 2026", ""),
                ("gemini-2.5-flash-live", "May 20, 2025", NO_DATE, "")]
    new = mp.watched(mp.parse_deprecations(_page(new_rows)))
    assert mp.diff_deprecations(old, new) == [
        '**gemini-2.5-flash-tts** added with shutdown date "November 17, 2026"']
    assert mp.diff_deprecations({}, new) == []


def test_undated_row_leaving_is_reported_dated_row_leaving_is_not():
    old = _snapshot(BASE_ROWS)
    gone = {"gemini-2.5-flash-lite", "gemini-2.5-flash-preview-05-20"}
    new = mp.watched(mp.parse_deprecations(_page([r for r in BASE_ROWS if r[0] not in gone])))
    assert mp.diff_deprecations(old, new) == [
        "**gemini-2.5-flash-lite** left the page with no shutdown date ever listed"]


class _Resp:
    def __init__(self, body):
        self._body = body.encode()

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture
def env(monkeypatch, tmp_path):
    """Snapshot in tmp, gh recorded instead of run, page served from a variable."""
    calls = []
    state = {"page": _page(BASE_ROWS), "gh_rc": 0}

    def fake_gh(*args):
        calls.append(args)
        stdout = "[]" if args[:2] == ("issue", "list") else "https://github.com/x/y/issues/1"
        return type("R", (), {"returncode": state["gh_rc"], "stdout": stdout, "stderr": ""})()

    def fake_urlopen(req, timeout=None):
        if isinstance(state["page"], Exception):
            raise state["page"]
        return _Resp(state["page"])

    monkeypatch.setattr(mp, "DEPRECATIONS_SNAPSHOT", tmp_path / "model_deprecations.json")
    monkeypatch.setattr(mp, "_gh", fake_gh)
    monkeypatch.setattr(mp.urllib.request, "urlopen", fake_urlopen)
    return state, calls


def test_failed_fetch_files_unreadable_issue_and_keeps_snapshot(env):
    state, calls = env
    assert mp.check_deprecations(dry_run=False)  # baseline
    before = mp.DEPRECATIONS_SNAPSHOT.read_text(encoding="utf-8")

    state["page"] = OSError("HTTP Error 503: Service Unavailable")
    assert mp.check_deprecations(dry_run=False) is False
    created = [c for c in calls if c[:2] == ("issue", "create")]
    assert len(created) == 1 and mp.UNREADABLE_ISSUE_TITLE in created[0]
    assert mp.DEPRECATIONS_SNAPSHOT.read_text(encoding="utf-8") == before


def test_date_change_files_issue_and_advances_snapshot(env):
    state, calls = env
    assert mp.check_deprecations(dry_run=False)
    assert not [c for c in calls if c[:2] == ("issue", "create")]  # baseline files nothing

    state["page"] = _page([("gemini-2.5-flash", "June 17, 2025", "June 17, 2027", ""),
                           *BASE_ROWS[1:]])
    assert mp.check_deprecations(dry_run=False)
    created = [c for c in calls if c[:2] == ("issue", "create")]
    assert len(created) == 1 and mp.DEPRECATION_ISSUE_TITLE in created[0]
    snap = json.loads(mp.DEPRECATIONS_SNAPSHOT.read_text(encoding="utf-8"))
    assert snap["models"]["gemini-2.5-flash"]["shutdown"] == "June 17, 2027"


def test_unfiled_change_keeps_old_snapshot_so_it_refiles(env):
    state, _ = env
    assert mp.check_deprecations(dry_run=False)
    state["page"] = _page([("gemini-2.5-flash", "June 17, 2025", "June 17, 2027", ""),
                           *BASE_ROWS[1:]])
    state["gh_rc"] = 1
    assert mp.check_deprecations(dry_run=False) is False
    snap = json.loads(mp.DEPRECATIONS_SNAPSHOT.read_text(encoding="utf-8"))
    assert snap["models"]["gemini-2.5-flash"]["shutdown"] == NO_DATE
