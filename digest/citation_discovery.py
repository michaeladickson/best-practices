"""
digest/citation_discovery.py
Feed-candidate discovery from the citation graph of articles we already trust.

Each weekly run, extract outbound links from newly archived posts, aggregate
by domain into data/feed_candidates.json, and when a domain crosses the
threshold — cited in >= MIN_ARTICLES distinct articles by >= MIN_SOURCES
distinct existing feeds — attempt feed resolution and open a GitHub issue in
this repo proposing the addition. Human approves by editing feeds.yaml;
nothing is ever auto-added (feed additions are cheap to approve, expensive to
silently get wrong — see the dropped-feed graveyard in feeds.yaml).

Resolution order: HTML autodiscovery tag on the homepage, then platform
patterns (YouTube channel feeds, GitHub .atom, Substack-convention /feed),
then conventional paths. A domain with no feed still gets proposed once as a
"no feed — check manually, route finds through the digest inbox" pointer.

Limitation, by design: content_preview is truncated at 3KB, so links deep in
long posts are missed; and discovery only expands one hop from the current
pool. Both are acceptable — repeated citation is the signal, and any one
mention landing inside 3KB across N articles is likely for a source that
matters.

Run: python -m digest.citation_discovery [--dry-run]
"""
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import click
import feedparser
import structlog

log = structlog.get_logger()

ROOT = Path(__file__).parent.parent
LEDGER_PATH = ROOT / "data" / "feed_candidates.json"

MIN_ARTICLES = 3      # distinct citing articles
MIN_SOURCES = 2       # distinct citing feeds
MAX_PROPOSALS_PER_RUN = 3
FIRST_SCAN_DAYS = 14  # bound the very first sweep

REPO = "michaeladickson/best-practices"

# Domains that are infrastructure, social, or self-referential — never feed
# candidates. Substrings matched against the registrable domain.
EXCLUDE = {
    "twitter.com", "x.com", "linkedin.com", "facebook.com", "reddit.com",
    "news.ycombinator.com", "google.com", "bit.ly", "t.co", "buttondown.email",
    "substack.com",  # bare substack.com (CDN/app links); real newsletters are *.substack.com
    "substackcdn.com", "amazonaws.com", "cloudfront.net", "wikipedia.org",
    "amazon.com", "apple.com", "archive.org", "arxiv.org",  # arxiv: subscribe by category deliberately, not by citation
    "docs.anthropic.com", "platform.openai.com", "en.wikipedia.org",
    "youtube.com", "youtu.be",  # video links are one-off inbox material until a channel recurs by name
    # Platform hubs surfaced by the first real scan (2026-08-23): a citation of
    # the platform is not a citation of a followable source.
    "github.com", "open.spotify.com", "podcasts.apple.com", "medium.com",
    "claude.com", "anthropic.com",  # already covered by the two Anthropic feeds
    "discord.gg", "discord.com", "slack.com", "meetup.com", "eventbrite.com",
    "lu.ma", "twitch.tv", "notion.site", "docs.google.com", "forms.gle",
}

FEED_PROBES = ["/feed", "/rss", "/feed.xml", "/rss.xml", "/atom.xml", "/index.xml"]

HREF_RE = re.compile(r'href=["\'](https?://[^"\']+)["\']', re.IGNORECASE)
AUTODISCOVERY_RE = re.compile(
    r'<link[^>]+type=["\']application/(?:rss|atom)\+xml["\'][^>]*href=["\']([^"\']+)["\']'
    r'|<link[^>]+href=["\']([^"\']+)["\'][^>]*type=["\']application/(?:rss|atom)\+xml["\']',
    re.IGNORECASE)


def _domain(url: str) -> str:
    return urlparse(url).netloc.replace("www.", "").lower()


def _excluded(domain: str) -> bool:
    return any(domain == e or domain.endswith("." + e) for e in EXCLUDE
               # *.substack.com newsletters ARE candidates; only bare substack.com is excluded
               if not (e == "substack.com" and domain != "substack.com"))


def _load_ledger() -> dict:
    if LEDGER_PATH.exists():
        with open(LEDGER_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {"last_scan": None, "domains": {}}


def _save_ledger(ledger: dict) -> None:
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LEDGER_PATH, "w", encoding="utf-8") as f:
        json.dump(ledger, f, indent=2, ensure_ascii=False)


def _feed_domains() -> set[str]:
    from digest.ai_digest import _load_feeds
    return {_domain(f["url"]) for f in _load_feeds()}


def _try_feed(url: str) -> bool:
    try:
        parsed = feedparser.parse(url)
        return bool(parsed.entries) and not parsed.get("bozo", 0)
    except Exception:
        return False


