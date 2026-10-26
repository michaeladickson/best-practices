"""
digest/model_pricing.py
Standing price check across frontier and open-weight models.

Snapshots per-token list pricing for a watchlist of models each weekly run,
diffs against the previous snapshot, and files a GitHub issue when a tracked
model's price moves or the model disappears from the feed. Writes a
human-readable table to data/model_pricing.md so the weekly commit carries the
diff even when nothing crosses the issue threshold.

Source is OpenRouter's public /api/v1/models endpoint: unauthenticated, 445
models across 59 vendors as of 2026-09, normalized to $/token, and it carries
open-weight models (llama, qwen, deepseek, mistral, gemma, nemotron, kimi) that
no first-party pricing page aggregates.

What this is NOT, and the reason every consumer of the report needs to know it:

- These are OpenRouter's list rates. They tracked Anthropic first-party exactly
  when spot-checked (Opus 5 $5/$25, Sonnet 5 $2/$10 on 2026-09-13), but that is
  a sample, not a guarantee, and it says nothing about the others.
- Partner-operated surfaces are priced separately and are NOT represented here.
  Vertex AI and Bedrock bill on their own sheets. crumbl-ops pays Vertex rates
  for its Gemini traffic, so this file cannot answer what that costs.
- Sticker $/MTok is a screening tool, not a bill. Thinking tokens, cache-read
  rates, and batch discounts move the real number more than the headline does.

So: use this to notice that something MOVED. Go to the vendor's own pricing page
before acting on the number.

The same run watches Google's Gemini API deprecations page (#32). A deprecation
is not a price change, so the price diff never sees one. This repo's digest
calls gemini-2.5-flash through AI Studio (GEMINI_API_KEY) at three call sites
(tests/test_model_strings_pinned.py pins them), and Google announces AI Studio
shutdown dates on that page, apart from the Vertex calendar and not necessarily
by email. When a watched row's shutdown cell changes (a date where there was
"No shutdown date announced", or a new row that arrives dated), it files an
issue. A page that cannot be fetched or parsed files its own issue and exits
non-zero: "fetched and found nothing" is not "nothing announced".

Run: python -m digest.model_pricing [--dry-run] [--deprecations-only]
"""
from __future__ import annotations

import json
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

import click
import structlog

log = structlog.get_logger()

ROOT = Path(__file__).parent.parent
SNAPSHOT = ROOT / "data" / "model_pricing.json"
REPORT = ROOT / "data" / "model_pricing.md"
REPO = "michaeladickson/best-practices"

SOURCE_URL = "https://openrouter.ai/api/v1/models"
TIMEOUT = 30

# Report a move only when it clears this fraction. Vendors reprice in cents and
# the feed occasionally re-derives a rate; a 1% jitter filing an issue every
# Friday would teach us to ignore the issues, which is worse than not filing.
MATERIAL_CHANGE = 0.05

# The watchlist, grouped for the report. Prefix match on the OpenRouter id, so
# "anthropic/claude-opus-5" also catches nothing else, while "google/gemini-3.1"
# catches the whole 3.1 line. Batch variants (":batch") are folded in as a
# separate column rather than separate rows.
#
# Add a row when a model enters real consideration for our workloads. Do NOT add
# the whole catalog: this exists to notice movement in what we might actually
# run, and 445 rows of noise defeats that.
WATCHLIST = {
    "Anthropic": [
        "anthropic/claude-opus-5",
        "anthropic/claude-sonnet-5",
        "anthropic/claude-haiku-4.5",
    ],
    "Google (in use)": [
        "google/gemini-2.5-flash",
        "google/gemini-2.5-pro",
    ],
    "Google (migration targets)": [
        "google/gemini-3.1-flash-lite",
        "google/gemini-3.5-flash-lite",
        "google/gemini-3.5-flash",
        "google/gemini-3.8-flash",
    ],
    "OpenAI": [
        "openai/gpt-5.4",
        "openai/gpt-5.4-mini",
    ],
    "Open weight": [
        "qwen/qwen3.8-max",
        "deepseek/deepseek-v3",
        "moonshotai/kimi-k3",
        "google/gemma-4-31b-it",
    ],
}


