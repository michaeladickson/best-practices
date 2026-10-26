"""Tripwire: LLM model-string literals are pinned (#28).

practice_updater.py auto-edits the living practice docs every Friday, guarded
only by a structural validator (H1 and anchors survive, length in bounds). A
model change that degraded the edits would pass that validator and land as an
[automated] commit. This test is what makes such a change visible: a bump
cannot merge without editing EXPECTED_MODEL_STRINGS in the same change.
Offline, no network. Ported from crumbl-ops tests/test_model_strings_pinned.py.

When you intentionally bump a model:
  1. Run the old and new model on the same real input (a week's archived
     articles through `python -m digest.practice_updater --dry-run`) and compare.
  2. Update EXPECTED_MODEL_STRINGS below, with the reason.
  3. Move the price watch (WATCHLIST "Google (in use)" in digest/model_pricing.py)
     to the new id; the test at the bottom fails until you do.
  4. Update the documented default in practices/ai/gemini-integration.md.

Scope: code only (.py/.yml/.yaml/.sh under digest/, scripts/,
.github/workflows/). Prose mentions in docs are intentionally not scanned: a
doc naming a model is not a call site, and scanning prose makes the gate noisy
enough to be disabled.
"""
import re
from pathlib import Path

from digest import model_pricing

# The complete set of model identifiers the code is allowed to call. Today that
# is one model at three call sites: ai_digest.py (analysis),
# practice_updater.py (GEMINI_MODEL), verdict_feedback.py (verdict extraction),
# all through AI Studio with GEMINI_API_KEY.
EXPECTED_MODEL_STRINGS = {
    "gemini-2.5-flash",
}

_ROOT = Path(__file__).resolve().parent.parent
_SCAN_DIRS = ["digest", "scripts", ".github/workflows"]
_SCAN_SUFFIXES = {".py", ".yml", ".yaml", ".sh"}
_MODEL_RE = re.compile(
    # The OpenRouter price-watch ids in model_pricing.py ("google/gemini-2.5-pro",
    # "anthropic/claude-opus-5") are not call sites: they name models we watch,
    # including ones we do not run. Scanned as call sites they would also hide a
    # bump to a watched migration target, since that id is already in the set.
    # The lookbehinds skip exactly those two vendor prefixes, so the API's own
    # "models/gemini-..." path form still counts.
    r"(?<!google/)(?<!anthropic/)"
    r"(?:"
    # The trailing (?:-[a-z0-9]+)* is load-bearing. Without it the pattern
    # stops at the tier: "gemini-3.1-flash-lite" scans as "gemini-3.1-flash", a
    # different and more expensive model, and Flash and Flash-Lite collapse
    # onto one string. Flash-Lite is Google's recommended successor to 2.5
    # Flash, so that is where the next bump is most likely to land.
    r"gemini-\d+\.\d+-(?:flash|pro)(?:-[a-z0-9]+)*"
    r"|claude-(?:opus|sonnet|haiku|fable|mythos)-\d+(?:-\d+)*"
    r")"
)


def test_model_regex_captures_qualified_ids_in_full():
    """Offline guard on the pattern itself. The scan only sees ids the repo
    already uses; the ids this protects are the ones not migrated to yet."""
    cases = {
        "gemini-2.5-flash": "gemini-2.5-flash",
        "gemini-2.5-pro": "gemini-2.5-pro",
        "gemini-3.1-flash-lite": "gemini-3.1-flash-lite",
        "gemini-3.5-flash-lite": "gemini-3.5-flash-lite",
        "gemini-3.8-flash": "gemini-3.8-flash",
        "gemini-2.5-flash-image": "gemini-2.5-flash-image",
        "gemini-2.5-flash-lite-preview-09-2025": "gemini-2.5-flash-lite-preview-09-2025",
        'model="models/gemini-3.6-flash"': "gemini-3.6-flash",
        "claude-opus-5": "claude-opus-5",
        "claude-opus-5-5": "claude-opus-5-5",
        "claude-fable-5-1": "claude-fable-5-1",
        "claude-haiku-4-5-20251001": "claude-haiku-4-5-20251001",
    }
    for raw, expected in cases.items():
        found = _MODEL_RE.findall(raw)
        assert found == [expected], f"{raw!r} scanned as {found!r}, expected [{expected!r}]"

    assert _MODEL_RE.findall("gemini-3.1-flash") != _MODEL_RE.findall("gemini-3.1-flash-lite")
    assert _MODEL_RE.findall("claude-opus-5") != _MODEL_RE.findall("claude-opus-5-1")
    # Price-watch ids are not call sites.
    assert _MODEL_RE.findall('"google/gemini-3.5-flash", "anthropic/claude-opus-5"') == []


def _scan_model_strings() -> tuple[set[str], int]:
    found: set[str] = set()
    scanned = 0
    for d in _SCAN_DIRS:
        for p in (_ROOT / d).rglob("*"):
            if p.suffix not in _SCAN_SUFFIXES or not p.is_file():
                continue
            try:
                text = p.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            scanned += 1
            found.update(_MODEL_RE.findall(text))
    return found, scanned


def test_model_strings_match_pinned_set():
    found, scanned = _scan_model_strings()
    # 19 files on 2026-10-26. A scan that reached almost nothing would pass
    # against an empty pinned set; this keeps a wrong _ROOT from reading green.
    assert scanned >= 10, f"scan reached only {scanned} files; is _ROOT right?"
    assert found == EXPECTED_MODEL_STRINGS, (
        "LLM model-string set changed. This is a model-upgrade gate.\n"
        f"  found:    {sorted(found)}\n"
        f"  expected: {sorted(EXPECTED_MODEL_STRINGS)}\n"
        "Before bumping: run the old and new model on the same week's articles "
        "(`python -m digest.practice_updater --dry-run`) and compare the edits. "
        "Then update EXPECTED_MODEL_STRINGS in this file with the reason, move "
        "the price watch in digest/model_pricing.py, and "
        "update the default in practices/ai/gemini-integration.md."
    )


def _pinned_gemini() -> set[str]:
    return {m for m in EXPECTED_MODEL_STRINGS if m.startswith("gemini-")}


def test_price_watch_tracks_the_models_in_use():
    """The price watch's "in use" group is the pinned set, so a bump that left
    it watching the old model would fail here instead of reporting stale rates."""
    in_use = {p.removeprefix("google/") for p in model_pricing.WATCHLIST["Google (in use)"]}
    assert _pinned_gemini() <= in_use, (
        f"pinned Gemini ids {sorted(_pinned_gemini() - in_use)} are not in "
        "WATCHLIST['Google (in use)'] in digest/model_pricing.py")

