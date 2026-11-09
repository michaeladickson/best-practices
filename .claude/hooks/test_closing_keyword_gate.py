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
import re
import shlex
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


def test_a_gh_repo_prefix_points_the_check_at_that_repo(monkeypatch, capsys):
    calls = []
    _run(monkeypatch, capsys, "GH_REPO=o/r gh pr merge 46 --squash", body="clean", calls=calls)
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


def test_an_explicit_repo_flag_wins_over_a_gh_repo_prefix(monkeypatch, capsys):
    calls = []
    _run(monkeypatch, capsys, "GH_REPO=a/b gh pr merge 46 -R c/d", body="clean", calls=calls)
    issue_list = next(a for a, _ in calls if a[:2] == ["issue", "list"])
    assert issue_list[2:4] == ["-R", "c/d"]


def test_a_heredoc_with_no_space_is_still_a_heredoc():
    command = "cat<<EOF > b.md\nthen gh pr merge 1 here\nEOF\ngh pr merge 264 --squash"
    assert [(v, a) for v, a, _ in gate._pr_commands(command)] == [("merge", ["264", "--squash"])]


# ── #69: fail closed on what the gate does not model (2026-11-08) ─────────
# Four review rounds on 2026-10-26 each found a construct the hand-written
# parsing misread. These block with the reason instead of modelling one more
# form, and each case passed unchecked on 384a24d.

@pytest.mark.parametrize("command", [
    # The create's heredoc vouched for the edit's piped body (command-center PR 760).
    "cat b.md | gh pr edit 5 --body-file - && gh pr create --title t --body-file - <<'EOF'\n"
    "clean\nEOF",
    # One reader, but the heredoc belongs to a command that does not read stdin.
    "cat b.md | gh pr edit 5 --body-file - && gh pr merge 6 <<'EOF'\nclean\nEOF",
])
def test_a_stdin_body_the_gate_cannot_attribute_fails_closed(monkeypatch, capsys, command):
    code, err = _run(monkeypatch, capsys, command, body="clean")
    assert code == 2 and "--body-file -" in err


def test_one_stdin_reader_with_its_own_heredoc_beside_other_edits_passes(monkeypatch, capsys):
    """A crumbl-ops session's real form: two label edits, then a body edit."""
    command = ("gh pr edit 5 --add-label x; gh pr edit 5 --remove-label y; "
               "gh pr edit 6 --body-file - <<'EOF' >/dev/null\nClean body.\nEOF")
    code, err = _run(monkeypatch, capsys, command)
    assert code == 0, err


@pytest.mark.parametrize("command,tool", [
    ("GH_REPO=o/r; export GH_REPO && gh pr merge 46 --squash", "Bash"),   # CC PR 760
    ("declare -x GH_REPO=o/r && gh pr merge 46 --squash", "Bash"),
    ("set -a; GH_REPO=o/r; gh pr merge 46 --squash", "Bash"),
    ("GH_REPO=o/r A=1; gh pr merge 46 --squash", "Bash"),
    ("gh pr merge 46 --squash && export GH_REPO=o/r", "Bash"),            # WM PR 289
    ("unset GH_REPO && gh pr merge 46 --squash", "Bash"),
    ("export GH_REPO=o/r && gh pr merge 46 --squash", "Bash"),
    ("GH_REPO=o/r\ngh pr merge 46 --squash", "Bash"),   # updates GH_REPO if already exported
    # #82: the same value as a real prefix elsewhere no longer vouches for it.
    ("GH_REPO=o/r gh pr view 1 && GH_REPO=o/r\ngh pr merge 46 --squash", "Bash"),
    ('$env:GH_REPO = "o/r"; gh pr merge 46 --squash', "PowerShell"),
])
def test_gh_repo_other_than_a_prefix_fails_closed(monkeypatch, capsys, command, tool):
    calls = []
    code, err = _run(monkeypatch, capsys, command, body="clean", calls=calls, tool=tool)
    assert code == 2 and "GH_REPO" in err and calls == []


@pytest.mark.parametrize("command", [
    "gh pr create --title t --body 'set GH_REPO=o/r first'",
    "git commit -m 'GH_REPO notes' && gh pr create --title t --body x",
    "GH_REPO=o/r gh pr view 5 && gh pr create --title t --body x",
])
def test_gh_repo_as_prose_or_a_one_command_prefix_passes(monkeypatch, capsys, command):
    code, err = _run(monkeypatch, capsys, command, open_issues=())
    assert code == 0, err


