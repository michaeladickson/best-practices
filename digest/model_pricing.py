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

Run: python -m digest.model_pricing [--dry-run]
"""
from __future__ import annotations

import json
import subprocess
import urllib.request
from datetime import datetime, timezone
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


def diff(old: dict, new: dict) -> list[str]:
    """Material changes only, phrased for a human reading an issue title."""
    changes: list[str] = []
    old_models = old.get("models", {})

    for key, cur in new.items():
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
        f"{MATERIAL_CHANGE:.0%}) on the watchlist.\n\n"
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


@click.command()
@click.option("--dry-run", is_flag=True,
              help="Fetch and diff; file no issue, write no snapshot or report")
def main(dry_run: bool):
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

    if changes:
        file_issue(changes, dry_run=False)


if __name__ == "__main__":
    main()
