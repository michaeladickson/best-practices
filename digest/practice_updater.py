"""
digest/practice_updater.py

Weekly maintenance step: scan the week's archived articles for genuinely-new best
practices relevant to the living practice docs, and AUTO-EDIT those docs in place.

Runs after the per-context digests in scripts/run_weekly_digest.sh. Reuses the feed
archive (already populated by those digests) and the Gemini client from ai_digest.

Auto-edit mode (chosen deliberately — writes land in the curated body with no staging
step). Safeguards, since this also edits the very doc about preventing AI slop:

  1. Dedup ledger (data/practice_updates/incorporated.json): a source article is never
     integrated into the same doc twice.
  2. Two-stage LLM: (a) extract NEW, actionable candidates not already covered;
     (b) integrate them into the full doc.
  3. Structural validation before any write: H1 preserved, required anchors present,
     length within sane bounds. On failure the doc is left untouched and the articles
     are NOT marked incorporated (so it retries next week). Git history is the backstop.

Usage:
    python -m digest.practice_updater --days 7
    python -m digest.practice_updater --dry-run        # show diffs, write nothing
"""
import difflib
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

import click
import structlog
import yaml

from digest.ai_digest import (
    _get_gemini_client,
    _load_feeds,
    _fetch_recent_posts,
    fetch_all_archived_posts,
)

log = structlog.get_logger()

REPO_ROOT = Path(__file__).parent.parent
CONFIG_DIR = Path(__file__).parent / "config"
LEDGER_PATH = REPO_ROOT / "data" / "practice_updates" / "incorporated.json"
GEMINI_MODEL = "gemini-2.5-flash"

# Validation bounds for an auto-edit. A good edit grows the doc a little; these guard
# against truncation (model dropped content) and runaway (model hallucinated bulk).
MIN_LEN_RATIO = 0.85
MAX_LEN_RATIO = 2.5

# Absolute ceiling. The ratio bounds alone compound (each week's growth becomes next
# week's baseline — the docs 2-4x'd in their first two months), so a doc that reaches
# this size stops accepting auto-edits until a human consolidation pass shrinks it.
# Checked before spending LLM calls and again on the integrated output.
MAX_DOC_BYTES = 70_000
NEAR_CAP_RATIO = 0.85


def _load_doc_config(path: Optional[str] = None) -> tuple[list[dict], list[str]]:
    p = Path(path) if path else CONFIG_DIR / "practice-docs.yaml"
    with open(p) as f:
        cfg = yaml.safe_load(f)
    return cfg["docs"], cfg.get("required_anchors", [])


def _load_ledger() -> dict:
    if LEDGER_PATH.exists():
        with open(LEDGER_PATH) as f:
            return json.load(f)
    return {}


def _save_ledger(ledger: dict):
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LEDGER_PATH, "w") as f:
        json.dump(ledger, f, indent=2, sort_keys=True)


def _recent_posts(days: int, feeds_path: Optional[str]) -> list[dict]:
    """Prefer the archive (digests just populated it); fetch only if it's empty."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    posts = [p for p in fetch_all_archived_posts() if p.get("published", "") >= cutoff]
    if posts:
        log.info("practice_posts_from_archive", within_window=len(posts), days=days)
        return posts
    log.info("practice_archive_empty_fetching", days=days)
    return _fetch_recent_posts(_load_feeds(feeds_path), days=days)


def _keyword_prefilter(posts: list[dict], keywords: list[str]) -> list[dict]:
    kws = [k.lower() for k in keywords]
    out = []
    for p in posts:
        hay = f" {p.get('title','')} {p.get('content_preview','')} ".lower()
        if any(k in hay for k in kws):
            out.append(p)
    return out


def _strip_json_fence(text: str) -> str:
    if "```json" in text:
        return text.split("```json")[1].split("```")[0]
    if "```" in text:
        parts = text.split("```")
        if len(parts) >= 3:
            return parts[1]
    return text


def _unwrap_markdown_fence(text: str) -> str:
    """If the model wrapped the whole doc in a ```markdown fence, unwrap it."""
    t = text.strip()
    if t.startswith("```"):
        first_nl = t.find("\n")
        if first_nl != -1:
            t = t[first_nl + 1:]
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    return t.strip() + "\n"