@pytest.mark.parametrize("command,tool", [
    ("bash <<'EOF'\ngh pr merge 264 --squash\nEOF", "Bash"),              # WM PR 289
    ("sh -s <<EOF\ngh pr merge 264 --squash\nEOF", "Bash"),
    ("ssh host <<EOF\ncd app && gh pr merge 264\nEOF", "Bash"),
    ("cat <<'EOF' | bash\ngh pr merge 264 --squash\nEOF", "Bash"),
    ("bash -c \"$(cat <<'EOF'\ngh pr merge 264 --squash\nEOF\n)\"", "Bash"),
    ("bash -c 'gh pr merge 264 --squash'", "Bash"),
    # A crumbl-ops session merged this way 7 times in 90 days, every one unchecked.
    ('wsl -- bash -c "cd /mnt/c/x && gh pr merge 2552 --squash 2>&1 | tail -5"', "Bash"),
    ("/usr/bin/env bash -c 'gh pr merge 264 --squash'", "Bash"),
    ("echo 'gh pr merge 264 --squash' | sh", "Bash"),
    ('eval "gh pr merge 264 --squash"', "Bash"),
    ("Invoke-Expression @'\ngh pr merge 264 --squash\n'@", "PowerShell"),
    ("@'\ngh pr merge 264 --squash\n'@ | iex", "PowerShell"),
    ('Invoke-Expression "gh pr merge 264 --squash"', "PowerShell"),
])
def test_a_pr_command_run_by_another_shell_fails_closed(monkeypatch, capsys, command, tool):
    calls = []
    code, err = _run(monkeypatch, capsys, command, body="clean", calls=calls, tool=tool)
    assert code == 2 and "cannot read" in err and calls == []


@pytest.mark.parametrize("command", [
    "python3 - <<'PY'\n# then gh pr merge -R owner/app 264\nprint(1)\nPY",   # a patch script
    "cat > b.md <<'EOF'\nthen gh pr merge 264 --squash\nEOF",
    "cat > deploy.sh <<'EOF'\ngh pr merge 264 --squash\nEOF",
    "gh pr create --title 'bash note' --body-file - <<'EOF'\nrun gh pr merge 5 after\nEOF",
    "gh issue create --title 'bash gate' --body-file - <<'EOF'\nrun gh pr merge 5\nEOF",
    # A crumbl-ops session's real form: the heredoc is cat's, not bash's.
    "wsl -- bash -c \"cd /mnt/c/x && pytest -q | tail -1\" && cat > b.md <<'EOF'\n"
    "`gh pr create --label` fires opened and labeled together.\nEOF\n"
    "gh pr create --title t --body x",
    "gh pr create --title t --body 'then gh pr merge 5'",
    'grep -rn "gh pr merge" .claude/skills',
    "wsl -- bash -c 'grep -o \"gh pr create[^ ]*\" t.jsonl | sort -u | head -20'",
    'grep -rn "gh pr merge" . | head -5 && bash scripts/check.sh',
    'Select-String -Pattern "gh pr merge" -Path *.md',
    # #82: a shell word that is not the command anything runs.
    'wsl -- grep -rn "gh pr merge" .claude/skills',
    'grep -rn "gh pr merge" scripts/ | grep -v bash',
    'wsl -- git log --grep="gh pr create"',
    'bash -n scripts/check.sh\nrg "gh pr merge 1" .claude',
    "bash -c 'echo hi' | grep 'gh pr merge'",
    "wsl -d Ubuntu -- grep -c 'gh pr merge' t.jsonl",
    "echo bash -c 'gh pr merge 264 --squash'",
    "grep -rn 'gh pr merge 1' . | grep -v -e bash -e sh",
])
def test_a_pr_command_written_as_prose_passes(monkeypatch, capsys, command):
    code, err = _run(monkeypatch, capsys, command, open_issues=())
    assert code == 0, err


