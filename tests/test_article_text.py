"""A post whose feed entry carries no text is judged by the article itself.

"How the Claude Code team does code review" reached the 2026-10-16 practice update
as a Hacker News stub (links and "Points: 181"), so neither the digest nor the
practice extraction saw a word of it. Google Cloud Blog and Hugging Face Blog send
empty entries every time. No network: urlopen is faked.
"""
import time
from urllib.error import HTTPError

from digest import ai_digest, article_text as at

PARA = "Agents write most of the code now, so review moved earlier in the loop. " * 5
HN_STUB = ('<p>Article URL: <a href="https://claude.dev/blog/x/">https://claude.dev/blog/x/</a></p>'
           '<p>Comments URL: <a href="https://news.ycombinator.com/item?id=1">'
           'https://news.ycombinator.com/item?id=1</a></p><p>Points: 181</p><p># Comments: 174</p>')
PAGE = f"""<html><head><script>var x = "not text";</script><style>p {{}}</style></head>
<body><nav><ul><li>Home</li><li>Blog</li></ul></nav>
<p>Sidebar paragraph outside the article that should not be preferred.</p>
<article><h1>How the Claude Code team does code review</h1>
<ul><li>twitter</li><li>mailto</li></ul>
<p>{PARA}</p><li>Cap review-and-fix rounds at three before rethinking the approach.</li></article>
<footer><p>Copyright footer text</p></footer></body></html>"""


class _Headers(dict):
    def get_content_charset(self):
        return "utf-8"


class _Resp:
    def __init__(self, body, ctype="text/html; charset=utf-8"):
        self.body, self.headers = body.encode("utf-8"), _Headers({"Content-Type": ctype})

    def read(self, n=-1):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _fake_urlopen(monkeypatch, body=PAGE, ctype="text/html; charset=utf-8", error=None):
    calls = []

    def fake(req, timeout=None):
        calls.append(req.full_url)
        if error:
            raise error
        return _Resp(body, ctype)

    monkeypatch.setattr(at, "urlopen", fake)
    return calls


# --- thin detection -------------------------------------------------------

def test_hn_stub_and_empty_and_title_only_are_thin():
    assert at.is_thin(HN_STUB)
    assert at.is_thin("")
    assert at.is_thin("Developing Enterprise Frontier Safeguards with our customers")


def test_a_real_paragraph_is_not_thin():
    assert not at.is_thin(f"<p>{PARA}</p>")


def test_hn_article_url_is_read_from_the_stub():
    assert at.hn_article_url(HN_STUB) == "https://claude.dev/blog/x/"
    assert at.hn_article_url("<p>plain</p>") is None


# --- extraction -----------------------------------------------------------

def test_extract_prefers_the_article_and_drops_chrome():
    text = at.extract_text(PAGE)
    assert text.startswith("How the Claude Code team does code review")
    assert "Cap review-and-fix rounds" in text
    for chrome in ("not text", "Home", "Sidebar paragraph", "Copyright", "twitter", "mailto"):
        assert chrome not in text


def test_extract_falls_back_to_the_page_without_an_article_tag():
    text = at.extract_text(f"<html><body><div><p>{PARA}</p></div></body></html>")
    assert "review moved earlier" in text


# --- fetch ----------------------------------------------------------------

def test_fetch_returns_capped_article_text(monkeypatch):
    _fake_urlopen(monkeypatch, body=PAGE.replace(PARA, PARA * 20))
    text = at.fetch_article_text("https://claude.dev/blog/x/")
    assert text.startswith("How the Claude Code team")
    assert len(text) == at.PREVIEW_MAX_CHARS + 3 and text.endswith("...")


def test_fetch_failure_returns_none_and_never_raises(monkeypatch):
    _fake_urlopen(monkeypatch, error=HTTPError("https://openai.com/x", 403, "Forbidden", {}, None))
    assert at.fetch_article_text("https://openai.com/x") is None


def test_non_html_and_too_short_pages_return_none(monkeypatch):
    _fake_urlopen(monkeypatch, ctype="application/pdf")
    assert at.fetch_article_text("https://example.test/a.pdf") is None
    _fake_urlopen(monkeypatch, body="<html><body><p>Too short.</p></body></html>")
    assert at.fetch_article_text("https://example.test/short") is None


def test_non_http_scheme_is_never_fetched(monkeypatch):
    calls = _fake_urlopen(monkeypatch)
    assert at.fetch_article_text("file:///etc/passwd") is None
    assert calls == []


# --- _fill_thin_preview ---------------------------------------------------

def _post(content=HN_STUB, link="https://claude.dev/blog/x/"):
    return {"source": "Hacker News", "title": "t", "link": link,
            "published": "2026-10-15", "content_preview": content}


