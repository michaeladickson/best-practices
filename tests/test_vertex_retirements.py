"""The Vertex model-versions watch in digest/model_pricing.py.

Vertex keeps its own retirement calendar, apart from AI Studio's deprecations
page. The watch reads the Gemini ids each Vertex-calling repo pins and files in
that repo when one gains a fixed retirement date, gets a different one, or
leaves the page, or when a repo starts calling a model that already has one.
No network: the page is a fixture shaped like the live one (2026-11-09), and gh
is recorded instead of run.

Live shape: an h3 per table ("Gemini models", "Models available for shorter
availability periods", "Retired models"), a Model ID / Release date /
Retirement date / Replacement model ID header (the retired table says
"Recommended upgrade"), and retirement cells that are either a fixed date or a
floor ("May 19, 2027 or later", "No sooner than May 20, 2028").
"""
import json

import pytest

from digest import model_pricing as mp

HEADER = ("Model ID", "Release date", "Retirement date", "Replacement model ID")
RETIRED_HEADER = ("Model ID", "Release date", "Retirement date", "Recommended upgrade")
UNDATED = "No retirement date announced"

LATEST = [
    ("gemini-3.8-flash", "September 2, 2026", "September 2, 2027 or later", ""),
    ("gemini-3.5-flash", "May 19, 2026", "May 19, 2027 or later", ""),
    ("gemini-2.5-flash", "June 17, 2025", "October 20, 2026",
     "gemini-3.8-flash or gemini-3.5-flash-lite"),
    ("gemini-embedding-001", "May 20, 2025", "No sooner than May 20, 2028", ""),
]
SHORTER = [
    ("gemini-3.6-flash", "July 21, 2026", UNDATED, ""),
    ("gemini-3.7-flash", "August 13, 2026", "January 28, 2027", "gemini-3.8-flash"),
]
RETIRED = [("gemini-2.0-flash", "February 5, 2025", "June 1, 2026", "gemini-3.5-flash-lite")]
# gemini-3.6-flash as the live page had it on 2026-11-09.
SHORTER_DATED = [("gemini-3.6-flash", "July 21, 2026", "November 19, 2026", "gemini-3.8-flash"),
                 *SHORTER[1:]]

OPS, WM = "o/ops", "o/wm"
CALLERS = {OPS: ["gemini-3.6-flash", "gemini-3.8-flash"], WM: ["gemini-2.5-flash"]}


def _table(header, rows):
    head = "".join(f"<th>{c}</th>" for c in header)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def _page(latest=LATEST, shorter=SHORTER, retired=RETIRED, header=HEADER):
    return (
        "<html><body><h1>Model versions and lifecycle</h1>"
        '<h2 id="latest-models">Latest available models</h2>'
        "<h3>Models available for at least 12 months after release</h3><p>Tables.</p>"
        f"<h3>Gemini models</h3>{_table(header, latest)}"
        f"<h3>Models available for shorter availability periods</h3>{_table(header, shorter)}"
        "<h3>Retired models</h3>"
        "<h4>The following table lists the retired models (click to expand)</h4>"
        f"{_table(RETIRED_HEADER, retired)}"
        "<h2>What's next</h2></body></html>")


def _snapshot(page=None, callers=CALLERS):
    return {"fetched_at": "2026-11-06 22:00 UTC", "callers": callers,
            "models": mp.parse_vertex_versions(page or _page())}


@pytest.fixture(autouse=True)
def _small_page_ok(monkeypatch):
    monkeypatch.setattr(mp, "MIN_VERTEX_ROWS", 3)
    monkeypatch.setattr(mp, "VERTEX_CALLERS", {OPS: "tests/pins.py", WM: "tests/pins.py"})


def test_parse_reads_every_table_by_header():
    rows = mp.parse_vertex_versions(_page(shorter=SHORTER_DATED))
    assert rows["gemini-3.6-flash"] == {
        "section": "Models available for shorter availability periods",
        "retirement": "November 19, 2026", "replacement": "gemini-3.8-flash"}
    assert rows["gemini-2.0-flash"] == {
        "section": "Retired models", "retirement": "June 1, 2026",
        "replacement": "gemini-3.5-flash-lite"}
    assert rows["gemini-3.8-flash"]["section"] == "Gemini models"
    assert "Model ID" not in rows
    assert len(rows) == len(LATEST) + len(SHORTER) + len(RETIRED)