def _existing_headings(doc_text: str) -> list[str]:
    return [ln.strip() for ln in doc_text.splitlines() if ln.lstrip().startswith("#")]


def _posts_block(posts: list[dict]) -> str:
    block = ""
    for i, p in enumerate(posts, 1):
        block += f"\n--- Article {i} ---\n"
        block += f"Title: {p.get('title','Untitled')}\n"
        block += f"Source: {p.get('source','?')} [{p.get('category','')}]\n"
        block += f"Date: {p.get('published','?')}\n"
        block += f"URL: {p.get('link','')}\n"
        block += f"Content:\n{p.get('content_preview','')}\n"
    return block


def _extract_candidates(client, topic: str, scope: str,
                        headings: list[str], posts: list[dict]) -> list[dict]:
    """Stage 1 — find NEW, concretely-actionable practices not already in the doc."""
    prompt = f"""You maintain a curated engineering best-practices document.

Topic of the document: {topic}

Scope it already covers:
{scope}

Section headings already in the document (do NOT propose anything already covered by these):
{chr(10).join('- ' + h for h in headings)}

Here are this week's articles:
{_posts_block(posts)}

Identify only GENUINELY NEW, concretely-actionable best practices on this exact topic
that the document does not already cover. Be strict: most weeks will yield 0-2. Ignore
vendor news, pricing, model-release chatter, and anything generic or off-topic.

Return a JSON object:
{{
  "candidates": [
    {{
      "practice": "One-line imperative best practice (concrete, actionable).",
      "detail": "2-3 sentences a maintainer can paste into the doc body.",
      "source_title": "exact article title",
      "source_name": "publication/author",
      "source_url": "exact URL from the article block",
      "source_date": "YYYY-MM-DD from the article block",
      "confidence": "high|medium|low",
      "not_already_covered_because": "1 sentence on why this is new vs the headings above"
    }}
  ]
}}

Rules:
- Only include high or medium confidence items. Drop low-confidence ones.
- Each candidate MUST map to a specific article in the block above (real URL).
- If nothing genuinely new and on-topic exists, return {{"candidates": []}}.
"""
    resp = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
    try:
        data = json.loads(_strip_json_fence(resp.text).strip())
    except json.JSONDecodeError as e:
        log.error("extract_json_parse_failed", error=str(e), head=(resp.text or "")[:200])
        return []
    cands = data.get("candidates", [])
    # keep only candidates that reference a URL actually present in this batch
    valid_urls = {p.get("link", "") for p in posts}
    return [c for c in cands if c.get("source_url") in valid_urls
            and c.get("confidence") in ("high", "medium")]


