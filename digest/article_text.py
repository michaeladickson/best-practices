"""
digest/article_text.py

Fetch an article's own text when its feed entry carries none.

Both the digest scoring and the practice-doc extraction judge a post by its
`content_preview`, which is whatever the feed put in the entry. For 16% of posts
archived 2026-09-01..10-21 that is under 40 characters: Google Cloud Blog (110 posts)
and Hugging Face Blog (37) send no body at all, Anthropic News repeats the title, and
the Hacker News feed sends only the article link, the comments link and the points.
"How the Claude Code team does code review" reached the 10/16 practice update as that
HN stub, so the extraction judged a 14-minute article from "Points: 181".

Standard library only. The weekly run uses WSL's system python3, and a missing
third-party parser there would fail the whole digest instead of one fetch.
"""
import re
from html.parser import HTMLParser
from typing import Optional
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import structlog

log = structlog.get_logger()

# Below this much real text a preview is a title or one teaser sentence. Measured on
# the archive since 2026-09-01: under 100 chars is a title or nothing (183 posts),
# 100-199 is one teaser sentence (246, mostly OpenAI Blog, CFO Dive, Accounting
# Today), and 200+ is paragraphs (Simon Willison's short posts start there).
THIN_PREVIEW_CHARS = 200
PREVIEW_MAX_CHARS = 3000
FETCH_TIMEOUT_S = 10
MAX_FETCH_BYTES = 2_000_000
USER_AGENT = "Mozilla/5.0 (compatible; best-practices-digest/1.0; +https://github.com/michaeladickson/best-practices)"

# Boilerplate the HN feed (hnrss) wraps around every item; not article text.
_HN_STUB_RE = re.compile(r"Article URL:|Comments URL:|Points:\s*\d+|#\s*Comments:\s*\d+")
_TAG_RE = re.compile(r"<[^>]+>")
_URL_RE = re.compile(r"https?://\S+")


def preview_text(content: str) -> str:
    """The readable text in a feed preview: tags, bare URLs and HN boilerplate removed."""
    s = _TAG_RE.sub(" ", content or "")
    s = _URL_RE.sub(" ", s)
    s = _HN_STUB_RE.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


def is_thin(content: str) -> bool:
    return len(preview_text(content)) < THIN_PREVIEW_CHARS


class _TextExtractor(HTMLParser):
    """Collects block-level text, preferring <article>, then <main>, then the page."""

    _SKIP = {"script", "style", "noscript", "nav", "header", "footer", "aside",
             "form", "svg", "button", "template", "iframe"}
    _BLOCKS = {"p", "h1", "h2", "h3", "h4", "li", "blockquote", "pre", "td"}
    # Short list items and cells are share links and author boxes ("About Daniel",
    # "twitter", "mailto" opened every Accounting Today page), not article text.
    _CHROME_BLOCKS = {"li", "td"}
    _CHROME_MAX_CHARS = 20

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.block = 0
        self.block_tag = ""
        self.scope = {"article": 0, "main": 0}
        self.out = {"article": [], "main": [], "page": []}
        self._buf: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self.skip += 1
        elif tag in self.scope:
            self.scope[tag] += 1
        elif tag in self._BLOCKS:
            if self.block == 0:
                self.block_tag = tag
            self.block += 1

    def handle_endtag(self, tag):
        if tag in self._SKIP:
            self.skip = max(0, self.skip - 1)
        elif tag in self.scope:
            self.scope[tag] = max(0, self.scope[tag] - 1)
        elif tag in self._BLOCKS and self.block:
            self.block -= 1
            if self.block == 0:
                self._flush()

    def handle_data(self, data):
        if self.block and not self.skip:
            self._buf.append(data)

    def _flush(self):
        text = re.sub(r"\s+", " ", "".join(self._buf)).strip()
        self._buf = []
        if not text:
            return
        if self.block_tag in self._CHROME_BLOCKS and len(text) < self._CHROME_MAX_CHARS:
            return
        self.out["page"].append(text)
        for name, depth in self.scope.items():
            if depth:
                self.out[name].append(text)

    def text(self) -> str:
        self._flush()
        for name in ("article", "main", "page"):
            joined = "\n".join(self.out[name])
            if len(joined) >= THIN_PREVIEW_CHARS:
                return joined
        return "\n".join(self.out["page"])


def extract_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    return parser.text()


def hn_article_url(content: str) -> Optional[str]:
    """The 'Article URL' an HN feed item points at, if the preview is an HN stub."""
    m = re.search(r'Article URL:\s*<a href="([^"]+)"', content or "")
    return m.group(1) if m else None


def fetch_article_text(url: str) -> Optional[str]:
    """Readable text of the page at `url`, capped at PREVIEW_MAX_CHARS, or None.

    Never raises: a fetch that fails leaves the feed's own preview in place."""
    if urlparse(url).scheme not in ("http", "https"):
        return None
    try:
        req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
        with urlopen(req, timeout=FETCH_TIMEOUT_S) as resp:
            ctype = resp.headers.get("Content-Type", "")
            if "html" not in ctype:
                log.info("article_fetch_skipped", url=url, content_type=ctype)
                return None
            raw = resp.read(MAX_FETCH_BYTES)
            charset = resp.headers.get_content_charset() or "utf-8"
        text = extract_text(raw.decode(charset, errors="replace"))
    except Exception as e:  # network, HTTP 4xx/5xx, decode: all non-fatal
        log.warning("article_fetch_failed", url=url, error=f"{type(e).__name__}: {e}"[:200])
        return None
    if len(text) < THIN_PREVIEW_CHARS:
        log.info("article_fetch_thin", url=url, chars=len(text))
        return None
    if len(text) > PREVIEW_MAX_CHARS:
        text = text[:PREVIEW_MAX_CHARS] + "..."
    return text