# ── #82: the reviews of the #69 copies (2026-11-09) ───────────────────────
# A shell counts only as a command word, found in words that keep the
# operators, newlines and quotes shlex.split drops. 30 of the 56 cases added
# for #82 have the wrong result on 79acb4ca; the rest passed there and guard
# what reading command words must keep, among them forms the first such
# reading lost (a pipe ending a line, a shell after an unlisted wrapper, a
# pipe into one).

@pytest.mark.parametrize("command", [
    "echo 'gh pr merge 264 --squash' |bash",
    "cd x&&bash -c 'gh pr merge 264 --squash'",
    "(bash -c 'gh pr merge 264 --squash')",
    "x=$(bash -c 'gh pr merge 264 --squash')",
    "x=`bash -c 'gh pr merge 264 --squash'`",
    "(echo 'gh pr merge 264 --squash') | bash",
    "{ echo 'gh pr merge 264 --squash'; } | bash",
    "echo 'gh pr merge 264 --squash' | wsl",
    "wsl -d Ubuntu -- bash -c 'gh pr merge 264 --squash'",
    "timeout 60 bash -c 'gh pr merge 264 --squash'",
    "bash -c \"bash -c 'gh pr merge 264 --squash'\"",
    "gh pr edit 5 --add-label x | bash <<'EOF'\ngh pr merge 264 --squash\nEOF",
    "ssh host 'cd app && sh' <<'EOF'\ngh pr merge 264 --squash\nEOF",
    "ssh host \"cd /repo; bash\" <<EOF\ngh pr merge 264 --squash\nEOF",
    # The reviews of the #82 copies: forms 79acb4ca blocked that its first
    # command-word reading passed. A newline after `|` continues the pipeline,
    "echo 'gh pr merge 264 --squash' |\nbash",
    "echo 'gh pr merge 264 --squash' | \n  bash",
    "(\n  echo 'gh pr merge 264 --squash'\n) | bash",
    # and a shell after a wrapper the gate does not list still runs.
    "setsid bash -c 'gh pr merge 264 --squash'",
    "flock /tmp/l bash -c 'gh pr merge 264 --squash'",
    "watch -n1 bash -c 'gh pr merge 264 --squash'",
    "wsl ~ -e bash -c 'gh pr merge 264 --squash'",
    "find . -maxdepth 0 -exec sh -c 'gh pr merge 264 --squash' \\;",
    "setsid bash <<'EOF'\ngh pr merge 264 --squash\nEOF",
    # A pipe feeds a shell behind a wrapper or inside a group (wealth-mgmt PR 302).
    "echo 'gh pr merge 264 --squash' | setsid bash",
    "echo 'gh pr merge 264 --squash' | flock /tmp/l bash",
    "echo 'gh pr merge 264 --squash' | ( bash )",
    "echo 'gh pr merge 264 --squash' |(bash)",
    "echo 'gh pr merge 264 --squash' | { bash; }",
    # A command kept in a variable and run by a shell (command-center PR 843).
    "CMD='gh pr merge 264 --squash'\neval \"$CMD\"",
    "CMD='gh pr merge 264 --squash' bash -c 'eval \"$CMD\"'",
    "cmd=\"gh pr merge 264 --squash\"; eval \"$cmd\"",
])
def test_a_shell_glued_to_punctuation_or_behind_a_quote_fails_closed(monkeypatch, capsys,
                                                                     command):
    calls = []
    code, err = _run(monkeypatch, capsys, command, body="clean", calls=calls)
    assert code == 2 and "cannot read" in err and calls == []


@pytest.mark.parametrize("command", [
    "cd ~/gh_repos/x && gh pr merge 264 --squash",
    "git add notes/gh_repo.md && gh pr merge 264 --squash",
])
def test_a_path_that_contains_gh_repo_is_not_the_variable(monkeypatch, capsys, command):
    code, err = _run(monkeypatch, capsys, command, body="clean")
    assert code == 0, err


