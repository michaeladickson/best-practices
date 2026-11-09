"""The Gemini deprecations-page watch in digest/model_pricing.py (#32, #75).

The two outcomes that matter: a watched row gaining a shutdown date files an
issue, and a page that cannot be read is reported as unreadable rather than as
"nothing announced". No network: the page is a fixture in each shape the real
one has had, and every test runs against both.

- html: ai.google.dev until 2026-10-30. An h2 per family, a Model / Release
  date / Shutdown date / Recommended replacement header row, single-cell
  "Preview models" divider rows.
- markdoc: aistudio.google.com from 2026-11-06 (#75). The page renders
  client-side and carries its content as HTML-escaped Markdoc in a <pre>:
  `{% table %}` blocks, one `* cell` line per cell, `---` between rows,
  backticked model ids.
"""
import html
import json

import pytest

from digest import model_pricing as mp

NO_DATE = mp.NO_SHUTDOWN_DATE
HEADER = ("Model", "Release date", "Shutdown date", "Recommended replacement")


def _html_page(rows, header=HEADER):
    head = "".join(f"<th>{h}</th>" for h in header)
    body = "".join(
        "<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return (f"<html><body><h2>Gemini 2.5 Flash models</h2><table><tr>{head}</tr>"
            f"<tr><td colspan='4'>Preview models</td></tr>{body}</table></body></html>")


def _markdoc_page(rows, header=HEADER):
    def cell(c):
        return f"`{c}`" if c.startswith("gemini-") else c

    rows_md = ["\n".join(f"  * {cell(c)}" for c in r) for r in (header, *rows)]
    md = ("> ## AI Agent Context\n\n# Gemini deprecations\n\n"
          '## Gemini 2.5 Flash models  {% id="gemini-2.5-flash-models" %}\n\n'
          '{% callout type="caution" %}\n  `gemini-2.5-flash` is deprecated.\n'
          "{% /callout %}\n\n{% table %}\n"
          + "\n\n  ---\n\n".join(rows_md)
          + "\n{% /table %}\n")
    return ("<html><head><script>var app = {};</script></head><body><app-root></app-root>"
            f"<pre>{html.escape(md)}</pre></body></html>")


@pytest.fixture(params=[_html_page, _markdoc_page], ids=["html", "markdoc"])
def page_of(request):
    return request.param


BASE_ROWS = [
    ("gemini-2.5-flash", "June 17, 2025", NO_DATE, ""),
    ("gemini-2.5-pro", "June 17, 2025", NO_DATE, ""),
    ("gemini-2.5-flash-lite", "July 22, 2025", NO_DATE, ""),
    ("gemini-2.5-flash-preview-05-20", "May 20, 2025", "November 18, 2025", "gemini-3.6-flash"),
    ("gemini-3.8-flash", "September 2, 2026", NO_DATE, ""),
]
FLASH_DATED = [("gemini-2.5-flash", "June 17, 2025", "June 17, 2027", "gemini-3.5-flash-lite"),
               *BASE_ROWS[1:]]


@pytest.fixture(autouse=True)
def _small_page_ok(monkeypatch):
    monkeypatch.setattr(mp, "MIN_PAGE_ROWS", 3)


@pytest.fixture(autouse=True)
def _watch_the_fixture_family(monkeypatch):
    """The fixture rows are the 2.5 family, so these tests watch 2.5 whatever the
    code calls today. The live watch moves with the pinned model (#78), and
    tests/test_model_strings_pinned.py checks that it covers it."""
    monkeypatch.setattr(mp, "DEPRECATION_WATCH_PREFIXES", ("gemini-2.5-",))
    monkeypatch.setitem(mp.WATCHLIST, "Google (in use)",
                        ["google/gemini-2.5-flash", "google/gemini-2.5-pro"])


def _watched(page_of, rows):
    return mp.watched(mp.parse_deprecations(page_of(rows)))


def _snapshot(page_of, rows):
    return {"fetched_at": "2026-10-23 22:00 UTC", "models": _watched(page_of, rows)}


def test_parse_reads_shutdown_by_header_and_skips_dividers(page_of):
    rows = mp.parse_deprecations(page_of(BASE_ROWS))
    assert rows["gemini-2.5-flash"] == {
        "section": "Gemini 2.5 Flash models", "shutdown": NO_DATE, "replacement": ""}
    assert rows["gemini-2.5-flash-preview-05-20"]["replacement"] == "gemini-3.6-flash"
    assert "Preview models" not in rows
    assert set(mp.watched(rows)) == {m for m, *_ in BASE_ROWS if m.startswith("gemini-2.5-")}


def test_parse_follows_a_reordered_shutdown_column(page_of):
    header = ("Model", "Shutdown date", "Release date", "Recommended replacement")
    rows = [(m, s, r, rep) for m, r, s, rep in BASE_ROWS]
    assert mp.parse_deprecations(page_of(rows, header))["gemini-2.5-flash-preview-05-20"][
        "shutdown"] == "November 18, 2025"


