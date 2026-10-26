"""
test_closing_keyword_gate.py
The gate must fire on every phrasing that has actually closed an issue in a
consumer repo, and stay quiet on the ordinary ways those repos cite issues.

A tripwire never shown to fire is not a tripwire: each historical strike is a
case below, verbatim where the text survives.

Canonical copy lives next to the hook in best-practices/.claude/hooks/; repos that
carry the gate carry this file too, beside the hook or under tests/. It finds the
hook by walking up from its own location, so it runs unchanged in either place.
"""
import importlib.util
import io
import json
from pathlib import Path

import pytest


def _find_hook() -> Path:
    for d in [Path(__file__).resolve().parent, *Path(__file__).resolve().parents]:
        for cand in (d / ".claude" / "hooks" / "closing_keyword_gate.py",
                     d / "closing_keyword_gate.py"):
            if cand.is_file():
                return cand
    raise FileNotFoundError("closing_keyword_gate.py not found above " + __file__)


_PATH = _find_hook()
_spec = importlib.util.spec_from_file_location("closing_keyword_gate", _PATH)
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)

OPEN = {261, 247, 1851, 1418, 1802}


@pytest.mark.parametrize("text,issue", [
    ("Merge pull request #264 from owner/claude/261-small-fixes\n\n#261: small",
     261),                                                              # strike
    ("The small fixes from #261.", 261),                                # one word between
    ("the fix #247 settled on is generic shared prompts", 247),         # strike
    ("Does NOT close #1851. This makes the existing path carry", 1851),  # strike
    ("Ready to close #1851 once this lands", 1851),                     # strike
    ("no auto-close: #1418", 1418),                                     # strike
    ("proposes nothing, fixed 2026-08-20\nunder #1802, and the", 1802),  # strike
])
def test_every_phrasing_that_closed_an_issue_is_caught(text, issue):
    assert [n for n, _ in gate.risky_references(text, OPEN)] == [issue]


@pytest.mark.parametrize("text", [
    "Closes #261",                                  # deliberate, own line
    "Body text.\n\nFixes: #261\n",
    "#261 stays open for the decisions.",
    "The first three items of #261, the ones that produce wrong numbers.",
    "fix(api): /exchange order (#46)",              # #46 is closed: re-close is a no-op
    # #262's commit style, which did NOT close #261: the keyword is ten words away.
    "fix(categorizer): a row it could not label is stored with no category\n\n#261. A",
    "A fixed cost. Then #261 is mentioned.",        # a period ends the sentence
])
def test_ordinary_references_pass(text):
    assert gate.risky_references(text, OPEN) == []


def test_a_deliberate_line_does_not_excuse_a_different_issue():
    text = "Closes #261\nAlso the fix #247 approach."
    assert [n for n, _ in gate.risky_references(text, OPEN)] == [247]


@pytest.mark.parametrize("command,verb", [
    ("gh pr create -R a/b --title t --body-file x.md", "create"),
    ("cd x && gh pr merge 264 -R a/b --merge", "merge"),
    ("gh pr edit 12 --body 'hi'", "edit"),
])
def test_pr_commands_are_recognised(command, verb):
    assert gate._pr_commands(command)[0][0] == verb


@pytest.mark.parametrize("command", ["gh pr view 12", "gh issue close 5", "git commit -m x"])
def test_other_commands_are_left_alone(command):
    assert gate._pr_commands(command) == []


@pytest.mark.parametrize("command", [
    "gh pr edit 276 --body-file b.md && gh pr merge 276 --squash",
    "gh pr edit 276 --body-file b.md; gh pr merge 276 --squash",   # PowerShell 5.1
    "gh pr edit 276 --body-file b.md\ngh pr merge 276 --squash",
])
def test_every_command_in_a_chain_is_found_with_its_own_args(command):
    assert [(v, a) for v, a, _ in gate._pr_commands(command)] == [
        ("edit", ["276", "--body-file", "b.md"]), ("merge", ["276", "--squash"])]


