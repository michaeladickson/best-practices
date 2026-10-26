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
import os
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


@pytest.mark.parametrize("text,code", [("Small fixes from #261.", 2), ("Clean body.", 0)])
def test_a_quoted_body_file_is_read_when_the_command_does_not_shlex(monkeypatch, capsys,
                                                                     tmp_path, text, code):
    """An apostrophe in a heredoc written earlier in the same command makes
    shlex raise, and the whitespace fallback kept the quotes around
    "$SP/body.md", so a correct `gh pr create` failed closed on a path with
    literal quotes in it (2026-10-26)."""
    (tmp_path / "body.md").write_text(text, encoding="utf-8")
    command = (f'SP="{tmp_path.as_posix()}"\n'
               "cat > $SP/notes.md <<'EOF'\nthe repo's own copy\nEOF\n"
               'gh pr create --title t --body-file "$SP/body.md"')
    got, err = _run(monkeypatch, capsys, command)
    assert "could not check" not in err
    assert got == code


@pytest.mark.parametrize("text,code", [("Small fixes from #261.", 2), ("Clean body.", 0)])
def test_a_powershell_backslash_path_keeps_its_backslashes(monkeypatch, capsys, tmp_path,
                                                            text, code):
    """POSIX shlex read `C:\\Users\\...\\b.md` as `C:Users...b.md`, so every
    PowerShell create with a Windows path failed closed (2026-10-26)."""
    body = tmp_path / "body.md"
    body.write_text(text, encoding="utf-8")
    win = str(body).replace("/", "\\")
    assert gate._pr_commands(f"gh pr create --body-file {win}", "PowerShell")[0][1] == [
        "--body-file", win]
    if os.name == "nt":                   # only there is the backslash path real
        got, err = _run(monkeypatch, capsys, f"gh pr create --title t --body-file {win}",
                        tool="PowerShell")
        assert "could not check" not in err
        assert got == code


def test_powershell_tokens_keep_hash_numbers():
    """shlex.shlex treats `#` as a comment by default; shlex.split does not."""
    assert gate._pr_commands("gh pr edit 12 --title '#261 stays open'", "PowerShell")[0][1] == [
        "12", "--title", "#261 stays open"]


@pytest.mark.parametrize("path,expected", [
    ("/c/Users/m/b.md", "C:/Users/m/b.md"),
    ("/d", "D:/"),
    ("/tmp/b.md", "/tmp/b.md"),                  # not a drive letter
    ("C:/Users/m/b.md", "C:/Users/m/b.md"),
])
def test_an_msys_path_is_opened_as_windows_reads_it(path, expected):
    """Git Bash prints `/c/Users/...`; Windows Python read that as C:\\c\\Users."""
    assert gate._local_path(path, nt=True) == expected
    assert gate._local_path(path, nt=False) == path


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


# ── findings from the first install PRs' reviews (2026-10-26) ─────────────

@pytest.mark.parametrize("command,target", [
    ("gh pr merge -R a/b 264 --squash", "264"),
    ("gh pr merge --subject x 264", "264"),
    ("gh pr merge -m 264", "264"),                  # -m is --merge, no value
    ("gh pr edit -m v1 12 --title t", "12"),        # -m is --milestone on edit
    ("gh pr merge --squash", ""),                   # the current branch's PR
])
def test_the_pr_is_the_first_argument_that_is_not_a_flag_value(command, target):
    """`gh pr merge -R owner/app 264` read `owner/app` as the PR and blocked."""
    verb, args, _ = gate._pr_commands(command)[0]
    assert gate._target(verb, args) == target


def test_a_merge_with_the_repo_flag_first_reads_the_right_pr(monkeypatch, capsys):
    calls = []
    code, _ = _run(monkeypatch, capsys, "gh pr merge -R a/b 264 --squash",
                   body="clean", calls=calls)
    view = next(a for a, _ in calls if a[:2] == ["pr", "view"])
    assert view[2] == "264" and code == 0


@pytest.mark.parametrize("text,code", [("Small fixes from #261.", 2), ("Clean body.", 0)])
def test_a_body_from_a_heredoc_on_stdin_is_scanned(monkeypatch, capsys, text, code):
    """`--body-file -` opened a file named "-" and failed closed on every such
    create; the heredoc it reads is in the raw command the gate scans."""
    command = f"gh pr create --title t --body-file - <<'EOF'\n{text}\nEOF"
    got, err = _run(monkeypatch, capsys, command)
    assert "could not check" not in err and got == code