def test_markdoc_cells_read_as_the_text_a_browser_shows():
    """Links, a wrapped cell, an empty cell written `* ` and a ### heading, as
    on the live page. The section stays the h2, as the HTML reader had it."""
    md = "\n".join([
        '## Gemini 2.5 Pro models  {% id="gemini-2.5-pro-models" %}', "",
        '### Deprecated models  {% id="gemini-2.5-pro-deprecated-models" %}', "",
        "{% table %}",
        *[f"  * {h}" for h in HEADER], "", "  ---", "",
        "  * `gemini-2.5-pro`", "  * June 17, 2025", "  * December 1, 2026",
        "  * [`gemini-3.8-flash`](/docs/models/gemini-3.8-flash) (requests to",
        '    `gemini-2.5-pro` "route" to it)', "", "  ---", "",
        "  * `gemini-2.5-flash`", "  * June 17, 2025", f"  * {NO_DATE}", "  * ", "",
        "  ---", "",
        "  * `gemini-2.5-flash-lite`", "  * July 22, 2025", f"  * **{NO_DATE}**", "  * ",
        "{% /table %}",
    ])
    rows = mp.parse_deprecations(f"<pre>{html.escape(md)}</pre>")
    assert rows["gemini-2.5-pro"] == {
        "section": "Gemini 2.5 Pro models", "shutdown": "December 1, 2026",
        "replacement": 'gemini-3.8-flash (requests to gemini-2.5-pro "route" to it)'}
    assert rows["gemini-2.5-flash"]["replacement"] == ""
    assert rows["gemini-2.5-flash-lite"]["shutdown"] == NO_DATE


UNREADABLE = [
    (lambda page_of: "<html><body>Something went wrong</body></html>", "no table"),
    (lambda page_of: "<html><body><app-root></app-root></body></html>", "no table"),
    (lambda page_of: page_of(BASE_ROWS, ("Model", "Release date", "Retirement", "Replacement")),
     "no table"),
    (lambda page_of: page_of(BASE_ROWS[:1]), "rows parsed"),
    (lambda page_of: page_of([r for r in BASE_ROWS if r[0] != "gemini-2.5-flash"]),
     "not on the page"),
]


@pytest.mark.parametrize("make, why", UNREADABLE, ids=[
    "error page", "app shell only", "renamed column", "too few rows", "in-use model absent"])
def test_unrecognisable_page_raises_instead_of_reading_as_quiet(page_of, make, why):
    with pytest.raises(mp.PageUnreadable, match=why):
        mp.parse_deprecations(make(page_of))


def test_in_use_model_gaining_a_date_is_reported(page_of):
    changes = mp.diff_deprecations(_snapshot(page_of, BASE_ROWS), _watched(page_of, FLASH_DATED))
    assert changes == ['**gemini-2.5-flash** shutdown date "No shutdown date announced" -> '
                       '"June 17, 2027" (replacement: gemini-3.5-flash-lite)']


def test_a_snapshot_from_the_html_page_diffs_cleanly_against_the_markdoc_page():
    """The switch itself must not read as a change: the first good read after
    #75 diffs a snapshot the HTML reader wrote against what the Markdoc reader
    returns."""
    old = _snapshot(_html_page, BASE_ROWS)
    assert mp.diff_deprecations(old, _watched(_markdoc_page, BASE_ROWS)) == []
    assert len(mp.diff_deprecations(old, _watched(_markdoc_page, FLASH_DATED))) == 1


def test_new_rows_report_only_when_dated_and_baseline_reports_nothing(page_of):
    new = _watched(page_of, [*BASE_ROWS,
                             ("gemini-2.5-flash-tts", "May 20, 2025", "November 17, 2026", ""),
                             ("gemini-2.5-flash-live", "May 20, 2025", NO_DATE, "")])
    assert mp.diff_deprecations(_snapshot(page_of, BASE_ROWS), new) == [
        '**gemini-2.5-flash-tts** added with shutdown date "November 17, 2026"']
    assert mp.diff_deprecations({}, new) == []


def test_undated_row_leaving_is_reported_dated_row_leaving_is_not(page_of):
    gone = {"gemini-2.5-flash-lite", "gemini-2.5-flash-preview-05-20"}
    new = _watched(page_of, [r for r in BASE_ROWS if r[0] not in gone])
    assert mp.diff_deprecations(_snapshot(page_of, BASE_ROWS), new) == [
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
def env(monkeypatch, tmp_path, page_of):
    """Snapshot in tmp, gh recorded instead of run, page served from a variable."""
    calls = []
    state = {"page": page_of(BASE_ROWS), "gh_rc": 0, "page_of": page_of}

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

    state["page"] = state["page_of"](FLASH_DATED)
    assert mp.check_deprecations(dry_run=False)
    created = [c for c in calls if c[:2] == ("issue", "create")]
    assert len(created) == 1 and mp.DEPRECATION_ISSUE_TITLE in created[0]
    snap = json.loads(mp.DEPRECATIONS_SNAPSHOT.read_text(encoding="utf-8"))
    assert snap["models"]["gemini-2.5-flash"]["shutdown"] == "June 17, 2027"


def test_unfiled_change_keeps_old_snapshot_so_it_refiles(env):
    state, _ = env
    assert mp.check_deprecations(dry_run=False)
    state["page"] = state["page_of"](FLASH_DATED)
    state["gh_rc"] = 1
    assert mp.check_deprecations(dry_run=False) is False
    snap = json.loads(mp.DEPRECATIONS_SNAPSHOT.read_text(encoding="utf-8"))
    assert snap["models"]["gemini-2.5-flash"]["shutdown"] == NO_DATE