@pytest.mark.parametrize("command,verbs", [
    ("cd x&&gh pr merge 5", ["merge"]),
    ("cd x && \\\ngh pr merge 5", ["merge"]),          # shlex reads `\ngh`
    ("echo $(gh pr merge 5)", ["merge"]),
    ("/usr/bin/gh pr edit 5 --add-label x", ["edit"]),
    ("git log --grep=gh pr create", []),
    ("echo high pr merge", []),
    ("echo don't && bash -c 'gh pr merge 264 --squash'", ["merge"]),   # fallback keeps 'gh
    ('out="$(gh pr merge 264 --squash 2>&1)"; echo "$out"', ["merge"]),
    # A Markdown code span in a body is not a substitution the gate reads,
    ("gh pr create --title t --body \"Run \\`gh pr merge 5\\` after\"", ["create"]),
    # nor is a commit message, nor a `$(` that never closes (crumbl-ops PR 3842).
    ("git commit -m 'read \"$(gh pr merge 264 2>&1)\" captures'", []),
    ("grep -F '$(gh pr merge' notes.md", []),
])
def test_gh_is_a_command_word_not_a_suffix(command, verbs):
    assert [v for v, _, _ in gate._pr_commands(command)] == verbs


@pytest.mark.parametrize("text,code", [("Small fixes from #261.", 2), ("Clean body.", 0)])
def test_a_merge_captured_in_a_quoted_substitution_is_checked(monkeypatch, capsys, text, code):
    """Before #82 this merge was never found, so it ran with nothing checked."""
    calls = []
    code_, err = _run(monkeypatch, capsys, 'out="$(gh pr merge 264 --squash 2>&1)"',
                      body=text, calls=calls)
    assert code_ == code and calls, err


def test_a_heredoc_delimiter_named_like_a_shell_is_not_a_shell(monkeypatch, capsys):
    code, err = _run(monkeypatch, capsys, "cat > notes.txt <<SH\nthen gh pr merge 5\nSH",
                     open_issues=())
    assert code == 0, err


# ── wealth-mgmt #284 M1 and #294: commands the parser misread (2026-11-09) ──
# Each was reproduced on the #82 copy: the merge ran unchecked, or was checked
# against this repo while gh merged another.

def _issue_list(calls):
    return next(a for a, _ in calls if a[:2] == ["issue", "list"])


def _repo_of(gh_args):
    """The `-R` value in one of the gate's own gh calls."""
    return gh_args[gh_args.index("-R") + 1] if "-R" in gh_args else None


def test_an_ordinary_merge_is_checked_exactly_as_before(monkeypatch, capsys):
    calls = []
    code, _ = _run(monkeypatch, capsys, "gh pr merge 46 --squash", body="clean", calls=calls)
    assert code == 0
    assert [a for a, _ in calls] == [
        ["pr", "view", "46", "--json", "number,title,body,commits,headRefName"],
        ["issue", "list", "--state", "open", "--limit", str(gate._ISSUE_LIMIT),
         "--json", "number", "--jq", ".[].number"]]


@pytest.mark.parametrize("command", [
    "gh pr -R owner/other merge 46 --squash",           # the #284 M1 reproduction
    "gh pr --repo owner/other merge 46 --squash",
    "gh pr --repo=owner/other merge 46 --squash",
    "gh pr -Rowner/other merge 46 --squash",
    "gh pr merge 46 -Rowner/other --squash",            # attached value after the verb
])
def test_a_repo_flag_before_the_verb_is_parsed_and_checked_there(monkeypatch, capsys, command):
    """`-R` is a flag of `gh pr` itself, so it may precede the verb. The parser
    read the verb only right after `pr`, found nothing, and the merge ran
    unchecked; an attached `-Rowner/other` was dropped, and the merge was
    checked against this repo."""
    calls = []
    code, _ = _run(monkeypatch, capsys, command, body="clean", calls=calls)
    view = next(a for a, _ in calls if a[:2] == ["pr", "view"])
    assert code == 0 and view[2] == "46" and _repo_of(view) == "owner/other"
    assert _issue_list(calls)[2:4] == ["-R", "owner/other"]


def test_a_gh_repo_prefix_continued_onto_the_next_line_binds(monkeypatch, capsys):
    """`\\` + newline joins the lines, so the prefix is the merge's: the gate
    checked this repo's #46 while gh merged o/r's (#294)."""
    calls = []
    code, err = _run(monkeypatch, capsys, "GH_REPO=o/r \\\n  gh pr merge 46 --squash",
                     body="clean", calls=calls)
    assert code == 0 and _issue_list(calls)[2:4] == ["-R", "o/r"], err