def test_a_body_piped_on_stdin_fails_closed(monkeypatch, capsys):
    code, err = _run(monkeypatch, capsys, "cat b.md | gh pr create --title t --body-file -")
    assert code == 2 and "stdin" in err


def test_an_open_issue_list_at_the_limit_fails_closed(monkeypatch, capsys):
    """gh lists newest first; a full page drops the oldest open issues, and a
    close aimed at one of them passed as clean."""
    code, err = _run(monkeypatch, capsys, "gh pr create --title t --body x",
                     open_issues=range(1, gate._ISSUE_LIMIT + 1))
    assert code == 2 and "incomplete" in err


@pytest.mark.parametrize("command,tool", [
    ("GH_REPO=o/r gh pr merge 46 --squash", "Bash"),
    ('$env:GH_REPO = "o/r"; gh pr merge 46 --squash', "PowerShell"),
])
def test_gh_repo_points_the_check_at_that_repo(monkeypatch, capsys, command, tool):
    calls = []
    _run(monkeypatch, capsys, command, body="clean", calls=calls, tool=tool)
    issue_list = next(a for a, _ in calls if a[:2] == ["issue", "list"])
    assert issue_list[2:4] == ["-R", "o/r"]


def test_a_merge_fed_by_xargs_fails_closed(monkeypatch, capsys):
    """gh reads the PR from stdin, so the gate would check the branch's PR."""
    code, err = _run(monkeypatch, capsys, "echo 1 2 | xargs -n1 gh pr merge --squash")
    assert code == 2 and "xargs" in err


@pytest.mark.parametrize("command", [
    "python3 - <<'PY'\n# then gh pr merge -R owner/app 264\nprint(1)\nPY",
    "$s = @'\nrun gh pr merge -R owner/app 264 next\n'@\nWrite-Output $s",
    "$s = @'\nrun gh pr merge 264 next\n'@ | Out-File x.md",
])
def test_prose_inside_a_heredoc_is_not_a_command(command):
    """The live gate blocked a patch script whose comment mentioned a merge."""
    assert gate._pr_commands(command) == []


def test_a_command_after_a_heredoc_is_still_found():
    command = "cat > b.md <<'EOF'\nthe gh pr merge 1 idea\nEOF\ngh pr merge 264 --squash"
    assert [(v, a) for v, a, _ in gate._pr_commands(command)] == [("merge", ["264", "--squash"])]


# ── the re-review of those fixes (2026-10-26) ─────────────────────────────

@pytest.mark.parametrize("before", [
    "x=$((n<<1))",                          # a shift, not a heredoc
    'jq . <<< "text"',                      # a here-string, not a heredoc
    'echo "a << b"',                        # quoted text; its "terminator" never comes
    'git config user.email "bot@"',         # ends in @", not a PowerShell here-string
])
def test_a_false_heredoc_opener_does_not_hide_a_later_merge(before):
    """Each of these opened a heredoc that never closed, so every later line
    was dropped and the merge after it passed unchecked."""
    command = before + "\ngh pr merge 264 --squash"
    assert [v for v, _, _ in gate._pr_commands(command)] == ["merge"]


def test_a_false_opener_still_lets_the_merge_be_checked(monkeypatch, capsys):
    code, err = _run(monkeypatch, capsys, "x=$((n<<1))\ngh pr merge 264 --squash",
                     body="The small fixes from #261.")
    assert code == 2 and "#261" in err


def test_a_gh_repo_prefix_binds_only_its_own_command(monkeypatch, capsys):
    """`GH_REPO=o/r gh pr view 5 && gh pr merge 46` merges THIS repo's #46."""
    calls = []
    _run(monkeypatch, capsys, "GH_REPO=o/r gh pr view 5 && gh pr merge 46 --squash",
         body="clean", calls=calls)
    issue_list = next(a for a, _ in calls if a[:2] == ["issue", "list"])
    assert "-R" not in issue_list