def _run(monkeypatch, capsys, command, *, body="", commits=(), open_issues=(261,),
         gh_fails=False, title="t", branch="b", tool="Bash", calls=None, cwd=None):
    def fake_gh(args, cwd=None):
        if calls is not None:
            calls.append((args, cwd))
        if gh_fails:
            raise RuntimeError("HTTP 502")
        if args[:2] == ["pr", "view"]:
            return json.dumps({"number": 264, "title": title, "body": body,
                               "headRefName": branch, "commits": [
                {"messageHeadline": c, "messageBody": ""} for c in commits]})
        return "\n".join(str(n) for n in open_issues)
    monkeypatch.setattr(gate, "_gh", fake_gh)
    payload = {"tool_name": tool, "tool_input": {"command": command}}
    if cwd:
        payload["cwd"] = cwd
    monkeypatch.setattr(gate.sys, "stdin",
                        io.TextIOWrapper(io.BytesIO(json.dumps(payload).encode())))
    code = gate.main()
    return code, capsys.readouterr().err


def test_a_merge_checks_the_merge_commit_github_will_write(monkeypatch, capsys):
    """The real #261 strike: a clean body, but the branch name ends in "fixes"
    and the title starts with the number."""
    code, err = _run(monkeypatch, capsys, "gh pr merge 264 --merge", body="clean",
                     title="#261: small fixes", branch="claude/261-small-fixes")
    assert code == 2 and "#261" in err


def test_a_merge_reads_the_pr_from_github_and_blocks(monkeypatch, capsys):
    code, err = _run(monkeypatch, capsys, "gh pr merge 264 --merge",
                     body="The small fixes from #261.")
    assert code == 2 and "#261" in err


def test_a_merge_also_scans_every_commit_message(monkeypatch, capsys):
    code, _ = _run(monkeypatch, capsys, "gh pr merge 264 --merge",
                   body="clean", commits=["refactor: the fix #261 asked for"])
    assert code == 2


def test_a_clean_merge_passes(monkeypatch, capsys):
    code, _ = _run(monkeypatch, capsys, "gh pr merge 264 --merge",
                   body="Closes #261\n\nEverything else (#46) is history.")
    assert code == 0


def test_a_gate_that_cannot_read_the_pr_blocks(monkeypatch, capsys):
    code, err = _run(monkeypatch, capsys, "gh pr merge 264 --merge", gh_fails=True)
    assert code == 2 and "HTTP 502" in err


def test_create_scans_the_body_file(monkeypatch, capsys, tmp_path):
    body = tmp_path / "body.md"
    body.write_text("Small fixes from #261.", encoding="utf-8")
    code, _ = _run(monkeypatch, capsys, f"gh pr create --title t --body-file {body.as_posix()}")
    assert code == 2


def test_a_non_shell_tool_is_ignored(monkeypatch, capsys):
    payload = {"tool_name": "Edit", "tool_input": {"file_path": "x"}}
    monkeypatch.setattr(gate.sys, "stdin",
                        io.TextIOWrapper(io.BytesIO(json.dumps(payload).encode())))
    assert gate.main() == 0


def test_a_merge_typed_in_powershell_is_checked(monkeypatch, capsys):
    """PowerShell is the primary shell here and gh is on its PATH."""
    code, err = _run(monkeypatch, capsys, "gh pr merge 264 --merge",
                     body="The small fixes from #261.", tool="PowerShell")
    assert code == 2 and "#261" in err


def test_settings_route_both_shells_to_the_gate():
    """The script accepting PowerShell is half of it; the matcher is the other."""
    import re
    settings = json.loads((_PATH.parent.parent / "settings.json").read_text(encoding="utf-8"))
    matchers = [entry["matcher"] for entry in settings["hooks"]["PreToolUse"]
                if any("closing_keyword_gate.py" in h["command"] for h in entry["hooks"])]
    assert matchers, "the gate is not registered as a PreToolUse hook"
    for tool in ("Bash", "PowerShell"):
        assert any(re.fullmatch(m, tool) for m in matchers), f"{tool} never reaches the gate"