def test_parse_follows_a_reordered_retirement_column():
    header = ("Model ID", "Retirement date", "Release date", "Replacement model ID")
    shorter = [(m, ret, rel, rep) for m, rel, ret, rep in SHORTER_DATED]
    latest = [(m, ret, rel, rep) for m, rel, ret, rep in LATEST]
    rows = mp.parse_vertex_versions(_page(latest=latest, shorter=shorter, header=header))
    assert rows["gemini-3.6-flash"]["retirement"] == "November 19, 2026"


@pytest.mark.parametrize("page, why", [
    ("<html><body>Something went wrong</body></html>", "no table"),
    (_page(header=("Model ID", "Release date", "End of life", "Replacement")).replace(
        "Retirement date", "End of support"), "no table"),
    (_page(latest=LATEST[:1], shorter=[], retired=[]), "rows parsed"),
], ids=["error page", "renamed column", "too few rows"])
def test_unrecognisable_page_raises_instead_of_reading_as_undated(page, why):
    with pytest.raises(mp.PageUnreadable, match=why):
        mp.parse_vertex_versions(page)


@pytest.mark.parametrize("cell, expected", [
    ("November 19, 2026", "2026-11-19"),
    ("January 28, 2027", "2027-01-28"),
    ("September 2, 2027 or later", None),
    ("No sooner than May 20, 2028", None),
    (UNDATED, None),
    ("", None),
    # A shape the parser does not know is filed as written, not skipped.
    ("Nov. 19, 2026", "Nov. 19, 2026"),
])
def test_retirement_date_separates_fixed_dates_from_floors(cell, expected):
    assert mp.retirement_date(cell) == expected


def _gh_returning(stdout, rc=0):
    def fake(*args):
        return type("R", (), {"returncode": rc, "stdout": stdout, "stderr": "boom"})()
    return fake


def test_pinned_ids_read_the_set_literal_and_keep_only_gemini(monkeypatch):
    src = ('"""Doc naming gemini-1.0-pro."""\n'
           "EXPECTED_MODEL_STRINGS = {\n"
           "    # comment naming gemini-2.0-flash\n"
           '    "gemini-3.8-flash",\n    "claude-opus-5-5",\n    "gemini-3.6-flash",\n}\n')
    monkeypatch.setattr(mp, "_gh", _gh_returning(src))
    assert mp.pinned_gemini_ids(OPS, "tests/pins.py") == ["gemini-3.6-flash", "gemini-3.8-flash"]

    monkeypatch.setattr(mp, "_gh", _gh_returning(
        'EXPECTED_MODEL_STRINGS: set[str] = {"gemini-2.5-flash"}\n'))
    assert mp.pinned_gemini_ids(WM, "tests/pins.py") == ["gemini-2.5-flash"]


@pytest.mark.parametrize("stdout, rc", [
    ("MODELS = {'gemini-3.8-flash'}\n", 0),
    ("", 1),
], ids=["no literal", "gh failed"])
def test_unreadable_pin_file_raises_instead_of_reading_as_no_models(monkeypatch, stdout, rc):
    monkeypatch.setattr(mp, "_gh", _gh_returning(stdout, rc))
    with pytest.raises(RuntimeError):
        mp.pinned_gemini_ids(OPS, "tests/pins.py")


def test_baseline_reports_nothing():
    assert mp.diff_vertex({}, mp.parse_vertex_versions(_page(shorter=SHORTER_DATED)),
                          CALLERS) == []


def test_called_model_gaining_a_date_files_in_the_repo_that_calls_it():
    rows = mp.parse_vertex_versions(_page(shorter=SHORTER_DATED))
    [f] = mp.diff_vertex(_snapshot(), rows, CALLERS)
    assert (f["repo"], f["title"], f["key"]) == (
        OPS, "Vertex retires gemini-3.6-flash on 2026-11-19", "2026-11-19")
    assert 'previous weekly check read "No retirement date announced"' in f["detail"]
    assert "Replacement: gemini-3.8-flash." in f["detail"]


