"""Which cited domains become feed-candidate issues.

The 2026-10-26 triage closed all 12 open proposals: 6 had no feed, and most of the
rest were product apps, an event host, a press-release wire or OpenAI subdomains the
OpenAI Blog feed already covers. No network, no gh.
"""
from digest import citation_discovery as cd


def _entry(articles=5):
    return {"articles": articles, "sources": ["A", "B"], "first_seen": "2026-10-01",
            "last_seen": "2026-10-20", "proposed": None}


def test_app_event_wire_and_openai_domains_are_excluded():
    for d in ("luma.com", "learn.chatgpt.com", "chatgpt.com", "developers.openai.com",
              "prnewswire.com"):
        assert cd._excluded(d), d
    assert not cd._excluded("blog.cloudflare.com")


def test_a_domain_without_a_feed_is_recorded_not_filed(monkeypatch, capsys):
    monkeypatch.setattr(cd, "resolve_feed",
                        lambda d: "https://blog.example.test/rss" if d == "blog.example.test" else None)
    ledger = {"domains": {"nofeed.example.test": _entry(6),
                          "blog.example.test": _entry(5)}}
    proposed = cd.propose(ledger, dry_run=True)
    assert proposed == ["blog.example.test"]
    nofeed = ledger["domains"]["nofeed.example.test"]
    assert nofeed["no_feed"] is True and nofeed["proposed"]
    out = capsys.readouterr().out
    assert "no feed, not filed: nofeed.example.test" in out
    assert "would propose: Feed candidate: nofeed" not in out