def _integrate(client, doc_text: str, topic: str, candidates: list[dict]) -> Optional[str]:
    """Stage 2 — integrate candidates into the full document, return the new full text."""
    cand_text = json.dumps(candidates, indent=2)
    prompt = f"""You are editing a curated engineering best-practices document (Markdown).
Topic: {topic}

Integrate the new practices below into the document. Then return the COMPLETE updated
document and nothing else (no commentary, no code fence around it).

NEW PRACTICES TO INTEGRATE:
{cand_text}

CURRENT DOCUMENT:
{doc_text}

Editing rules — follow exactly:
- Preserve the document's structure, voice, and ALL existing sections and headings,
  including the H1 title, the "## Self-Assessment" pointer, "## Sources", and
  "## Where Used". Do not delete existing content.
- **Preserve markdown links exactly.** Every `[label](url)` in the current document
  must remain `[label](url)` in your output. Never flatten a link to `[label]`,
  strip its URL, or alter its bracket / parenthesis syntax. This applies to every
  link in "## Sources", inline links, and anywhere else.
- **Check for duplication BEFORE adding a numbered practice.** For each candidate,
  scan the existing "## Best Practices" section for a practice covering the same
  IDEA (not the same wording — match on substance). If one exists, DO NOT add a
  new numbered practice; instead add ONLY a bullet to "## Sources" attributing the
  new article. Splitting one clear practice into two overlapping ones is worse
  than adding nothing. When in doubt, prefer a Sources-only addition.
- **No cosmetic churn on unchanged content.** Do not alter whitespace, list-marker
  spacing (e.g. `1. ` vs `1.  `), capitalization, or ordering of any line whose
  meaning you are not directly changing. If a line is unchanged in meaning, output
  it byte-for-byte.
- Integrate each GENUINELY-NEW practice into the most fitting place: add a new
  numbered practice under "## Best Practices", add a row to the failure-mode or
  anti-pattern table if it fits, and/or refine an adjacent existing practice.
  Keep numbering consistent.
- Be surgical and concise. Do not pad. Match the existing formatting exactly.
- For EVERY article you draw from — whether it produces a new numbered practice
  OR a Sources-only addition — append a matching bullet to the "## Sources"
  section in the existing format: **Title** (source) — one phrase. Digest: YYYY-MM-DD.
- Do not invent sources, URLs, or claims beyond what the new practices state.
- Return only the full Markdown document.
"""
    resp = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
    if not resp.text:
        return None
    return _unwrap_markdown_fence(resp.text)


_MD_LINK_RE = re.compile(r"\[[^\]]+\]\([^)]+\)")
_PRACTICE_HEADING_RE = re.compile(r"^###\s+\d+\.\s+(.+?)\s*$")
_HEADING_STOP = frozenset({
    "a", "an", "the", "of", "to", "for", "and", "or", "in", "on", "at", "by",
    "with", "from", "into", "not", "no", "it", "is", "be", "as", "via",
    "own", "use", "your", "you", "this", "that", "then", "when", "if", "but",
    "so", "just", "any", "all", "each", "one", "two",
})


def _count_md_links(text: str) -> int:
    return len(_MD_LINK_RE.findall(text))


def _heading_key(title: str) -> tuple[str, ...]:
    """First 3 content tokens of a heading, lowercased and stop-word-stripped.
    Empty tuple if fewer than 3 content tokens (too short to compare)."""
    words = re.sub(r"[^\w\s]", " ", title.lower()).split()
    content = [w for w in words if w not in _HEADING_STOP and len(w) > 2]
    return tuple(content[:3]) if len(content) >= 3 else ()


def _duplicate_heading_pairs(text: str) -> list[tuple[str, str]]:
    """Pairs of numbered `### N. Title` headings sharing the same 3-content-word key."""
    by_key: dict[tuple[str, ...], list[str]] = {}
    for ln in text.splitlines():
        m = _PRACTICE_HEADING_RE.match(ln.strip())
        if not m:
            continue
        k = _heading_key(m.group(1))
        if k:
            by_key.setdefault(k, []).append(m.group(1))
    pairs: list[tuple[str, str]] = []
    for hs in by_key.values():
        for i, h1 in enumerate(hs):
            for h2 in hs[i + 1:]:
                pairs.append((h1, h2))
    return pairs