DEPRECATIONS_URL = "https://ai.google.dev/gemini-api/docs/deprecations"
DEPRECATIONS_SNAPSHOT = ROOT / "data" / "model_deprecations.json"
# Rows on the deprecations page whose model id starts with one of these are
# watched. Must cover every Gemini id the code calls:
# tests/test_model_strings_pinned.py fails when a pinned id falls outside them.
DEPRECATION_WATCH_PREFIXES = ("gemini-2.5-",)
NO_SHUTDOWN_DATE = "No shutdown date announced"
DEPRECATION_ISSUE_TITLE = "Gemini deprecations page: watched model shutdown date changed"
UNREADABLE_ISSUE_TITLE = "Gemini deprecations watch: page unreadable"
# The page listed 86 distinct model ids on 2026-10-26. Far fewer means the markup
# changed under the parser, which must read as a failure, not as a quiet page.
MIN_PAGE_ROWS = 40


def _fetch() -> list[dict]:
    req = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "best-practices-digest"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.load(resp)["data"]


def _per_mtok(raw: str | None) -> float | None:
    """OpenRouter prices per token as a decimal string. Absent or empty means
    the model has no published rate, which is NOT the same as free — a $0.00
    row is explicitly free, a None row is unknown."""
    if raw in (None, ""):
        return None
    try:
        return float(raw) * 1_000_000
    except (TypeError, ValueError):
        return None


def collect(models: list[dict]) -> dict:
    """Pick the watchlist out of the full catalog.

    Matching is by prefix, and the shortest matching id wins, so
    "qwen/qwen3.8-max" resolves to the base model rather than a dated snapshot.
    A watchlist entry that matches nothing is recorded as missing rather than
    dropped — a model vanishing from the feed is exactly the event worth an
    issue, and a silently absent row would look identical to a stable one.
    """
    by_id = {m["id"]: m for m in models}
    out: dict[str, dict] = {}

    for group, patterns in WATCHLIST.items():
        for pattern in patterns:
            matches = sorted(
                (mid for mid in by_id if mid.startswith(pattern) and not mid.endswith(":batch")),
                key=len,
            )
            if not matches:
                out[pattern] = {"group": group, "missing": True}
                continue
            mid = matches[0]
            m = by_id[mid]
            p = m.get("pricing", {})
            batch = by_id.get(f"{mid}:batch", {}).get("pricing", {})
            out[pattern] = {
                "group": group,
                "resolved_id": mid,
                "input": _per_mtok(p.get("prompt")),
                "output": _per_mtok(p.get("completion")),
                "batch_input": _per_mtok(batch.get("prompt")),
                "batch_output": _per_mtok(batch.get("completion")),
                "context": m.get("context_length"),
            }
    return out


# Groups whose movement files an issue. The rest of the watchlist still lands in the
# weekly table (data/model_pricing.md) but never in the issue queue. From 2026-09-18 to
# 2026-10-24 the job filed five pricing issues, and kimi-k3 moved in every one. Four
# held nothing but open-weight re-rates on models no workload here runs; the fifth
# also moved a Gemini migration target, and would still be filed.
ISSUE_GROUPS = frozenset({"Anthropic", "Google (in use)", "Google (migration targets)"})


def diff(old: dict, new: dict, groups: frozenset | None = None) -> list[str]:
    """Material changes only, phrased for a human reading an issue title.

    `groups` limits the result to watchlist groups that warrant an issue; None
    reports every group (the dry-run view)."""
    changes: list[str] = []
    old_models = old.get("models", {})

    for key, cur in new.items():
        if groups is not None and cur.get("group") not in groups:
            continue
        prev = old_models.get(key)
        if prev is None:
            continue  # first sighting is not a change

        if cur.get("missing") and not prev.get("missing"):
            changes.append(f"**{key}** disappeared from the pricing feed")
            continue
        if prev.get("missing") and not cur.get("missing"):
            changes.append(f"**{key}** reappeared at "
                           f"${cur['input']:.2f}/${cur['output']:.2f}")
            continue

        for field, label in (("input", "input"), ("output", "output")):
            a, b = prev.get(field), cur.get(field)
            if a is None or b is None or a == 0:
                continue
            if abs(b - a) / a >= MATERIAL_CHANGE:
                direction = "up" if b > a else "down"
                changes.append(
                    f"**{key}** {label} {direction} "
                    f"${a:.2f} -> ${b:.2f} per 1M ({(b - a) / a:+.0%})")
    return changes