def test_gh_pr_new_is_checked_as_a_create(monkeypatch, capsys):
    """`gh pr new` is gh's alias for create, and it was not a verb the gate knew."""
    code, err = _run(monkeypatch, capsys, "gh pr new --title t --body 'Small fixes from #261.'")
    assert code == 2 and "#261" in err


@pytest.mark.parametrize("command,code,why", [
    ("bash -c 'gh pr -R o/r merge 46 --squash'", 2, "cannot read"),
    ("bash -c 'gh pr new --title t --body x'", 2, "cannot read"),
    ("echo 46 | xargs gh pr -R o/r merge --squash", 2, "xargs"),
    ("gh pr new --title t --body-file - <<'EOF'\nClean body.\nEOF", 0, ""),
])
def test_every_check_reads_the_verb_the_parser_reads(monkeypatch, capsys, command, code, why):
    """The shell and xargs checks read the verb with the parser and the stdin
    check by pattern; each must know `-R` before it and `new`."""
    got, err = _run(monkeypatch, capsys, command, open_issues=())
    assert got == code and why in err, err


@pytest.mark.parametrize("command,tool", [
    ("gh pr view 12", "Bash"),
    ('gh pr list --search "merge"', "Bash"),
    ('gh pr comment 5 --body "will merge after CI"', "Bash"),
    ("gh pr -R o/r view 12", "Bash"),
    ('gh issue create --title "pr merge flow" --body x', "Bash"),
    ("git log --oneline | grep pr", "Bash"),
    ("git checkout -b gh-pr-merge-fix", "Bash"),
    ("echo gh && echo pr", "Bash"),
    ("gh pr checks 5; git merge main", "Bash"),
    ("gh pr view 5 --json title | Select-String merge", "PowerShell"),
])
def test_a_command_that_only_mentions_gh_or_pr_is_not_blocked(monkeypatch, capsys,
                                                              command, tool):
    calls = []
    code, err = _run(monkeypatch, capsys, command, calls=calls, tool=tool)
    assert code == 0 and err == "" and calls == []


# ── a repeated -R (wealth-mgmt #307 post-merge review, 2026-11-09) ─────────
# gh keeps the last of a repeated flag; the gate read the first, so it checked
# one repo's PR and open issues while gh merged another's.

@pytest.mark.parametrize("command", [
    "gh pr merge 46 -R a/b -R c/d --squash",
    "gh pr merge 46 --repo a/b --repo c/d",
    "gh pr merge 46 --repo=a/b -R c/d",
    "gh pr merge 46 -Ra/b -R c/d",
    "gh pr merge 46 -R=a/b --repo=c/d",
    "gh pr -R a/b merge 46 -R c/d",                     # the review's form
    "gh pr -R a/b --repo c/d merge 46",
    "gh pr edit 46 -R a/b --title t -R c/d",
    "gh pr create -R a/b --title t --body x -R c/d",
])
def test_a_command_naming_two_repos_fails_closed(monkeypatch, capsys, command):
    calls = []
    code, err = _run(monkeypatch, capsys, command, body="clean", calls=calls)
    assert code == 2 and calls == [] and "more than one repo" in err and "a/b, c/d" in err


@pytest.mark.parametrize("command", [
    "gh pr merge 46 -R a/b -R a/b --squash",
    "gh pr -R a/b merge 46 --repo=a/b",
])
def test_the_same_repo_named_twice_is_checked_there(monkeypatch, capsys, command):
    calls = []
    code, err = _run(monkeypatch, capsys, command, body="clean", calls=calls)
    assert code == 0 and _issue_list(calls)[2:4] == ["-R", "a/b"], err


@pytest.mark.parametrize("command,repo", [
    ("gh pr create --title '-Rework the parser' --body x", None),
    ("gh pr create -R a/b --title t --body '-Rc/d is not a flag here'", "a/b"),
])
def test_a_title_or_body_starting_with_dash_r_is_not_a_repo(monkeypatch, capsys,
                                                            command, repo):
    """`_flag` reads an attached `-R...` anywhere, a body value included, and
    checked the repo `ework the parser`."""
    calls = []
    code, err = _run(monkeypatch, capsys, command, open_issues=(), calls=calls)
    issue_list = _issue_list(calls)
    assert code == 0, err
    assert (issue_list[2:4] == ["-R", repo]) if repo else "-R" not in issue_list