def _validate(old: str, new: str, required_anchors: list[str]) -> tuple[bool, str]:
    if not new or not new.strip():
        return False, "empty response"
    old_lines = old.splitlines()
    old_h1 = next((ln.strip() for ln in old_lines if ln.startswith("# ")), None)
    if old_h1 and old_h1 not in new:
        return False, f"H1 missing ({old_h1!r})"
    for anchor in required_anchors:
        if anchor in old and anchor not in new:
            return False, f"required anchor dropped ({anchor!r})"
    if len(new) < MIN_LEN_RATIO * len(old):
        return False, f"suspiciously short ({len(new)} < {MIN_LEN_RATIO}*{len(old)})"
    if len(new) > MAX_LEN_RATIO * len(old):
        return False, f"suspiciously long ({len(new)} > {MAX_LEN_RATIO}*{len(old)})"
    if len(new) > MAX_DOC_BYTES:
        return False, f"exceeds absolute cap ({len(new)} > {MAX_DOC_BYTES}); consolidate the doc"
    # Structural defenses against the specific failure modes seen in the
    # 2026-07-05 dry-run (URL flattening in Sources; duplicate practice
    # headings). Both are "new-only" — pre-existing baseline issues don't
    # cause perpetual rejects.
    old_links = _count_md_links(old)
    new_links = _count_md_links(new)
    if new_links < old_links:
        return False, f"markdown links dropped ({old_links} -> {new_links})"
    fresh_dupes = set(_duplicate_heading_pairs(new)) - set(_duplicate_heading_pairs(old))
    if fresh_dupes:
        h1, h2 = next(iter(fresh_dupes))
        return False, f"new duplicate practice heading: {h1!r} vs {h2!r}"
    return True, "ok"


def _process_doc(doc: dict, required_anchors: list[str], posts: list[dict],
                 ledger: dict, dry_run: bool, get_client) -> dict:
    """Returns a result dict; mutates ledger only on success / confirmed no-op."""
    rel_path = doc["path"]
    abs_path = REPO_ROOT / rel_path
    result = {"doc": rel_path, "status": "skipped", "candidates": 0}

    if not abs_path.exists():
        log.warning("practice_doc_missing", path=rel_path)
        result["status"] = "missing"
        return result

    seen = set(ledger.get(rel_path, []))
    candidate_posts = _keyword_prefilter(posts, doc.get("keywords", []))
    new_posts = [p for p in candidate_posts if p.get("link", "") not in seen]
    log.info("practice_prefilter", doc=rel_path, prefiltered=len(candidate_posts),
             new_after_ledger=len(new_posts))
    if not new_posts:
        result["status"] = "no_new_articles"
        return result

    doc_text = abs_path.read_text(encoding="utf-8")
    if len(doc_text) >= MAX_DOC_BYTES:
        # Don't spend LLM calls integrating into a doc that validation would reject
        # anyway. Articles are NOT marked seen — they get another shot after a human
        # consolidation pass brings the doc back under the cap.
        log.warning("practice_doc_at_capacity", doc=rel_path,
                    bytes=len(doc_text), cap=MAX_DOC_BYTES)
        result["status"] = "at_capacity:consolidate"
        return result
    client = get_client()
    candidates = _extract_candidates(
        client, doc["topic"], doc.get("scope", ""), _existing_headings(doc_text), new_posts
    )
    result["candidates"] = len(candidates)
    considered_urls = [p.get("link", "") for p in new_posts if p.get("link")]

    if not candidates:
        # Nothing worth adding — mark the considered articles as seen so we don't
        # re-evaluate them every week.
        ledger[rel_path] = sorted(seen.union(considered_urls))
        result["status"] = "no_candidates"
        return result

    new_text = _integrate(client, doc_text, doc["topic"], candidates)
    ok, reason = _validate(doc_text, new_text or "", required_anchors)
    if not ok:
        # Leave the doc untouched and do NOT mark articles seen — retry next week.
        log.error("practice_update_rejected", doc=rel_path, reason=reason)
        result["status"] = f"rejected:{reason}"
        return result

    if dry_run:
        diff = "".join(difflib.unified_diff(
            doc_text.splitlines(keepends=True), new_text.splitlines(keepends=True),
            fromfile=f"a/{rel_path}", tofile=f"b/{rel_path}",
        ))
        result["status"] = "would_update"
        result["diff"] = diff
        result["incorporated"] = [c.get("source_title") for c in candidates]
        return result

    abs_path.write_text(new_text, encoding="utf-8")
    if len(new_text) > NEAR_CAP_RATIO * MAX_DOC_BYTES:
        log.warning("practice_doc_near_capacity", doc=rel_path,
                    bytes=len(new_text), cap=MAX_DOC_BYTES)
    # Mark the source articles (those that produced candidates) AND the rest of the
    # considered batch as incorporated/seen.
    incorporated_urls = {c.get("source_url") for c in candidates if c.get("source_url")}
    ledger[rel_path] = sorted(seen.union(considered_urls).union(incorporated_urls))
    log.info("practice_doc_updated", doc=rel_path, added=len(candidates))
    result["status"] = "updated"
    result["incorporated"] = [c.get("source_title") for c in candidates]
    return result