def render(snapshot: dict) -> str:
    ts = snapshot["fetched_at"]
    lines = [
        "# Model pricing watch",
        "",
        f"Source: OpenRouter `/api/v1/models` list rates, fetched {ts}.",
        "",
        "**These are list rates on OpenRouter's platform, not a bill.** Vertex AI",
        "and Bedrock price separately and are not represented here — crumbl-ops'",
        "Gemini traffic runs on Vertex, so this table cannot answer what it costs.",
        "Thinking tokens, cache-read rates, and batch discounts move real spend",
        "more than the headline rate does. Use this to notice movement; confirm on",
        "the vendor's own pricing page before acting.",
        "",
        "Regenerated weekly by `digest/model_pricing.py`.",
        "",
    ]

    for group in WATCHLIST:
        rows = [(k, v) for k, v in snapshot["models"].items() if v.get("group") == group]
        if not rows:
            continue
        lines += [f"## {group}", "",
                  "| Model | Input $/1M | Output $/1M | Batch in | Batch out | Context |",
                  "|---|---|---|---|---|---|"]
        for key, v in rows:
            if v.get("missing"):
                lines.append(f"| `{key}` | n/a | n/a | n/a | n/a | *not in feed* |")
                continue
            def fmt(x):
                return "n/a" if x is None else f"${x:,.2f}"
            ctx = f"{v['context']:,}" if v.get("context") else "n/a"
            lines.append(
                f"| `{v['resolved_id']}` | {fmt(v['input'])} | {fmt(v['output'])} "
                f"| {fmt(v['batch_input'])} | {fmt(v['batch_output'])} | {ctx} |")
        lines.append("")

    return "\n".join(lines)