# ── one-letter flags in a group (wealth-mgmt #309 post-merge review) ───────
# pflag reads `-sR c/d` as -s then -R c/d. The gate read only a word that began
# with the flag, so the repo and the body file in a group went unread.

@pytest.mark.parametrize("command", [
    "gh pr merge 46 -sR c/d",                   # the review's form
    "gh pr merge 46 -dRc/d",
    "gh pr merge 46 -sdR=c/d",
    "gh pr merge 46 -mR c/d",                   # -m is --merge here, no value
    "gh pr -sRc/d merge 46",                    # before the verb, attached
])
def test_a_repo_flag_in_a_group_is_read(monkeypatch, capsys, command):
    calls = []
    code, err = _run(monkeypatch, capsys, command, body="clean", calls=calls)
    view = next(a for a, _ in calls if a[:2] == ["pr", "view"])
    assert code == 0 and _repo_of(view) == "c/d", err
    assert _issue_list(calls)[2:4] == ["-R", "c/d"]


def test_a_repo_flag_in_a_group_counts_toward_two_repos(monkeypatch, capsys):
    calls = []
    code, err = _run(monkeypatch, capsys, "gh pr merge 46 -R a/b -sR c/d", calls=calls)
    assert code == 2 and calls == [] and "a/b, c/d" in err


@pytest.mark.parametrize("command", [
    "gh pr edit 46 -tRework --body x",          # -t takes the rest: a title
    "gh pr create -lRelease --title t --body x",  # -l is --label on create
    "gh pr create -mR --title t --body x",      # -m is --milestone on create
])
def test_an_r_after_a_flag_that_takes_a_value_is_that_value(monkeypatch, capsys, command):
    calls = []
    code, err = _run(monkeypatch, capsys, command, open_issues=(), calls=calls)
    assert code == 0 and "-R" not in _issue_list(calls), err


@pytest.mark.parametrize("flags", ["-sF {f}", "-dF{f}", "-F {clean} -F {f}", "-F {f} -F {clean}",
                                   "--body-file={clean} -F {f}"])
def test_every_body_file_is_read_in_a_group_or_repeated(monkeypatch, capsys, tmp_path, flags):
    """`-sF b.md` never read b.md, and of `-F a.md -F b.md` only a.md was read
    while gh used b.md."""
    (tmp_path / "dirty.md").write_text("Small fixes from #261.", encoding="utf-8")
    (tmp_path / "clean.md").write_text("Clean body.", encoding="utf-8")
    command = "gh pr merge 46 " + flags.format(f=(tmp_path / "dirty.md").as_posix(),
                                                clean=(tmp_path / "clean.md").as_posix())
    code, err = _run(monkeypatch, capsys, command, body="clean")
    assert code == 2 and "#261" in err, err


@pytest.mark.parametrize("text,code", [("Small fixes from #261.", 2), ("Clean body.", 0)])
def test_a_grouped_stdin_body_with_its_heredoc_is_scanned(monkeypatch, capsys, text, code):
    command = f"gh pr create --title t -dF - <<'EOF'\n{text}\nEOF"
    got, err = _run(monkeypatch, capsys, command)
    assert "stdin" not in err and got == code, err


# ── any flag with a value before the verb (2026-11-09) ────────────────────
# gh finds the verb past `--x v`, `-x v`, `--x=v` and `-xv`, and the verb reads
# them as its own; the gate looked past `-R` alone, so these merged unread.

@pytest.mark.parametrize("command", [
    "gh pr --subject 'Small fixes from #261.' merge 46",
    "gh pr -t 'Small fixes from #261.' merge 46",
    "gh pr --body='Small fixes from #261.' merge 46",
    "gh pr --title t --body 'Small fixes from #261.' create",
    "gh pr -sRo/r --subject 'Small fixes from #261.' merge 46",
])
def test_a_command_with_flags_before_the_verb_is_found_and_checked(monkeypatch, capsys,
                                                                  command):
    calls = []
    code, err = _run(monkeypatch, capsys, command, body="clean", calls=calls)
    assert code == 2 and "#261" in err and calls, err


