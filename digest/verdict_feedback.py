"""
digest/verdict_feedback.py
Closes the loop between digest recommendations and their evaluations.

Each week the target repo evaluates the digest's ideas and closes the issue
with verdicts ("already built — see src/x.py", "false premise", "tracked as
#NNNN"). Until now that rejection data evaporated, so the generator kept
re-proposing the same ideas and the context yaml's hand-maintained
"Already-built" list was perpetually behind. This module:

  1. collect_verdicts(ctx): pulls recently CLOSED digest issues from the
     target repo via the local `gh` CLI, distills each issue's evaluation
     (final comments) into per-idea verdict entries with one cheap Gemini
     call, and appends them to a per-project ledger at
     data/digest_feedback/<project>.json. Issues already in the ledger are
     never re-fetched (dedup by issue number, same pattern as
     data/practice_updates/incorporated.json).
  2. render_verdict_block(project_name): renders the most recent ledger
     entries as a prompt block so the generator sees what was already
     rejected and why.

Degrades gracefully: no `gh`, no auth, no network, or a Gemini failure means
collection is skipped with a log line — the digest run itself is never
blocked, and the previously committed ledger still feeds the prompt (this is
what the GitHub Actions fallback gets, since it lacks cross-repo gh auth).
"""
import json
import subprocess
from pathlib import Path
from typing import Optional

import structlog

log = structlog.get_logger()

LEDGER_DIR = Path(__file__).parent.parent / "data" / "digest_feedback"

# How many closed issues to look back over per run, and how many ledger
# entries to inject into the prompt. Entries beyond the prompt cap stay in
# the ledger (history is cheap; prompt tokens are not).
ISSUE_LOOKBACK = 6
PROMPT_ENTRY_CAP = 30
GH_TIMEOUT_S = 60

VALID_VERDICTS = {"already-built", "false-premise", "rejected", "tracked", "accepted"}


def _ledger_path(project_name: str) -> Path:
    return LEDGER_DIR / f"{project_name}.json"


def _load_ledger(project_name: str) -> dict:
    path = _ledger_path(project_name)
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {"issues": {}}


def _save_ledger(project_name: str, ledger: dict) -> None:
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    with open(_ledger_path(project_name), "w", encoding="utf-8") as f:
        json.dump(ledger, f, indent=2, ensure_ascii=False)


def _gh_json(args: list[str]) -> Optional[object]:
    try:
        result = subprocess.run(
            ["gh"] + args, capture_output=True, text=True, timeout=GH_TIMEOUT_S,
            # Windows defaults text mode to cp1252, which dies on smart quotes
            # in issue bodies (hit on crumbl-ops#1020 at first seed).
            encoding="utf-8", errors="replace",
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        log.warning("verdict_gh_unavailable", error=str(e))
        return None
    if result.returncode != 0:
        log.warning("verdict_gh_failed", args=args[:3], stderr=result.stderr[:300])
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        log.warning("verdict_gh_bad_json", args=args[:3])
        return None


def _distill_evaluation(issue_body: str, comments: list[str],
                        project_name: str) -> Optional[list[dict]]:
    """One cheap Gemini call: evaluation text -> per-idea verdict entries."""
    # Imported here, not at module top: ai_digest imports this module, and the
    # Gemini client setup lives there.
    from digest.ai_digest import _get_gemini_client

    evaluation_text = "\n\n---\n\n".join(comments[-3:])  # verdicts land in final comments
    prompt = f"""A weekly AI-ideas digest proposed ideas to the "{project_name}" project.
The project owner evaluated them. Below is the digest issue body (the proposals)
followed by the evaluation comments (the verdicts).

ISSUE BODY (proposals):
{issue_body[:6000]}

EVALUATION COMMENTS (verdicts):
{evaluation_text[:8000]}

Extract one entry per evaluated idea as a JSON array:
[{{"idea": "short name of the proposed idea (under 15 words)",
   "verdict": "already-built|false-premise|rejected|tracked|accepted",
   "reason": "one sentence, keep any file/module/issue references verbatim"}}]

Rules:
- Only ideas that were actually evaluated. If the comments contain no
  evaluation verdicts, return [].
- "tracked" means the idea was folded into an existing issue.
- Return ONLY the JSON array, no prose."""

    try:
        client = _get_gemini_client()
        response = client.models.generate_content(
            model="gemini-2.5-flash", contents=prompt,
        )
        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("```")[1].lstrip("json\n")
        entries = json.loads(text)
    except Exception as e:
        log.warning("verdict_distill_failed", error=str(e))
        return None
    clean = [e for e in entries
             if isinstance(e, dict) and e.get("idea")
             and e.get("verdict") in VALID_VERDICTS]
    return clean


def collect_verdicts(ctx: dict) -> None:
    """Fetch newly closed digest issues and append their verdicts to the ledger."""
    gh_cfg = ctx.get("github_issue", {})
    repo, title_prefix = gh_cfg.get("repo"), gh_cfg.get("title_prefix")
    project_name = ctx.get("project_name", "unknown")
    if not repo or not title_prefix:
        return

    issues = _gh_json([
        "issue", "list", "--repo", repo, "--state", "closed",
        "--search", f'"{title_prefix}" in:title',
        "--limit", str(ISSUE_LOOKBACK),
        "--json", "number,title,closedAt",
    ])
    if not issues:
        return

    ledger = _load_ledger(project_name)
    new_count = 0
    for issue in issues:
        num = str(issue["number"])
        if num in ledger["issues"] or not issue["title"].startswith(title_prefix):
            continue
        detail = _gh_json([
            "issue", "view", num, "--repo", repo,
            "--json", "body,comments",
        ])
        if not detail:
            continue
        comments = [c.get("body", "") for c in detail.get("comments", [])]
        if not comments:
            continue  # closed without evaluation — nothing to learn
        entries = _distill_evaluation(detail.get("body", ""), comments, project_name)
        if entries is None:
            continue  # distill failed; retry next run (issue not marked seen)
        ledger["issues"][num] = {
            "title": issue["title"],
            "closed_at": issue.get("closedAt", "")[:10],
            "verdicts": entries,
        }
        new_count += 1
        log.info("verdict_collected", issue=num, verdicts=len(entries))

    if new_count:
        _save_ledger(project_name, ledger)
        log.info("verdict_ledger_updated", project=project_name, new_issues=new_count)


def render_verdict_block(project_name: str) -> str:
    """Render recent non-accepted verdicts as a prompt block ('' if none)."""
    ledger = _load_ledger(project_name)
    if not ledger["issues"]:
        return ""

    rows = []
    # Newest issues first; skip "accepted" (no need to warn the generator off wins).
    for num in sorted(ledger["issues"], key=int, reverse=True):
        for v in ledger["issues"][num]["verdicts"]:
            if v["verdict"] != "accepted":
                rows.append(f"- [{v['verdict']}] {v['idea']} — {v['reason']}")
        if len(rows) >= PROMPT_ENTRY_CAP:
            break

    if not rows:
        return ""
    return f"""
Previously proposed ideas and the owner's evaluation verdicts. Do NOT re-propose
these (or close variants) unless this week's articles add genuinely new,
technique-level information that answers the stated reason:
{chr(10).join(rows[:PROMPT_ENTRY_CAP])}
"""
