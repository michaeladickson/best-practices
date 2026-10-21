import pytest

from digest import article_text


@pytest.fixture(autouse=True)
def _no_article_fetches(monkeypatch):
    """No test reaches the network for an article page. _fetch_feeds now reads the
    article when a feed entry is thin, and the fixtures' entries are ("body"), so
    without this every feed test would make real HTTP calls. Tests of the fetch
    itself install their own fake urlopen over this one."""
    def _refuse(*a, **k):
        raise OSError("network disabled in tests")

    monkeypatch.setattr(article_text, "urlopen", _refuse)