def test_a_body_file_before_the_verb_is_read(monkeypatch, capsys, tmp_path):
    (tmp_path / "b.md").write_text("Small fixes from #261.", encoding="utf-8")
    code, err = _run(monkeypatch, capsys,
                     f"gh pr --body-file {(tmp_path / 'b.md').as_posix()} merge 46",
                     body="clean")
    assert code == 2 and "#261" in err, err


def test_flags_before_the_verb_inside_a_shell_still_block(monkeypatch, capsys):
    code, err = _run(monkeypatch, capsys, "bash -c 'gh pr --subject \"a b\" merge 46'")
    assert code == 2 and "cannot read" in err, err


@pytest.mark.parametrize("command,target", [
    ("gh pr merge -sR c/d 46", "46"),           # the review of wealth-mgmt PR 311
    ("gh pr merge -dt release 46", "46"),       # -t is --subject: `release` is its value
    ("gh pr merge -dtrelease 46", "46"),
    ("gh pr merge -s 46", "46"),
    ("gh pr merge --match-head-commit abc123 46", "46"),
    ("gh pr edit --add-label bug 12 --title t", "12"),
    ("gh pr edit -mv1 12", "12"),
])
def test_the_pr_is_found_past_flag_groups_and_long_values(command, target):
    """The PR reader split flags its own way: in `gh pr merge -sR c/d 46` it
    passed over `-sR` and took `c/d` as the PR, where the repo reader took
    `c/d` as the repo."""
    verb, args, _ = gate._pr_commands(command)[0]
    assert gate._target(verb, args) == target


def test_a_grouped_repo_before_the_pr_checks_that_pr_there(monkeypatch, capsys):
    calls = []
    code, err = _run(monkeypatch, capsys, "gh pr merge -sR c/d 46", body="clean", calls=calls)
    view = next(a for a, _ in calls if a[:2] == ["pr", "view"])
    assert code == 0 and view[2] == "46" and _repo_of(view) == "c/d", err


# ── a dash or quoted value before the verb (wealth-mgmt PR 311 review) ────
# _verb_at pairs `-x v` whatever v is, but the pattern the shell, substitution,
# xargs and stdin checks then shared took a lone `-` for no value and stopped at
# an escaped or attached quote, so `bash -c 'gh pr -t - merge 46'` merged unread.

@pytest.mark.parametrize("command,why", [
    ("bash -c 'gh pr -t - merge 46'", "cannot read"),           # the review's form
    ("bash -c 'gh pr -F - merge 46'", "cannot read"),
    ("""bash -c 'gh pr --subject "a \\"b\\"" merge 46'""", "cannot read"),
    ("""bash -c 'gh pr --subject="a b" merge 46'""", "cannot read"),
    ("""bash -c 'gh pr -t"a b" merge 46'""", "cannot read"),
    ("echo 46 | xargs gh pr -t - merge", "xargs"),
])
def test_a_dash_or_quoted_value_before_the_verb_still_blocks(monkeypatch, capsys,
                                                             command, why):
    code, err = _run(monkeypatch, capsys, command)
    assert code == 2 and why in err, err


def test_a_quoted_substitution_past_a_dash_value_is_read(monkeypatch, capsys):
    code, err = _run(monkeypatch, capsys, 'out="$(gh pr -t - merge 46)"',
                     body="Small fixes from #261.")
    assert code == 2 and "#261" in err, err


@pytest.mark.parametrize("text,code", [("Small fixes from #261.", 2), ("Clean body.", 0)])
def test_a_stdin_body_before_the_verb_with_its_heredoc_is_scanned(monkeypatch, capsys,
                                                                  text, code):
    got, err = _run(monkeypatch, capsys, f"gh pr -F - merge 46 <<'EOF'\n{text}\nEOF",
                    body="clean")
    assert "stdin" not in err and got == code, err