def test_a_merge_chained_after_an_edit_is_checked(monkeypatch, capsys, tmp_path):
    """The edit's own body is clean; the merge's commits are not."""
    (tmp_path / "b.md").write_text("Clean body.", encoding="utf-8")
    code, err = _run(monkeypatch, capsys,
                     f"gh pr edit 264 --body-file {(tmp_path / 'b.md').as_posix()} "
                     "&& gh pr merge 264 --squash",
                     body="clean", commits=["refactor: the fix #261 asked for"])
    assert code == 2 and "#261" in err


@pytest.mark.parametrize("body", [
    'Adds the "dry run" default.\nThe small fixes from #261.',   # shlex stops at the quote
    'Adds a "quote.\nThis fixes #261.',                          # odd quote: shlex raises
])
def test_a_heredoc_body_is_scanned_past_its_first_quote(monkeypatch, capsys, body):
    """Claude Code's usual idiom. shlex ends the --body argument at the first
    double quote inside the text, so everything after it went unscanned."""
    command = f"gh pr create --title t --body \"$(cat <<'EOF'\n{body}\nEOF\n)\""
    code, err = _run(monkeypatch, capsys, command)
    assert code == 2 and "#261" in err


def test_a_deliberate_close_in_a_heredoc_body_passes(monkeypatch, capsys):
    command = ("gh pr create --title t --body \"$(cat <<'EOF'\n"
               'Adds the "dry run" default.\n\nCloses #261\nEOF\n)"')
    code, _ = _run(monkeypatch, capsys, command)
    assert code == 0


def test_a_body_file_named_through_a_shell_variable_is_read(monkeypatch, capsys, tmp_path):
    """The gate's first live run blocked `SP="..."; gh pr create --body-file
    "$SP/body.md"`: it sees the command before the shell expands it."""
    (tmp_path / "body.md").write_text("Small fixes from #261.", encoding="utf-8")
    sp = tmp_path.as_posix()
    code, _ = _run(monkeypatch, capsys,
                   f'SP="{sp}"\ngh pr create --title t --body-file "$SP/body.md"')
    assert code == 2, "the body behind $SP was not read, or not flagged"


def test_an_unresolvable_path_still_fails_closed(monkeypatch, capsys):
    monkeypatch.delenv("NOPE_UNSET", raising=False)
    code, err = _run(monkeypatch, capsys,
                     'gh pr create --title t --body-file "$NOPE_UNSET/body.md"')
    assert code == 2 and "could not check" in err


# ── every reference form GitHub honours, and the repo it lives in ──────────

THIS = "owner/app"


@pytest.mark.parametrize("text,expected", [
    ("This fixes owner/app#261 for good.", [261]),   # this repo, qualified
    ("It fixes https://github.com/owner/app/issues/261 too", [261]),
    ("the fix in owner/other#2913 lands", ["owner/other#2913"]),
    ("Closes owner/other#2913", []),                # deliberate, own line
    ("This fixes owner/app#999 too", []),        # this repo, closed
])
def test_qualified_and_url_references_are_judged(text, expected):
    """`#N` alone was matched, so a qualified reference or an issue link closed
    the issue past the gate, and another repo's issue was never considered.
    GitHub closes those on merge too."""
    assert [n for n, _ in gate.risky_references(text, OPEN, THIS)] == expected


def test_a_cd_into_another_repo_is_checked_there(monkeypatch, capsys, tmp_path):
    """gh resolves the repo from its working directory. Run from here, it read
    THIS repo's PR #46 and open issues for another repo's merge."""
    calls = []
    _run(monkeypatch, capsys, "cd ../other-repo && gh pr merge 46 --squash",
         body="clean", calls=calls, cwd=str(tmp_path / "app"))
    assert calls and all(c == str(tmp_path / "other-repo") for _, c in calls)


def test_a_pr_url_names_the_repo_its_issues_come_from(monkeypatch, capsys):
    calls = []
    _run(monkeypatch, capsys,
         "gh pr merge https://github.com/owner/other-repo/pull/46 --squash",
         body="clean", calls=calls)
    issue_list = next(a for a, _ in calls if a[:2] == ["issue", "list"])
    assert ["-R", "owner/other-repo"] == issue_list[2:4]
