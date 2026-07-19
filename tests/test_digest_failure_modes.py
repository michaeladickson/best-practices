"""Failure-mode tests for the weekly digest.

This job runs unattended once a week, so a failure that exits 0 is invisible
until someone reads the log. Three such bugs have shipped:

  2026-07-03  wealth-mgmt analysis returned prose instead of JSON; main()
              did a bare `return`, so run_weekly_digest.sh (which counts a
              failed context via exit status) never reported it.
  2026-07-17  the Gemini call hung with no client-side timeout; Task
              Scheduler's ExecutionTimeLimit killed the whole run.
  (latent)    a total feed outage produced zero posts and exited 0, which is
              indistinguishable from a genuinely quiet week.

Every test here pins "this failure must be loud". No network, no Gemini
calls, no email, no writes to the real feed archive.
"""
import time

import pytest

from digest import ai_digest

CONTEXT = ["--context", "digest/config/context-command-center.yaml", "--days", "7"]
RECENT = time.gmtime(time.time() - 3600)
OLD = time.gmtime(time.time() - 400 * 86400)


class FakeEntry(dict):
    """feedparser entries support both attribute and dict access."""

    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError:
            raise AttributeError(k)


def _entry(when, n):
    return FakeEntry(title=f"post {n}", link=f"https://example.test/{n}",
                     summary="body", published_parsed=when)


class FakeParsed:
    """Mimics feedparser's real failure shape.

    feedparser.parse() does NOT raise on HTTP or DNS errors — it returns an
    object with `bozo` set and `entries` empty. Observed 2026-07-19:
        404 on live host  -> bozo=1,    status=404,  entries=0
        unresolvable host -> bozo=True, status=None, entries=0 (URLError)
        HTML not XML      -> bozo=1,    status=200,  entries=0
    """

    def __init__(self, entries=(), bozo=0, status=200, exc=None):
        self.entries = list(entries)
        self.bozo = bozo
        self.status = status
        self.bozo_exception = exc


def dead_404():
    return FakeParsed(bozo=1, status=404, exc=Exception("not found"))


def dead_dns():
    return FakeParsed(bozo=True, status=None, exc=OSError("dns"))


def healthy(when=RECENT, n=1):
    return FakeParsed(entries=[_entry(when, n)])


@pytest.fixture
def run_digest(monkeypatch):
    """Invoke main() against a scripted set of feed results."""
    from click.testing import CliRunner

    def _run(feed_results):
        feeds = [{"name": f"feed{i}", "url": f"https://example.test/{i}/rss",
                  "category": "test"} for i in range(len(feed_results))]
        calls = iter(feed_results)
        monkeypatch.setattr(ai_digest, "_load_feeds", lambda *a, **k: feeds)
        monkeypatch.setattr(ai_digest.feedparser, "parse", lambda url: next(calls))
        # Never touch the real archive or knowledge dir.
        monkeypatch.setattr(ai_digest, "_load_archive", lambda: {})
        monkeypatch.setattr(ai_digest, "_save_archive", lambda archive: None)
        monkeypatch.setattr(ai_digest, "_save_digest_knowledge", lambda *a, **k: None)
        monkeypatch.setattr(ai_digest, "_analyze_posts",
                            lambda *a, **k: {"top_posts": [],
                                             "project_recommendations": []})
        return CliRunner().invoke(ai_digest.main, CONTEXT + ["--dry-run"])

    return _run


# --- feed-health classification -----------------------------------------

@pytest.mark.parametrize("parsed,expected", [
    (dead_404(), "http_404"),
    (dead_dns(), "parse_error:OSError"),
    (healthy(), None),
    # bozo fires on benign encoding quirks; entries present means it worked.
    (FakeParsed(entries=[_entry(RECENT, 1)], bozo=1, exc=Exception("enc")), None),
    # 200, well-formed, genuinely no items — unusual but not a failure.
    (FakeParsed(entries=[], bozo=0, status=200), None),
])
def test_feed_failure_reason(parsed, expected):
    assert ai_digest._feed_failure_reason(parsed) == expected


# --- "no fetch" must be distinguishable from "no news" ------------------

def test_total_feed_outage_exits_nonzero(run_digest):
    res = run_digest([dead_404(), dead_dns(), dead_404(), dead_dns()])
    assert res.exit_code == 1


def test_majority_feed_failure_exits_nonzero(run_digest):
    """Exits 1 even though one feed returned usable posts."""
    res = run_digest([dead_404(), dead_404(), dead_dns(), healthy()])
    assert res.exit_code == 1


def test_minority_feed_failure_proceeds(run_digest):
    res = run_digest([dead_404(), healthy(n=1), healthy(n=2), healthy(n=3)])
    assert res.exit_code == 0


def test_quiet_week_still_exits_zero(run_digest):
    """All feeds healthy, nothing inside the window — not a failure."""
    res = run_digest([healthy(OLD, 1), healthy(OLD, 2), healthy(OLD, 3)])
    assert res.exit_code == 0
    assert "No new posts found." in res.output


# --- analysis failures must be loud -------------------------------------

def test_analysis_failure_exits_nonzero(monkeypatch):
    """A bare `return` here exited 0 and hid the 2026-07-03 wealth-mgmt break."""
    from click.testing import CliRunner

    monkeypatch.setattr(ai_digest, "_fetch_feeds", lambda feeds, **k: (
        [{"source": "s", "category": "c", "title": "t", "link": "u",
          "published": "2026-07-19", "content_preview": "x"}],
        {"total": len(feeds), "ok": len(feeds), "failed": []}))
    monkeypatch.setattr(ai_digest, "_analyze_posts", lambda *a, **k: None)

    res = CliRunner().invoke(ai_digest.main, CONTEXT)
    assert res.exit_code == 1


def test_analysis_transport_error_returns_none(monkeypatch):
    """A timeout must not raise a traceback through click."""

    class Boom:
        class models:
            @staticmethod
            def generate_content(**kw):
                raise TimeoutError("simulated hang")

    monkeypatch.setattr(ai_digest, "_get_gemini_client", lambda: Boom())
    posts = [{"source": "s", "category": "c", "title": "t", "link": "u",
              "published": "2026-07-19", "content_preview": "x"}]
    assert ai_digest._analyze_posts(posts, "ctx", "proj") is None


# --- the hang guard -----------------------------------------------------

def test_gemini_client_has_bounded_timeout(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "dummy-key-for-construction-only")
    client = ai_digest._get_gemini_client()
    assert client._api_client._http_options.timeout == ai_digest.GEMINI_TIMEOUT_MS
    assert 0 < ai_digest.GEMINI_TIMEOUT_MS <= 15 * 60 * 1000


# --- callers of the posts-only wrapper must keep working ----------------

def test_fetch_recent_posts_wrapper_returns_list(monkeypatch):
    """practice_updater returns this directly; it must stay list[dict]."""
    monkeypatch.setattr(ai_digest, "_load_archive", lambda: {})
    monkeypatch.setattr(ai_digest, "_save_archive", lambda a: None)
    monkeypatch.setattr(ai_digest.feedparser, "parse",
                        lambda url: healthy(RECENT, 9))
    out = ai_digest._fetch_recent_posts(
        [{"name": "f0", "url": "u", "category": "c"}], days=7)
    assert isinstance(out, list)
    assert len(out) == 1 and isinstance(out[0], dict)