@click.command()
@click.option("--days", default=7, help="Look back N days for new posts")
@click.option("--dry-run", is_flag=True, help="Show diffs, write nothing, touch no ledger")
@click.option("--docs", "docs_path", default=None,
              help="Path to practice-docs YAML (default: config/practice-docs.yaml)")
@click.option("--feeds", "feeds_path", default=None,
              help="Path to feeds YAML (used only if the archive is empty)")
def main(days: int, dry_run: bool, docs_path: Optional[str], feeds_path: Optional[str]):
    """Auto-update the living practice docs from this week's articles."""
    docs, required_anchors = _load_doc_config(docs_path)
    posts = _recent_posts(days, feeds_path)
    if not posts:
        print("No recent posts in window — nothing to update.")
        return

    ledger = _load_ledger()
    ledger_before = json.dumps(ledger, sort_keys=True)

    # Lazy client so a no-article week makes zero API calls.
    _client_cache = {}

    def get_client():
        if "c" not in _client_cache:
            _client_cache["c"] = _get_gemini_client()
        return _client_cache["c"]

    results = []
    for doc in docs:
        try:
            results.append(_process_doc(doc, required_anchors, posts, ledger,
                                        dry_run, get_client))
        except Exception as e:  # one doc failing must not abort the others
            log.error("practice_doc_failed", doc=doc.get("path"), error=str(e))
            results.append({"doc": doc.get("path"), "status": f"error:{e}", "candidates": 0})

    if not dry_run and json.dumps(ledger, sort_keys=True) != ledger_before:
        _save_ledger(ledger)

    # Human-readable summary (also useful in the scheduled-task log).
    print("\n=== Practice-doc update summary ===")
    for r in results:
        line = f"- {r['doc']}: {r['status']}"
        if r.get("candidates"):
            line += f" ({r['candidates']} candidate(s))"
        print(line)
        for title in r.get("incorporated", []) or []:
            print(f"    + {title}")
        if dry_run and r.get("diff"):
            print(r["diff"])

    updated = [r for r in results if r["status"] in ("updated", "would_update")]
    if dry_run:
        print(f"\nDry run: {len(updated)} doc(s) would change. No files or ledger written.")
    else:
        print(f"\n{len(updated)} doc(s) updated.")

    # A blocked doc silently discards that week's candidates and will block again
    # next week for the same reason — it needs a human. Exit non-zero so the caller
    # (run_weekly_digest.sh) counts it and the run reports FAILED. Before this,
    # main() always returned None, so a doc could be rejected every week for months
    # while the job reported success: on 2026-08-01 code-review-and-ai-slop.md was
    # rejected over the size cap, dropping 75 candidates, and the run still exited 0.
    #
    # Only these statuses block. no_new_articles / no_candidates are normal weeks
    # and must NOT fail the run.
    blocked = [r for r in results
               if r["status"].startswith(("rejected:", "at_capacity:", "error:"))
               or r["status"] == "missing"]
    if blocked:
        print(f"\n=== {len(blocked)} doc(s) BLOCKED — candidates discarded, needs a human ===")
        for r in blocked:
            lost = f", {r['candidates']} candidate(s) lost" if r.get("candidates") else ""
            print(f"  ! {r['doc']}: {r['status']}{lost}")
        print("  These will block again next week until resolved.")
        sys.exit(1)


if __name__ == "__main__":
    main()