def resolve_feed(domain: str) -> str | None:
    """Best-effort feed URL for a domain, or None."""
    import urllib.request
    homepage = f"https://{domain}/"
    try:
        req = urllib.request.Request(homepage, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read(65536).decode("utf-8", errors="replace")
        m = AUTODISCOVERY_RE.search(html)
        if m:
            href = m.group(1) or m.group(2)
            if href.startswith("/"):
                href = f"https://{domain}{href}"
            if _try_feed(href):
                return href
    except Exception:
        pass
    for probe in FEED_PROBES:
        candidate = f"https://{domain}{probe}"
        if _try_feed(candidate):
            return candidate
    return None


def scan(ledger: dict) -> int:
    """Fold newly archived posts' citations into the ledger. Returns new-post count."""
    from digest.ai_digest import _load_archive
    archive = _load_archive()
    since = ledger["last_scan"] or (
        datetime.now(timezone.utc) - timedelta(days=FIRST_SCAN_DAYS)).strftime("%Y-%m-%d")
    own = _feed_domains()
    scanned = 0
    for url, post in archive.items():
        pub = post.get("published", "")
        if pub < since:
            continue
        scanned += 1
        cited_here = set()
        for link in HREF_RE.findall(post.get("content_preview", "")):
            d = _domain(link)
            if not d or d in own or _excluded(d) or d == _domain(url):
                continue
            cited_here.add(d)
        for d in cited_here:  # count each article once per domain
            entry = ledger["domains"].setdefault(
                d, {"articles": 0, "sources": [], "first_seen": pub,
                    "last_seen": pub, "proposed": None})
            entry["articles"] += 1
            entry["last_seen"] = max(entry["last_seen"], pub)
            if post.get("source") and post["source"] not in entry["sources"]:
                entry["sources"].append(post["source"])
    ledger["last_scan"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return scanned


def propose(ledger: dict, dry_run: bool) -> list[str]:
    import subprocess
    proposed = []
    ready = sorted(
        ((d, e) for d, e in ledger["domains"].items()
         if e["articles"] >= MIN_ARTICLES and len(e["sources"]) >= MIN_SOURCES
         and not e["proposed"]),
        key=lambda kv: -kv[1]["articles"])
    for domain, entry in ready[:MAX_PROPOSALS_PER_RUN]:
        feed_url = resolve_feed(domain)
        if feed_url:
            action = (f"Feed found: `{feed_url}`\n\nTo subscribe, add to "
                      f"`digest/config/feeds.yaml` (pick a category).")
        else:
            action = ("No feed found (autodiscovery + conventional paths). "
                      "Check the site manually; route one-off finds through the "
                      "digest inbox rather than a scraper.")
        title = f"Feed candidate: {domain} (cited in {entry['articles']} articles)"
        body = (f"`{domain}` crossed the citation threshold.\n\n"
                f"- Cited in **{entry['articles']}** distinct articles "
                f"by **{len(entry['sources'])}** feeds: {', '.join(entry['sources'][:6])}\n"
                f"- First seen {entry['first_seen']}, last seen {entry['last_seen']}\n\n"
                f"{action}\n\nProposed by `digest/citation_discovery.py`. Approving "
                f"means editing feeds.yaml by hand — nothing is auto-added. If not "
                f"worth adding, just close; it will not be re-proposed.")
        if dry_run:
            print(f"[dry-run] would propose: {title}\n  {action.splitlines()[0]}")
        else:
            result = subprocess.run(
                ["gh", "issue", "create", "--repo", REPO, "--title", title,
                 "--body", body, "--label", "feed-candidate"],
                capture_output=True, text=True, encoding="utf-8", errors="replace")
            if result.returncode != 0:
                # Label may not exist yet; retry without it rather than losing the proposal.
                result = subprocess.run(
                    ["gh", "issue", "create", "--repo", REPO, "--title", title,
                     "--body", body],
                    capture_output=True, text=True, encoding="utf-8", errors="replace")
            if result.returncode != 0:
                log.warning("candidate_issue_failed", domain=domain,
                            stderr=result.stderr[:200])
                continue
            log.info("candidate_proposed", domain=domain, url=result.stdout.strip())
        entry["proposed"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        proposed.append(domain)
    return proposed


@click.command()
@click.option("--dry-run", is_flag=True, help="Scan and report; file no issues, write no ledger")
def main(dry_run: bool):
    ledger = _load_ledger()
    scanned = scan(ledger)
    over = [(d, e) for d, e in ledger["domains"].items()
            if e["articles"] >= MIN_ARTICLES and len(e["sources"]) >= MIN_SOURCES
            and not e["proposed"]]
    print(f"Scanned {scanned} new posts; {len(ledger['domains'])} cited domains "
          f"tracked; {len(over)} over threshold.")
    proposed = propose(ledger, dry_run)
    if not dry_run:
        _save_ledger(ledger)
    if proposed:
        print(f"Proposed: {', '.join(proposed)}")


if __name__ == "__main__":
    main()
