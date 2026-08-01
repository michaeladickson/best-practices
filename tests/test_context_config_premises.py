"""Regression tests for the digest context configs.

The generator reasons about each project from its context YAML alone — it never
reads the target repo. So a wrong line here does not produce a small error; it
produces a confidently-wrong "10/10 relevance" recommendation that costs a full
human evaluation cycle to disprove.

That has now happened twice, both from the same line:

  crumbl-ops#968  (2026-07-15)  two ideas rated 10/10 on "Gemini does vendor
                                invoice extraction"
  crumbl-ops#1252 (2026-08-01)  two more ideas on the identical premise

Invoice parsing in crumbl-ops is deterministic per-vendor code
(src/invoices/vendors.py) and has never involved an LLM. Every idea in both
issues was premise-broken or already-built.

These tests pin the corrections so a future rewrite of the YAML cannot silently
drop them. They assert on the config text only — no network, no Gemini, no
cross-repo filesystem access (the target repos are not present on every machine
that runs this suite).
"""
from pathlib import Path

import pytest
import yaml

CONFIG_DIR = Path(__file__).resolve().parent.parent / "digest" / "config"
CRUMBL = CONFIG_DIR / "context-crumbl-ops.yaml"


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _all_text(cfg: dict) -> str:
    return "\n".join(v for v in cfg.values() if isinstance(v, str)).lower()


# Discovered by glob, never hand-listed — a new project config is covered
# automatically instead of being the one nobody remembered to add.
ALL_CONFIGS = sorted(CONFIG_DIR.glob("context-*.yaml"))


def test_configs_discovered():
    """An empty glob would make every parametrised test below vacuous."""
    assert len(ALL_CONFIGS) >= 3, f"found only {[p.name for p in ALL_CONFIGS]}"


@pytest.mark.parametrize("path", ALL_CONFIGS, ids=lambda p: p.name)
def test_config_parses_with_required_keys(path: Path):
    cfg = _load(path)
    required = {
        "project_name", "description", "tech_stack",
        "current_ai_usage", "key_areas", "interests",
    }
    assert required <= set(cfg), f"{path.name} missing {required - set(cfg)}"


_NOT_AI_MARKER = "explicitly not ai"


def _affirmative_text(cfg: dict) -> str:
    """The parts of the config that ASSERT what the platform currently uses.

    Structural split, not word-proximity: everything from the 'Explicitly NOT
    AI' marker onward is the correction itself, and naturally contains both an
    LLM name and the word 'invoice' in one sentence. An earlier version of this
    test scanned the whole file and false-failed on its own fix — the classic
    substring-tripwire trap.
    """
    usage = cfg["current_ai_usage"].lower()
    idx = usage.find(_NOT_AI_MARKER)
    affirmative_usage = usage[:idx] if idx != -1 else usage
    return "\n".join(
        [cfg["description"].lower(), cfg["tech_stack"].lower(), affirmative_usage]
    )


def test_crumbl_does_not_claim_ai_invoice_extraction():
    """The exact false premise behind #968 and #1252.

    Matches the CLAIM shape (an LLM doing invoice/document extraction), not the
    bare word 'invoice' — the config legitimately mentions invoice processing as
    a key area, and must keep being able to.
    """
    llm = ("gemini", "claude", "llm", "ai ")
    for line in _affirmative_text(_load(CRUMBL)).splitlines():
        if not any(tok in line for tok in llm):
            continue
        # A line that names an LLM must not also assign it invoice/PDF parsing.
        mentions_extraction = (
            ("invoice" in line or "pdf" in line or "receipt" in line)
            and ("extract" in line or "pars" in line)
        )
        assert not mentions_extraction, (
            "context-crumbl-ops.yaml appears to attribute invoice/document "
            f"extraction to an LLM again:\n    {line.strip()}\n\n"
            "Invoice parsing is deterministic per-vendor code "
            "(src/invoices/vendors.py), zero LLM calls. This premise produced "
            "crumbl-ops#968 and #1252 — do not reintroduce it."
        )


def test_premise_check_would_catch_the_original_bad_line():
    """Counterfactual — a tripwire that cannot fail is worthless.

    Feeds the test the ACTUAL line from the pre-2026-08-01 config and asserts
    the detector fires on it.
    """
    bad = {
        "description": "Operations platform for 6 Crumbl locations.",
        "tech_stack": (
            "AI: Gemini for vendor invoice extraction + email classification"
        ),
        "current_ai_usage": "- Gemini for vendor invoice PDF extraction\n",
    }
    hits = [
        line for line in _affirmative_text(bad).splitlines()
        if any(t in line for t in ("gemini", "claude", "llm", "ai "))
        and ("invoice" in line or "pdf" in line)
        and ("extract" in line or "pars" in line)
    ]
    assert hits, "detector failed to fire on the known-bad historical config"


def test_crumbl_keeps_the_explicit_not_ai_section():
    """The positive guard, not just the absence of the bad string.

    Absence alone would pass on a config that had been gutted. The generator
    needs the explicit negative statement to avoid re-inferring the premise.
    """
    usage = _load(CRUMBL)["current_ai_usage"].lower()
    assert "not ai" in usage or "zero llm" in usage, (
        "context-crumbl-ops.yaml lost its explicit 'NOT AI' section. The "
        "generator re-infers 'Gemini parses invoices' without it — that is how "
        "#1252 happened after #968 had already corrected the record."
    )
    assert "vendors.py" in usage, (
        "the NOT-AI section should name src/invoices/vendors.py so the claim is "
        "checkable rather than assertive"
    )


def test_crumbl_does_not_claim_lightgbm_forecasting():
    """Stale as of 2026-05: the ML models were deleted when v3 replaced them.

    Only a requirements pin remains, and #1252 idea 4 reasoned from a
    'LightGBM baseline' that no longer exists in src/.
    """
    text = _all_text(_load(CRUMBL))
    assert "lightgbm" not in text or "deleted" in text, (
        "context-crumbl-ops.yaml describes LightGBM as current. There are no "
        "lightgbm imports in crumbl-ops/src/ — the v3 forecast replaced them."
    )


def test_crumbl_store_count_is_current():
    """The acquisitions closed; '3 stores expanding' misdescribes the business."""
    desc = _load(CRUMBL)["description"].lower()
    assert "6 crumbl" in desc or "six crumbl" in desc, (
        "context-crumbl-ops.yaml should state the current 6-store roster; a "
        "stale count skews every scale-sensitive recommendation."
    )