def test_a_date_moving_files_again_with_the_new_date():
    old = _snapshot(_page(shorter=SHORTER_DATED))
    later = [("gemini-3.6-flash", "July 21, 2026", "December 3, 2026", "gemini-3.8-flash"),
             *SHORTER[1:]]
    [f] = mp.diff_vertex(old, mp.parse_vertex_versions(_page(shorter=later)), CALLERS)
    assert f["title"] == "Vertex retires gemini-3.6-flash on 2026-12-03"


def test_floors_moving_unchanged_dates_and_uncalled_models_report_nothing():
    latest = [("gemini-3.8-flash", "September 2, 2026", "December 1, 2027 or later", ""),
              *LATEST[1:]]
    shorter = [SHORTER[0], ("gemini-3.7-flash", "August 13, 2026", "March 1, 2027", "")]
    rows = mp.parse_vertex_versions(_page(latest=latest, shorter=shorter))
    # 3.8 floor moved, 2.5 still dated as before, 3.7 re-dated but nobody calls it.
    assert mp.diff_vertex(_snapshot(), rows, CALLERS) == []


def test_a_repo_starting_to_call_a_dated_model_files_and_an_undated_one_does_not():
    rows = mp.parse_vertex_versions(_page())
    callers = {**CALLERS, WM: ["gemini-2.5-flash", "gemini-3.5-flash", "gemini-3.7-flash"]}
    [f] = mp.diff_vertex(_snapshot(), rows, callers)
    assert (f["repo"], f["title"]) == (WM, "Vertex retires gemini-3.7-flash on 2027-01-28")
    assert "pinned it after the previous weekly check" in f["detail"]


def test_a_called_model_leaving_the_page_files_and_dropping_one_does_not():
    rows = mp.parse_vertex_versions(_page(shorter=SHORTER[1:]))
    [f] = mp.diff_vertex(_snapshot(), rows, CALLERS)
    title = "Vertex model-versions page does not list gemini-3.6-flash"
    assert (f["repo"], f["title"]) == (OPS, title)
    assert mp.diff_vertex(_snapshot(), rows, {OPS: ["gemini-3.8-flash"], WM: []}) == []


PINS = {OPS: ('EXPECTED_MODEL_STRINGS = {"gemini-3.6-flash", "gemini-3.8-flash", '
              '"claude-opus-5-5"}\n'),
        WM: 'EXPECTED_MODEL_STRINGS = {"gemini-2.5-flash", "claude-opus-5-5"}\n'}


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
    """Snapshot in tmp, gh recorded instead of run, page and pin files from state."""
    calls = []
    state = {"page": _page(), "pins": dict(PINS), "issues": [], "create_rc": 0}

    def fake_gh(*args):
        calls.append(args)
        rc, stdout = 0, ""
        if args[0] == "api":
            repo = next(r for r in state["pins"] if args[1].startswith(f"repos/{r}/"))
            stdout = state["pins"][repo]
            rc = 0 if stdout is not None else 1
        elif args[:2] == ("issue", "list"):
            stdout = json.dumps(state["issues"])
        elif args[:2] == ("issue", "create"):
            rc, stdout = state["create_rc"], "https://github.com/o/r/issues/9"
        return type("R", (), {"returncode": rc, "stdout": stdout or "", "stderr": ""})()

    def fake_urlopen(req, timeout=None):
        if isinstance(state["page"], Exception):
            raise state["page"]
        return _Resp(state["page"])

    monkeypatch.setattr(mp, "VERTEX_SNAPSHOT", tmp_path / "vertex_model_versions.json")
    monkeypatch.setattr(mp, "_gh", fake_gh)
    monkeypatch.setattr(mp.urllib.request, "urlopen", fake_urlopen)
    return state, calls


def _created(calls):
    return [c for c in calls if c[:2] == ("issue", "create")]


def _snap():
    return json.loads(mp.VERTEX_SNAPSHOT.read_text(encoding="utf-8"))