@pytest.mark.parametrize("command", [
    "gh pr merge 46", "gh pr -R o/r merge 46", "gh pr --repo=o/r merge 46",
    "gh pr -sRo/r merge 46", "gh pr -t - merge 46", "gh pr -F - merge 46",
    "gh pr --subject -x merge 46", "gh pr --subject 'a b' merge 46",
    'gh pr --subject "a \\"b\\"" merge 46', 'gh pr --subject="a b" merge 46',
    "gh pr -t'a b' merge 46", "gh pr - merge 46",
    'gh pr -ta" b" merge 46', 'gh pr --subject a" b" merge 46',    # PR 847 review
    'gh pr --subject=x"a b" merge 46', "gh pr --subject a\\ b merge 46",
    # cobra pairs the flag with `merge`, so there is no verb; `--` ends the flags
    "gh pr --squash merge 46", "gh pr -s merge 46", "gh pr -- merge 46",
    "gh pr view 46", "gh pr -R o/r view 46", "gh pr list --search merge",
])
def test_the_verb_pattern_finds_what_the_parser_finds(command):
    """The stdin check finds a `gh pr` verb by pattern and the parser by
    _verb_at. Where the pattern misses, a correct command with its heredoc
    fails closed; the other checks no longer use it."""
    found = gate._verb_at(shlex.split(command), 0) is not None
    assert (re.search(r"\b" + gate._PR_VERB_TEXT, command) is not None) == found


@pytest.mark.parametrize("path", [_PATH, Path(__file__)], ids=["hook", "test"])
def test_every_line_fits_the_strictest_consumer_lint(path):
    """command-center lints these two files at 100 columns. best-practices does
    not check line length, so a 101-column line merged here and failed there
    (2026-11-09). This test travels with the copies and fails first."""
    lines = path.read_text(encoding="utf-8").splitlines()
    assert [n for n, line in enumerate(lines, 1) if len(line) > 100] == []


# ── the parser decides (command-center PR 847 review) ────────────────────
# The shell and substitution checks ran a pattern before the parser, and the
# xargs check ran one alone. A value the pattern could not shape (`-ta" b"`,
# a quote that starts mid-word) or a quoted `"pr"` hid the merge from all three.

@pytest.mark.parametrize("command,why", [
    ("""bash -c 'gh pr -ta" b" merge 46'""", "cannot read"),      # the review's form
    ("""bash -c 'gh pr --subject a" b" merge 46'""", "cannot read"),
    ("""bash -c 'gh "pr" merge 46'""", "cannot read"),
    ('CMD=\'gh "pr" merge 5\'\neval "$CMD"', "cannot read"),
    ("""echo 46 | xargs gh pr -ta" b" merge""", "xargs"),
    # in a quoted `$(...)`: one word at the top (wealth-mgmt PR 317 review)
    ('out="$(echo 46 | xargs gh pr merge --squash)"', "xargs"),
    ('echo "$(echo 46 | xargs -n1 gh pr -R o/r merge)"', "xargs"),
    ("out=$(echo 46 | xargs gh pr merge --squash)", "xargs"),
    ("out=`echo 46 | xargs gh pr merge --squash`", "xargs"),
])
def test_a_command_only_the_parser_reads_still_blocks(monkeypatch, capsys, command, why):
    code, err = _run(monkeypatch, capsys, command)
    assert code == 2 and why in err, err


def test_a_substitution_only_the_parser_reads_is_checked(monkeypatch, capsys):
    code, err = _run(monkeypatch, capsys, 'out="$(gh pr -ta\' b\' merge 46)"',
                     body="Small fixes from #261.")
    assert code == 2 and "#261" in err, err


def test_a_body_that_mentions_xargs_is_prose(monkeypatch, capsys):
    """The xargs pattern ran over the whole text and blocked this create."""
    code, err = _run(monkeypatch, capsys,
                     'gh pr create --title t --body "run: xargs gh pr merge 5"')
    assert code == 0, err


@pytest.mark.parametrize("command", [
    "gh pr -ta\" b\" create -F - <<'EOF'\nClean body.\nEOF",
    "gh pr create --title t -F- <<'EOF'\nClean body.\nEOF",
])
def test_a_visible_stdin_body_is_read_not_failed_closed(monkeypatch, capsys, command):
    code, err = _run(monkeypatch, capsys, command)
    assert code == 0 and "stdin" not in err, err


@pytest.mark.parametrize("text,reads", [
    ("-F -", True), ("-F-", True), ("--body-file -", True), ("--body-file=-", True),
    ("-dF -", True), ("-sdF -", True), ("-tF -", False), ("-F -x", False),
])
def test_the_stdin_pattern_reads_only_a_real_body_file_dash(text, reads):
    """In `-tF -`, F is the title and `-` a stray argument: nothing reads stdin."""
    assert (gate._READS_STDIN.search(text) is not None) == reads
