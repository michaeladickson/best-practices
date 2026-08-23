"""
digest/feed_report.py
Per-feed yield and freshness report, so pruning decisions are a routine
glance instead of a hand analysis.

For every feed in feeds.yaml:
  - archived posts (all-time and trailing window)
  - practice-doc incorporations (join incorporated.json URLs to feeds via the
    archive's source field, falling back to netloc match)
  - newest archived post age in days (the check that would have caught The
    Diff's 3.7-years-frozen feed, and Chip Huyen's — "resolves and returns
    entries" is not "alive")

Writes data/feed_report.md and prints it. Relevance scores are deliberately
NOT reported — everything scores 9-10, they carry no signal (2026-08-23
analysis). Incorporations and freshness are the honest yield metrics.

Run: python -m digest.feed_report [--days 90]
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import click
import yaml

ROOT = Path(__file__).parent.parent
REPORT_PATH = ROOT / "data" / "feed_report.md"
INCORPORATED = ROOT / "data" / "practice_updates" / "incorporated.json"


def _netloc(url: str) -> str:
    return urlparse(url).netloc.replace("www.", "")


def build_report(days: int = 90) -> str:
    from digest.ai_digest import _load_archive, _load_feeds

    feeds = _load_feeds()
    archive = _load_archive()
    today = datetime.now(timezone.utc)
    cutoff = (today - timedelta(days=days)).strftime("%Y-%m-%d")

    incorporated_urls: set[str] = set()
    if INCORPORATED.exists():
        with open(INCORPORATED, encoding="utf-8") as f:
            ledger = json.load(f)
        incorporated_urls = {u for urls in ledger.values() for u in urls}

    # url -> source name via archive (exact); netloc fallback for older entries
    stats = {f["name"]: {"all": 0, "window": 0, "inc_all": 0, "inc_window": 0,
                         "newest": None, "netloc": _netloc(f["url"])}
             for f in feeds}
    netloc_to_name = {s["netloc"]: name for name, s in stats.items()}

    for url, post in archive.items():
        name = post.get("source")
        if name not in stats:
            name = netloc_to_name.get(_netloc(url))
            if name is None:
                continue  # post from a since-removed feed
        s = stats[name]
        pub = post.get("published", "")
        s["all"] += 1
        if pub >= cutoff:
            s["window"] += 1
        if s["newest"] is None or pub > s["newest"]:
            s["newest"] = pub
        if url in incorporated_urls:
            s["inc_all"] += 1
            if pub >= cutoff:
                s["inc_window"] += 1

    lines = [
        f"# Feed Yield Report — {today.strftime('%Y-%m-%d')}",
        "",
        f"Trailing window: {days} days. Yield = practice-doc incorporations",
        "(finance/macro feeds legitimately score 0 here — they feed the repo",
        "digests, not the practice docs — judge those by digest appearances).",
        "Newest-post age > ~60d on a feed that still fetches usually means a",
        "frozen archive, not a quiet author. Regenerated weekly; not hand-edited.",
        "",
        f"| Feed | posts ({days}d) | incorporated ({days}d) | incorporated (all) | newest post | age (d) |",
        "|---|---|---|---|---|---|",
    ]
    def _age(s):
        if not s["newest"]:
            return 9999
        return (today.replace(tzinfo=None) - datetime.strptime(s["newest"], "%Y-%m-%d")).days

    for name, s in sorted(stats.items(), key=lambda kv: (-kv[1]["inc_window"], -kv[1]["window"])):
        age = _age(s)
        age_str = str(age) if age < 9999 else "never seen"
        flag = " ⚠️" if age >= 60 and age < 9999 else ""
        lines.append(f"| {name} | {s['window']} | {s['inc_window']} | {s['inc_all']} "
                     f"| {s['newest'] or '—'} | {age_str}{flag} |")

    zero = [n for n, s in stats.items() if s["window"] == 0 and _age(s) >= days]
    if zero:
        lines += ["", f"**No posts in {days}d (dead or dormant):** " + ", ".join(zero)]
    lines += _acceptance_section()
    return "\n".join(lines) + "\n"


def _acceptance_section() -> list[str]:
    """Digest-idea acceptance rate per target repo, from the verdict ledgers.

    This is the kill-criteria number: if a repo's acceptance stays ~0 for a
    quarter after the 2026-08-23 changes (practitioner feeds, narrow-delta
    guidance, verdict feedback) settle in, downgrade that digest's cadence or
    drop its issue leg rather than keep paying for it.
    """
    feedback_dir = ROOT / "data" / "digest_feedback"
    if not feedback_dir.exists():
        return []
    lines = ["", "## Digest idea acceptance (from evaluation verdicts)", ""]
    found = False
    for path in sorted(feedback_dir.glob("*.json")):
        with open(path, encoding="utf-8") as f:
            ledger = json.load(f)
        verdicts = [v for iss in ledger.get("issues", {}).values()
                    for v in iss.get("verdicts", [])]
        if not verdicts:
            continue
        found = True
        accepted = sum(1 for v in verdicts if v["verdict"] == "accepted")
        by_kind = {}
        for v in verdicts:
            by_kind[v["verdict"]] = by_kind.get(v["verdict"], 0) + 1
        breakdown = ", ".join(f"{k}: {n}" for k, n in sorted(by_kind.items(), key=lambda kv: -kv[1]))
        lines.append(f"- **{path.stem}** — {accepted}/{len(verdicts)} accepted "
                     f"({breakdown}) across {len(ledger['issues'])} evaluated issues")
    return lines if found else []


@click.command()
@click.option("--days", default=90, help="Trailing window in days")
def main(days: int):
    report = build_report(days)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report)
    print(report)


if __name__ == "__main__":
    main()