def test_baseline_writes_snapshot_and_files_nothing(env):
    _, calls = env
    assert mp.check_vertex_retirements(dry_run=False)
    assert not _created(calls)
    snap = _snap()
    assert snap["callers"] == {OPS: ["gemini-3.6-flash", "gemini-3.8-flash"],
                               WM: ["gemini-2.5-flash"]}
    assert snap["models"]["gemini-3.6-flash"]["retirement"] == UNDATED


def test_date_change_files_in_the_calling_repo_and_advances_snapshot(env):
    state, calls = env
    assert mp.check_vertex_retirements(dry_run=False)
    state["page"] = _page(shorter=SHORTER_DATED)
    assert mp.check_vertex_retirements(dry_run=False)
    [create] = _created(calls)
    assert create[create.index("--repo") + 1] == OPS
    assert create[create.index("--title") + 1] == "Vertex retires gemini-3.6-flash on 2026-11-19"
    assert _snap()["models"]["gemini-3.6-flash"]["retirement"] == "November 19, 2026"


def test_a_hand_filed_issue_naming_model_and_date_stops_a_duplicate(env):
    state, calls = env
    assert mp.check_vertex_retirements(dry_run=False)
    state["page"] = _page(shorter=SHORTER_DATED)
    carrier = "Vertex retires gemini-3.6-flash (GEMINI_FLASH) on 2026-11-19"
    state["issues"] = [{"number": 3833, "title": carrier}]
    assert mp.check_vertex_retirements(dry_run=False)
    assert not _created(calls)
    assert _snap()["models"]["gemini-3.6-flash"]["retirement"] == "November 19, 2026"


def test_an_issue_about_a_longer_id_is_not_taken_for_this_one(env):
    state, calls = env
    assert mp.check_vertex_retirements(dry_run=False)
    state["page"] = _page(shorter=SHORTER_DATED)
    state["issues"] = [{"number": 1, "title": "Vertex retires gemini-3.6-flash-lite on 2026-11-19"}]
    assert mp.check_vertex_retirements(dry_run=False)
    assert len(_created(calls)) == 1


def test_unfiled_finding_keeps_old_snapshot_so_it_refiles(env):
    state, calls = env
    assert mp.check_vertex_retirements(dry_run=False)
    state["page"] = _page(shorter=SHORTER_DATED)
    state["create_rc"] = 1
    assert mp.check_vertex_retirements(dry_run=False) is False
    assert _snap()["models"]["gemini-3.6-flash"]["retirement"] == UNDATED

    state["create_rc"] = 0
    assert mp.check_vertex_retirements(dry_run=False)
    assert len(_created(calls)) == 2  # the failed attempt and the retry


@pytest.mark.parametrize("break_it", [
    lambda s: s.update(page=OSError("HTTP Error 503: Service Unavailable")),
    lambda s: s.update(page="<html><body>Something went wrong</body></html>"),
    lambda s: s["pins"].update({WM: None}),
], ids=["fetch failed", "page unrecognisable", "pin file unreadable"])
def test_unreadable_input_files_here_and_keeps_snapshot(env, break_it):
    state, calls = env
    assert mp.check_vertex_retirements(dry_run=False)
    before = mp.VERTEX_SNAPSHOT.read_text(encoding="utf-8")

    break_it(state)
    assert mp.check_vertex_retirements(dry_run=False) is False
    [create] = _created(calls)
    assert create[create.index("--repo") + 1] == mp.REPO
    assert mp.VERTEX_UNREADABLE_TITLE in create
    assert mp.VERTEX_SNAPSHOT.read_text(encoding="utf-8") == before


def test_dry_run_writes_and_files_nothing(env, capsys):
    state, calls = env
    assert mp.check_vertex_retirements(dry_run=False)
    before = mp.VERTEX_SNAPSHOT.read_text(encoding="utf-8")
    state["page"] = _page(shorter=SHORTER_DATED)
    assert mp.check_vertex_retirements(dry_run=True)
    assert not _created(calls)
    assert mp.VERTEX_SNAPSHOT.read_text(encoding="utf-8") == before
    assert "would file in o/ops: Vertex retires gemini-3.6-flash on 2026-11-19" in (
        capsys.readouterr().out)
