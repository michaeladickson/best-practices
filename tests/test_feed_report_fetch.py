"""The feed report shows what article fetching did, per feed.

Friday 2026-10-23 is the first run that fetches the article for a thin feed entry
(digest/article_text.py). Without this section nothing shows whether it worked,
or when a site that used to answer starts refusing. No network, no real archive.
"""
from datetime import datetime, timedelta, timezone

from digest import ai_digest, feed_report as fr

TODAY = datetime(2026, 10, 24, 12, tzinfo=timezone.utc)
RECENT = (TODAY - timedelta(days=2)).strftime("%Y-%m-%d")
OLD = (TODAY - timedelta(days=30)).strftime("%Y-%m-%d")
PARA = "A real paragraph of article text that is long enough to count as content. " * 4


def _post(source, published=RECENT, preview="", **flags):
    return {"source": source, "published": published, "content_preview": preview, **flags}


def _rows(lines):
    return {ln.split("|")[1].strip(): [c.strip() for c in ln.split("|")[2:5]]
            for ln in lines if ln.startswith("| ") and not ln.startswith("| Feed")}


def test_counts_filled_failed_and_still_thin_per_feed():
    archive = {
        "a": _post("Google Cloud Blog", preview=PARA, content_fetched=True),
        "b": _post("Google Cloud Blog", preview=PARA, content_fetched=True),
        "c": _post("OpenAI Blog", preview="One teaser sentence.", article_fetch_failed=True),
        "d": _post("Hugging Face Blog", preview=""),
    }
    rows = _rows(fr._fetch_section(archive, TODAY))
    assert rows["Google Cloud Blog"] == ["2", "0", "0"]
    assert rows["OpenAI Blog"] == ["0", "1", "0"]
    assert rows["Hugging Face Blog"] == ["0", "0", "1 ⚠️"]
    assert rows["**total**"] == ["2", "1", "1"]


def test_posts_with_real_text_and_old_posts_are_left_out():
    archive = {
        "rich": _post("Simon Willison", preview=PARA),
        "old_thin": _post("Hugging Face Blog", published=OLD, preview=""),
        "old_fetched": _post("Google Cloud Blog", published=OLD, preview=PARA, content_fetched=True),
    }
    lines = fr._fetch_section(archive, TODAY)
    assert _rows(lines) == {}
    assert "No post in the last 7 days arrived without text." in lines


def test_a_feed_with_unattempted_thin_posts_sorts_first():
    archive = {
        "a": _post("Google Cloud Blog", preview=PARA, content_fetched=True),
        "b": _post("Hugging Face Blog", preview=""),
    }
    feeds = [r for r in _rows(fr._fetch_section(archive, TODAY)) if r != "**total**"]
    assert feeds == ["Hugging Face Blog", "Google Cloud Blog"]


def test_build_report_includes_the_fetch_section(monkeypatch, tmp_path):
    archive = {"https://example.test/x": _post("Google Cloud Blog", published=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                                                preview=PARA, content_fetched=True)}
    monkeypatch.setattr(ai_digest, "_load_archive", lambda: archive)
    monkeypatch.setattr(ai_digest, "_load_feeds", lambda *a, **k: [
        {"name": "Google Cloud Blog", "url": "https://cloud.google.com/blog/rss"}])
    monkeypatch.setattr(fr, "INCORPORATED", tmp_path / "none.json")
    monkeypatch.setattr(fr, "ROOT", tmp_path)
    report = fr.build_report(90)
    assert "## Article fetch (7d)" in report
    assert "| Google Cloud Blog | 1 | 0 | 0 |" in report