def test_thin_post_gets_article_text_and_archive_is_updated(monkeypatch):
    calls = _fake_urlopen(monkeypatch)
    post, archive, budget = _post(), {}, [5]
    assert ai_digest._fill_thin_preview(post, archive, budget)
    assert "review moved earlier" in post["content_preview"]
    assert archive[post["link"]]["content_preview"] == post["content_preview"]
    assert archive[post["link"]]["content_fetched"] is True
    assert calls == ["https://claude.dev/blog/x/"] and budget == [4]


def test_hn_stub_fetches_the_article_url_not_the_item(monkeypatch):
    calls = _fake_urlopen(monkeypatch)
    ai_digest._fill_thin_preview(_post(link="https://news.ycombinator.com/item?id=1"), {}, [5])
    assert calls == ["https://claude.dev/blog/x/"]


def test_existing_thin_archive_entry_is_filled_in_place(monkeypatch):
    _fake_urlopen(monkeypatch)
    post = _post()
    archive = {post["link"]: dict(post, published="2026-10-14")}
    assert ai_digest._fill_thin_preview(post, archive, [5])
    assert archive[post["link"]]["published"] == "2026-10-14"
    assert not at.is_thin(archive[post["link"]]["content_preview"])


def test_text_already_in_the_archive_is_reused_without_a_fetch(monkeypatch):
    calls = _fake_urlopen(monkeypatch)
    post = _post()
    archive = {post["link"]: dict(post, content_preview=PARA)}
    assert not ai_digest._fill_thin_preview(post, archive, [5])
    assert post["content_preview"] == PARA and calls == []


def test_a_failed_fetch_is_flagged_and_not_retried(monkeypatch):
    calls = _fake_urlopen(monkeypatch, error=OSError("timed out"))
    post, archive = _post(), {}
    assert ai_digest._fill_thin_preview(post, archive, [5])
    assert archive[post["link"]]["article_fetch_failed"] is True
    assert post["content_preview"] == HN_STUB
    assert not ai_digest._fill_thin_preview(_post(), archive, [5])
    assert len(calls) == 1


def test_rich_preview_and_spent_budget_never_fetch(monkeypatch):
    calls = _fake_urlopen(monkeypatch)
    assert not ai_digest._fill_thin_preview(_post(content=f"<p>{PARA}</p>"), {}, [5])
    assert not ai_digest._fill_thin_preview(_post(), {}, [0])
    assert calls == []


# --- through _fetch_feeds -------------------------------------------------

class _Entry(dict):
    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError:
            raise AttributeError(k)


class _Parsed:
    def __init__(self, entries):
        self.entries, self.bozo, self.status, self.bozo_exception = entries, 0, 200, None


def test_fetch_feeds_reads_thin_in_window_posts_only(monkeypatch):
    recent, old = time.gmtime(time.time() - 3600), time.gmtime(time.time() - 30 * 86400)
    entries = [_Entry(title="new", link="https://example.test/new", summary="", published_parsed=recent),
               _Entry(title="old", link="https://example.test/old", summary="", published_parsed=old)]
    calls = _fake_urlopen(monkeypatch)
    saved = {}
    monkeypatch.setattr(ai_digest, "_load_archive", lambda: {})
    monkeypatch.setattr(ai_digest, "_save_archive", lambda a: saved.update(a))
    monkeypatch.setattr(ai_digest.feedparser, "parse", lambda url: _Parsed(entries))
    posts, _ = ai_digest._fetch_feeds([{"name": "Google Cloud Blog", "url": "u"}], days=7)
    assert calls == ["https://example.test/new"]
    assert "review moved earlier" in posts[0]["content_preview"]
    assert "review moved earlier" in saved["https://example.test/new"]["content_preview"]
    assert saved["https://example.test/old"]["content_preview"] == ""


def test_fetch_feeds_saves_the_archive_when_only_enrichment_changed_it(monkeypatch):
    recent = time.gmtime(time.time() - 3600)
    link = "https://example.test/new"
    entries = [_Entry(title="new", link=link, summary="", published_parsed=recent)]
    _fake_urlopen(monkeypatch)
    saved = []
    archive = {link: {"source": "Google Cloud Blog", "title": "new", "link": link,
                      "published": "2026-10-20", "content_preview": ""}}
    monkeypatch.setattr(ai_digest, "_load_archive", lambda: archive)
    monkeypatch.setattr(ai_digest, "_save_archive", lambda a: saved.append(True))
    monkeypatch.setattr(ai_digest.feedparser, "parse", lambda url: _Parsed(entries))
    ai_digest._fetch_feeds([{"name": "Google Cloud Blog", "url": "u"}], days=7)
    assert saved == [True]
    assert not at.is_thin(archive[link]["content_preview"])