def file_issue(changes: list[str], dry_run: bool) -> None:
    title = f"Model pricing moved ({len(changes)} change{'s' if len(changes) > 1 else ''})"
    body = (
        "Weekly price check found material movement (>= "
        f"{MATERIAL_CHANGE:.0%}) on a model we run or might migrate to.\n\n"
        + "\n".join(f"- {c}" for c in changes)
        + "\n\nFull table: `data/model_pricing.md`.\n\n"
        "**Before acting on any number here:** these are OpenRouter list rates. "
        "Partner surfaces (Vertex AI, Bedrock) price separately and are not "
        "covered — confirm on the vendor's own pricing page. A move on a model "
        "we actually run is worth a look at whether the workload should move; a "
        "move on one we don't is usually just noise worth closing.\n\n"
        "Filed by `digest/model_pricing.py`. Close if not actionable; it will "
        "not be re-filed unless the price moves again."
    )
    if dry_run:
        print(f"[dry-run] would file: {title}")
        for c in changes:
            print(f"  - {c}")
        return
    result = subprocess.run(
        ["gh", "issue", "create", "--repo", REPO, "--title", title, "--body", body],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        log.warning("pricing_issue_failed", stderr=result.stderr[:200])
    else:
        log.info("pricing_issue_filed", url=result.stdout.strip())


class _TableRows(HTMLParser):
    """Every <tr> on the page as a list of cell texts, tagged with the h2 it
    sits under. Standard library only, like digest/article_text.py."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows: list[tuple[str, list[str]]] = []
        self._section = ""
        self._heading: list[str] | None = None
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "h2":
            self._heading = []
        elif tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag):
        if tag == "h2" and self._heading is not None:
            self._section = " ".join("".join(self._heading).split())
            self._heading = None
        elif tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append((self._section, self._row))
            self._row = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)
        elif self._heading is not None:
            self._heading.append(data)


class PageUnreadable(Exception):
    pass


def parse_deprecations(page: str) -> dict[str, dict]:
    """Model id -> {section, shutdown, replacement} for every model row.

    The column is found by its "Shutdown date" header, not by position, so a
    reordered table still reads right and a renamed one fails loudly. Raises
    PageUnreadable when the page does not look like the deprecations table:
    a parse that quietly returned nothing would report every watched model as
    unannounced, the one wrong answer this check exists to prevent.
    """
    parser = _TableRows()
    parser.feed(page)

    out: dict[str, dict] = {}
    cols: tuple[int, int | None] | None = None
    headers_seen = 0
    for section, cells in parser.rows:
        lowered = [c.lower() for c in cells]
        if lowered and lowered[0] in ("model", "agent"):
            shutdown = next((i for i, c in enumerate(lowered) if "shutdown" in c), None)
            replacement = next((i for i, c in enumerate(lowered) if "replacement" in c), None)
            cols = (shutdown, replacement) if shutdown is not None else None
            headers_seen += cols is not None
            continue
        if cols is None or len(cells) <= cols[0] or not cells[0]:
            continue  # "Preview models" divider rows, or a table with no shutdown column
        shutdown_i, replacement_i = cols
        out[cells[0]] = {
            "section": section,
            "shutdown": cells[shutdown_i],
            "replacement": (cells[replacement_i]
                            if replacement_i is not None and len(cells) > replacement_i else ""),
        }

    if headers_seen == 0:
        raise PageUnreadable("no table with a Model / Shutdown date header")
    if len(out) < MIN_PAGE_ROWS:
        raise PageUnreadable(f"only {len(out)} model rows parsed (expected >= {MIN_PAGE_ROWS})")
    in_use = [p.removeprefix("google/") for p in WATCHLIST["Google (in use)"]]
    absent = [m for m in in_use if m not in out]
    if absent:
        raise PageUnreadable(f"in-use model(s) {absent} not on the page")
    return out


def watched(rows: dict[str, dict]) -> dict[str, dict]:
    return {m: v for m, v in rows.items() if m.startswith(DEPRECATION_WATCH_PREFIXES)}


def diff_deprecations(old: dict, new: dict) -> list[str]:
    """Changes to watched rows, phrased for an issue.

    Reported: a shutdown cell that changed, a new row that arrives already
    dated, and an undated row that left the page. Not reported: a dated row
    leaving (a preview reaching its shutdown and being dropped is the page
    working as intended), or anything on a baseline run.
    """
    old_rows = old.get("models")
    if not old_rows:
        return []
    changes: list[str] = []
    for model, cur in new.items():
        prev = old_rows.get(model)
        repl = f" (replacement: {cur['replacement']})" if cur["replacement"] else ""
        if prev is None:
            if cur["shutdown"] != NO_SHUTDOWN_DATE:
                changes.append(f"**{model}** added with shutdown date "
                               f"\"{cur['shutdown']}\"{repl}")
        elif prev["shutdown"] != cur["shutdown"]:
            changes.append(f"**{model}** shutdown date \"{prev['shutdown']}\" -> "
                           f"\"{cur['shutdown']}\"{repl}")
    for model, prev in old_rows.items():
        if model not in new and prev["shutdown"] == NO_SHUTDOWN_DATE:
            changes.append(f"**{model}** left the page with no shutdown date ever listed")
    return changes


def _gh(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["gh", *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def file_deprecation_issue(changes: list[str], dry_run: bool) -> bool:
    in_use = sorted(p.removeprefix("google/") for p in WATCHLIST["Google (in use)"])
    body = (
        f"The weekly check of {DEPRECATIONS_URL} found a change on a watched "
        f"row (prefixes {', '.join(DEPRECATION_WATCH_PREFIXES)}):\n\n"
        + "\n".join(f"- {c}" for c in changes)
        + "\n\nThis repo's digest calls `gemini-2.5-flash` through AI Studio "
        "(`GEMINI_API_KEY`); `tests/test_model_strings_pinned.py` lists the call "
        f"sites. Price-watch \"in use\" ids: {', '.join(in_use)}. Google lists the "
        "earliest possible shutdown date and says the exact date comes with "
        "advance notice. Other repos may call the same model through AI Studio; "
        "check their call sites before closing.\n\n"
        "To migrate, follow the bump steps in the docstring of "
        "`tests/test_model_strings_pinned.py`.\n\n"
        "Filed by `digest/model_pricing.py`. The same change is not re-filed; a "
        "further change files a new issue."
    )
    if dry_run:
        print(f"[dry-run] would file: {DEPRECATION_ISSUE_TITLE}")
        for c in changes:
            print(f"  - {c}")
        return True
    result = _gh("issue", "create", "--repo", REPO, "--title", DEPRECATION_ISSUE_TITLE,
                 "--body", body)
    if result.returncode != 0:
        log.error("deprecation_issue_failed", stderr=result.stderr[:200])
        return False
    log.info("deprecation_issue_filed", url=result.stdout.strip())
    return True


def report_unreadable(reason: str, dry_run: bool) -> None:
    """Comment on the open unreadable issue, or open one. If gh fails too, the
    error goes to the log and the exit code still says the check failed."""
    body = (
        f"The weekly check could not read {DEPRECATIONS_URL}: {reason}\n\n"
        "Until a run reads it again, nothing watches the AI Studio shutdown dates "
        "for the Gemini models this repo calls. `data/model_deprecations.json` "
        "was left as it was, so the next good read diffs against the last good "
        "one and misses nothing announced in between.\n\n"
        "Check by hand: `python -m digest.model_pricing --dry-run "
        "--deprecations-only`. Close once a weekly run reads the page again."
    )
    if dry_run:
        print(f"[dry-run] would file or comment: {UNREADABLE_ISSUE_TITLE}\n  {reason}")
        return
    found = _gh("issue", "list", "--repo", REPO, "--state", "open", "--search",
                f'"{UNREADABLE_ISSUE_TITLE}" in:title', "--json", "number,title")
    existing = []
    if found.returncode == 0:
        existing = [i["number"] for i in json.loads(found.stdout or "[]")
                    if i["title"] == UNREADABLE_ISSUE_TITLE]
    if existing:
        result = _gh("issue", "comment", str(existing[0]), "--repo", REPO, "--body", body)
    else:
        result = _gh("issue", "create", "--repo", REPO, "--title", UNREADABLE_ISSUE_TITLE,
                     "--body", body)
    if result.returncode != 0:
        log.error("deprecations_unreadable_unreported", reason=reason,
                  stderr=result.stderr[:200])


def check_deprecations(dry_run: bool) -> bool:
    """True when the page was read, whether or not anything changed."""
    try:
        req = urllib.request.Request(DEPRECATIONS_URL,
                                     headers={"User-Agent": "best-practices-digest"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            page = resp.read().decode("utf-8", errors="replace")
        rows = parse_deprecations(page)
    except Exception as e:  # network, HTTP status, or PageUnreadable
        reason = f"{type(e).__name__}: {e}"
        log.error("deprecations_unreadable", reason=reason)
        report_unreadable(reason, dry_run)
        return False

    current = watched(rows)
    old = {}
    if DEPRECATIONS_SNAPSHOT.exists():
        old = json.loads(DEPRECATIONS_SNAPSHOT.read_text(encoding="utf-8"))
    changes = diff_deprecations(old, current)
    log.info("deprecations_checked", page_rows=len(rows), watched=len(current),
             changes=len(changes))

    if dry_run:
        print(f"\nGemini deprecations ({DEPRECATIONS_URL}): {len(rows)} model rows "
              f"parsed, {len(current)} watched ({', '.join(DEPRECATION_WATCH_PREFIXES)}):")
        for model, v in sorted(current.items()):
            print(f"  {model:42} {v['shutdown']}")
        if not old:
            print("No previous snapshot: baseline run, nothing can be detected as "
                  "changed yet.")
        elif changes:
            file_deprecation_issue(changes, dry_run=True)
        else:
            print(f"No change since {old.get('fetched_at', 'the previous snapshot')}.")
        return True

    if changes and not file_deprecation_issue(changes, dry_run=False):
        return False  # old snapshot kept, so next week diffs against it and re-files
    snapshot = {
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "source": DEPRECATIONS_URL,
        "page_rows": len(rows),
        "models": current,
    }
    DEPRECATIONS_SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    DEPRECATIONS_SNAPSHOT.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    return True


def check_pricing(dry_run: bool) -> None:
    models = _fetch()
    current = collect(models)

    old = {}
    if SNAPSHOT.exists():
        old = json.loads(SNAPSHOT.read_text(encoding="utf-8"))

    changes = diff(old, current)
    snapshot = {
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "source": SOURCE_URL,
        "catalog_size": len(models),
        "models": current,
    }

    missing = [k for k, v in current.items() if v.get("missing")]
    log.info("pricing_checked", catalog=len(models), tracked=len(current),
             missing=len(missing), changes=len(changes))

    if dry_run:
        print(render(snapshot))
        if not old:
            print("\nNo previous snapshot — this is a baseline run, not a clean "
                  "comparison. Nothing can be detected as changed yet.")
        elif changes:
            print("\nChanges since last snapshot:")
            for c in changes:
                print(f"  - {c}")
        else:
            print(f"\nNo material change (>= {MATERIAL_CHANGE:.0%}) since "
                  f"{old.get('fetched_at', 'the previous snapshot')}.")
        return

    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    REPORT.write_text(render(snapshot), encoding="utf-8")

    to_file = diff(old, current, ISSUE_GROUPS)
    if to_file:
        file_issue(to_file, dry_run=False)


@click.command()
@click.option("--dry-run", is_flag=True,
              help="Fetch and diff; file no issue, write no snapshot or report")
@click.option("--deprecations-only", is_flag=True,
              help="Skip the price check; run only the deprecations-page watch")
def main(dry_run: bool, deprecations_only: bool):
    # Each check runs whatever the other did. Either failing exits 1, so the
    # wrapper's WARNING line names this step.
    ok = True
    if not deprecations_only:
        try:
            check_pricing(dry_run)
        except Exception as e:
            log.error("pricing_check_failed", error=f"{type(e).__name__}: {e}")
            ok = False
    if not check_deprecations(dry_run):
        ok = False
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