def test_export_gh_repo_applies_to_later_commands(monkeypatch, capsys):
    calls = []
    _run(monkeypatch, capsys, "export GH_REPO=o/r && gh pr merge 46 --squash",
         body="clean", calls=calls)
    issue_list = next(a for a, _ in calls if a[:2] == ["issue", "list"])
    assert issue_list[2:4] == ["-R", "o/r"]


def test_gh_repo_in_a_body_is_prose_not_a_setting(monkeypatch, capsys):
    """A PR body describing `GH_REPO=owner/app` redirected the open-issue list,
    so a close of one of this repo's issues passed."""
    calls = []
    command = ("cat > b.md <<'EOF'\nexport GH_REPO=owner/app is the trick\nEOF\n"
               "gh pr merge 46 --squash")
    _run(monkeypatch, capsys, command, body="clean", calls=calls)
    issue_list = next(a for a, _ in calls if a[:2] == ["issue", "list"])
    assert "-R" not in issue_list


def test_a_piped_body_fails_closed_even_with_a_heredoc_elsewhere(monkeypatch, capsys):
    command = "cat > n.md <<'EOF'\nnotes\nEOF\ncat b.md | gh pr create --title t --body-file -"
    code, err = _run(monkeypatch, capsys, command)
    assert code == 2 and "stdin" in err


def test_a_powershell_here_string_piped_into_create_is_scanned(monkeypatch, capsys):
    command = "@'\nSmall fixes from #261.\n'@ | gh pr create --title t --body-file -"
    code, err = _run(monkeypatch, capsys, command, tool="PowerShell")
    assert code == 2 and "#261" in err


def test_xargs_in_a_body_is_prose(monkeypatch, capsys):
    command = ("cat > b.md <<'EOF'\nnever run xargs gh pr merge\nEOF\n"
               "gh pr create --title t --body-file b.md")
    monkeypatch.setattr(gate, "text_to_scan", lambda *a, **k: "clean")
    code, err = _run(monkeypatch, capsys, command)
    assert code == 0 and "xargs" not in err


def test_gh_host_fails_closed(monkeypatch, capsys):
    code, err = _run(monkeypatch, capsys, "GH_HOST=ghe.example.com gh pr merge 46")
    assert code == 2 and "GH_HOST" in err


# ── the command-center re-review of those fixes (2026-10-26) ──────────────

def test_a_heredoc_for_a_later_command_does_not_vouch_for_a_piped_body(monkeypatch, capsys):
    """The heredoc after `&&` belongs to cat, and gh reads b.md on stdin."""
    command = ("cat b.md | gh pr edit 5 --body-file - && cat > n.md <<'EOF'\n"
               "notes\nEOF")
    code, err = _run(monkeypatch, capsys, command)
    assert code == 2 and "stdin" in err


@pytest.mark.parametrize("text,code", [("Small fixes from #261.", 2), ("Clean body.", 0)])
def test_a_heredoc_piped_into_create_is_scanned(monkeypatch, capsys, text, code):
    """`cat <<'EOF' | gh pr create --body-file -` is a common correct form."""
    command = f"cat <<'EOF' | gh pr create --title t --body-file -\n{text}\nEOF"
    got, err = _run(monkeypatch, capsys, command)
    assert "could not check" not in err and got == code


def test_gh_repo_on_the_line_before_is_not_a_prefix(monkeypatch, capsys):
    """Not exported, so gh merges in the cwd repo; shlex had dropped the newline."""
    calls = []
    _run(monkeypatch, capsys, "GH_REPO=o/r\ngh pr merge 46 --squash", body="clean", calls=calls)
    issue_list = next(a for a, _ in calls if a[:2] == ["issue", "list"])
    assert "-R" not in issue_list


def test_an_explicit_repo_flag_wins_over_a_gh_repo_prefix(monkeypatch, capsys):
    calls = []
    _run(monkeypatch, capsys, "GH_REPO=a/b gh pr merge 46 -R c/d", body="clean", calls=calls)
    issue_list = next(a for a, _ in calls if a[:2] == ["issue", "list"])
    assert issue_list[2:4] == ["-R", "c/d"]


def test_a_heredoc_with_no_space_is_still_a_heredoc():
    command = "cat<<EOF > b.md\nthen gh pr merge 1 here\nEOF\ngh pr merge 264 --squash"
    assert [(v, a) for v, a, _ in gate._pr_commands(command)] == [("merge", ["264", "--squash"])]
