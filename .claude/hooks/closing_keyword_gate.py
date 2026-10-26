#!/usr/bin/env python3
"""
.claude/hooks/closing_keyword_gate.py
PreToolUse gate: no PR may close an OPEN issue by accident.

Canonical copy lives in best-practices/.claude/hooks/, with its tests beside it;
repos that carry the gate carry an identical copy, as with lint_on_write.py.

GitHub closes an issue when a closing word (close/fix/resolve, any tense)
appears near "#N" anywhere in a merged PR's body or in any of its commit
messages. Its matcher is looser than its documentation, and prose kept
tripping it in the consumer repos:

  "the fix #247 settled on"        closed #247 on a merge (2026-09-30)
  "...claude/261-small-fixes\\n\\n#261: small fixes"
                                   closed #261 on a merge (2026-10-04): the
                                   branch name and the title, joined by the
                                   merge commit GitHub writes

plus three strikes in another repo in August ("Does NOT close #1851", "no
auto-close: #1418", "fixed 2026-08-20\\nunder #1802"). Three strikes of one
class make a gate, not another rule.

On `gh pr create` / `gh pr edit` it scans the title and body being written. On
`gh pr merge` it reads the PR's title, body and every commit message from
GitHub, because all of them feed the parser. It reads every `gh pr` command in
a chained command, typed in Bash or PowerShell, and the raw command text too,
which is the only place a heredoc body survives. It flags a closing word within
the same sentence as an OPEN issue's number; closed numbers are skipped, since
re-closing them is a no-op. A deliberate close is a line of its own:

    Closes #255

Blocking is exit 2 with the reason on stderr. A gate that cannot read the PR
also blocks: an error that let the merge through would be a gate that fails
open on exactly the run it exists for.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys

# GitHub's closing words, then at most two intervening words (spaces, colons
# and newlines between), then the number. Calibrated on what GitHub actually
# did: every strike had the number right after the word, or within two words
# ("fixed 2026-08-20\nunder #1802"), while #262's commits, with "fix(...)" about
# ten words before "#261", did NOT close it. A sentence-wide window flagged
# every "fix(x): ...\n\n#N" commit in this repo's own style.
#
# The reference is any form GitHub honours: `#N`, `owner/repo#N`, or the issue
# URL. Only `#N` was matched, so "Fixes owner/repo#261" or a pasted issue link
# closed the issue past the gate, and a reference into ANOTHER repo was outside
# its model entirely.
_REF = (r"(?:#(?P<n1>\d+)"
        r"|(?P<repo>[\w.-]+/[\w.-]+)#(?P<n2>\d+)"
        r"|https?://github\.com/(?P<urepo>[\w.-]+/[\w.-]+)/issues/(?P<n3>\d+))")
KEYWORD_NEAR_ISSUE = re.compile(
    r"\b(close[sd]?|fix(?:e[sd])?|resolve[sd]?)\b(?:[\s:]+[^\s.#]+){0,2}?[\s:]+" + _REF,
    re.IGNORECASE)
DELIBERATE_LINE = re.compile(
    r"^\s*(close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s*:?\s*" + _REF + r"\s*\.?\s*$",
    re.IGNORECASE)


def risky_references(text: str, open_issues: set[int],
                     this_repo: str | None = None) -> list[tuple[int | str, str]]:
    """(issue, snippet) for each accidental closing reference.

    An issue in this repo is an int and counts only while open. One in another
    repo is "owner/repo#N" and always counts: GitHub closes it on merge, and
    its open issues are not fetched. `this_repo` ("owner/repo") lets a
    qualified reference to this repo be judged like `#N`.
    """
    def ref(m) -> tuple[str | None, int]:
        repo = m.group("repo") or m.group("urepo")
        n = int(m.group("n1") or m.group("n2") or m.group("n3"))
        if repo and this_repo and repo.lower() == this_repo.lower():
            repo = None
        return (repo.lower() if repo else None), n

    deliberate = {ref(m) for line in text.splitlines()
                  if (m := DELIBERATE_LINE.match(line))}
    hits = []
    for m in KEYWORD_NEAR_ISSUE.finditer(text):
        repo, n = ref(m)
        if (repo, n) in deliberate:
            continue
        snippet = " ".join(m.group(0).split())[:160]
        if repo is None and n in open_issues:
            hits.append((n, snippet))
        elif repo is not None:
            hits.append((f"{repo}#{n}", snippet))
    return hits


# `SP="C:/.../scratchpad"` earlier in the same command, then `--body-file
# "$SP/body.md"`: the hook sees the command text before the shell runs it, so
# the variable has to be resolved here. Its first live run blocked exactly that
# (2026-10-05). An unresolvable path still fails closed in main().
_ASSIGN = re.compile(r"""(?:^|[\s;&|(])([A-Za-z_][A-Za-z0-9_]*)=("[^"]*"|'[^']*'|[^\s;&|]+)""")
_VAR_REF = re.compile(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?")


def _shell_vars(command: str) -> dict[str, str]:
    found = {}
    for name, raw in _ASSIGN.findall(command):
        quoted = len(raw) >= 2 and raw[0] in "\"'" and raw[-1] == raw[0]
        found[name] = raw[1:-1] if quoted else raw
    return found


def _expand(value: str, shell_vars: dict[str, str]) -> str:
    return _VAR_REF.sub(lambda m: shell_vars.get(m.group(1),
                                                 os.environ.get(m.group(1), m.group(0))),
                        value)


def _flag(args: list[str], *names: str) -> str | None:
    for i, a in enumerate(args):
        for name in names:
            if a == name and i + 1 < len(args):
                return args[i + 1]
            if a.startswith(name + "="):
                return a.split("=", 1)[1]
    return None


def _gh(args: list[str], cwd: str | None = None) -> str:
    # Each call under 20s. One merge is two gh calls (the PR, the open issues)
    # plus a 5s `git remote` per command in _repo_slug, so an edit chained to a
    # merge is 20+20+5+5 = 50s, inside the 60s hook timeout in settings.json.
    # Past that timeout Claude Code treats the hook as making NO decision, and
    # the merge would run unchecked. Two merges chained in one command can
    # still exceed it.
    out = subprocess.run(["gh", *args], capture_output=True, timeout=20, cwd=cwd)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.decode("utf-8", "replace").strip()[:300])
    return out.stdout.decode("utf-8", "replace")


_SEPARATORS = {"&&", "||", ";", "|", "&"}

# Flags that take a value, per verb. The PR is the first argument that is
# neither a flag nor such a value: `gh pr merge -R owner/app 264` read
# `owner/app` as the PR and blocked a correct merge. Per verb because `-m` is
# `--merge` (no value) on merge and `--milestone` on edit.
_VALUE_FLAGS = {
    "merge": {"-t", "--subject", "-b", "--body", "-F", "--body-file", "-A",
              "--author-email", "--match-head-commit", "-R", "--repo"},
    "edit": {"-t", "--title", "-b", "--body", "-F", "--body-file", "-B", "--base",
             "-m", "--milestone", "--add-assignee", "--remove-assignee", "--add-label",
             "--remove-label", "--add-project", "--remove-project", "--add-reviewer",
             "--remove-reviewer", "-R", "--repo"},
}


def _target(verb: str, args: list[str]) -> str:
    """The PR a merge or edit names, or "" (create has none; "" is the branch's)."""
    takes_value = _VALUE_FLAGS.get(verb)
    if takes_value is None:
        return ""
    skip = False
    for a in args:
        if skip:
            skip = False
        elif a in takes_value:
            skip = True
        elif not a.startswith("-"):
            return a
    return ""


def _is_pr_verb(tokens: list[str], i: int) -> bool:
    return (tokens[i].endswith("gh") and tokens[i + 1:i + 2] == ["pr"]
            and tokens[i + 2:i + 3] in (["create"], ["edit"], ["merge"]))


def _unquote(token: str) -> str:
    """One matching pair of surrounding quotes off, a trailing `;` kept."""
    tail = ";" if token.endswith(";") else ""
    core = token[:-1] if tail else token
    if len(core) >= 2 and core[0] == core[-1] and core[0] in "\"'":
        core = core[1:-1]
    return core + tail


def _split(command: str, shell: str) -> list[str]:
    # PowerShell has no backslash escape (its escape is the backtick), and
    # POSIX shlex read `C:\Users\...\b.md` as `C:Users...b.md`.
    if shell != "PowerShell":
        return shlex.split(command, posix=True)
    lex = shlex.shlex(command, posix=True)
    lex.whitespace_split, lex.escape, lex.commenters = True, "", ""
    return list(lex)


def _local_path(path: str, nt: bool = os.name == "nt") -> str:
    """An MSYS path (`/c/Users/...`, what Git Bash prints) as Windows Python
    opens it. Windows Python read `/c/...` as `C:\\c\\...` and found nothing."""
    m = re.match(r"^/([A-Za-z])(/.*)?$", path)
    if nt and m and not os.path.exists(path):
        return f"{m.group(1).upper()}:{m.group(2) or '/'}"
    return path


_HEREDOC_OPEN = re.compile(r"<<-?\s*(['\"]?)(\w+)\1")


def _strip_heredocs(command: str) -> str:
    """The command with heredoc and here-string BODIES removed.

    Prose in a body written earlier in the command ("then gh pr merge -R
    owner/app 264") was parsed as a command, checked against the wrong PR,
    and failed closed (2026-10-26). Only command finding uses this; the raw
    text, bodies included, is still what gets scanned for closing words.
    """
    out, ends = [], []
    for line in command.split("\n"):
        if ends:
            end = ends[0]
            if line.strip() == end or (end.endswith("@") and line.lstrip().startswith(end)):
                ends.pop(0)
                out.append(line)
            continue
        out.append(line)
        ends = [m.group(2) for m in _HEREDOC_OPEN.finditer(line)]
        if re.search(r"@['\"]\s*$", line):
            ends.append(line.rstrip()[-1] + "@")
    return "\n".join(out)


def _pr_commands(command: str, shell: str = "Bash") -> list[tuple[str, list[str], str | None]]:
    """(verb, its own args, the `cd` in force) for EVERY gh pr command in it.

    Every one, not the first: `gh pr edit ... && gh pr merge ...` is the chain
    this gate's own advice invites, and reading only the edit let the merge
    through unchecked. Each command's args stop at a separator or the next one.
    The `cd` matters because gh resolves the repo from its working directory:
    `cd ../other-repo && gh pr merge 46` was checked against THIS repo's
    PR #46 and open issues, found nothing, and passed.
    """
    command = _strip_heredocs(command)
    try:
        tokens = _split(command, shell)
    except ValueError:
        # An odd apostrophe or quote outside a heredoc makes shlex raise. Plain
        # split kept the quotes on "$SP/body.md", and a correct create failed
        # closed on a path with quotes in it.
        tokens = [_unquote(t) for t in command.split()]
    found = []
    cd = None
    for i in range(len(tokens)):
        if tokens[i] in ("cd", "Set-Location", "sl", "pushd") and i + 1 < len(tokens):
            cd = tokens[i + 1].rstrip(";")
        if not _is_pr_verb(tokens, i):
            continue
        args = []
        for j in range(i + 3, len(tokens)):
            t = tokens[j]
            if t in _SEPARATORS or _is_pr_verb(tokens, j):
                break
            if t.endswith(";"):                    # `... b.md; gh pr merge`
                args.append(t[:-1])
                break
            args.append(t)
        found.append((tokens[i + 2], args, cd))
    return found


_PR_URL = re.compile(r"https?://github\.com/([\w.-]+/[\w.-]+)/pull/\d+")
_REMOTE = re.compile(r"github\.com[:/]([\w.-]+/[\w.-]+?)(?:\.git)?/?$")


def _repo_slug(repo: tuple, cwd: str | None) -> str | None:
    """"owner/repo" the command targets: its -R, else the git remote where gh runs."""
    if repo:
        return "/".join(repo[1].rstrip("/").split("/")[-2:])
    try:
        out = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True,
                             timeout=5, cwd=cwd)
    except Exception:  # noqa: BLE001 - unknown means every qualified ref counts
        return None
    m = _REMOTE.search(out.stdout.decode("utf-8", "replace").strip())
    return m.group(1) if m else None


def text_to_scan(verb: str, args: list[str], repo: list[str],
                 shell_vars: dict[str, str] | None = None, cwd: str | None = None) -> str:
    parts = [_flag(args, "--title", "-t") or "", _flag(args, "--body", "-b") or "",
             _flag(args, "--subject") or ""]
    body_file = _flag(args, "--body-file", "-F")
    if body_file and body_file != "-":     # stdin: main() checks the heredoc
        with open(_local_path(_expand(body_file, shell_vars or {})), encoding="utf-8") as f:
            parts.append(f.read())
    if verb == "merge":
        target = [t] if (t := _target(verb, args)) else []
        pr = json.loads(_gh(["pr", "view", *target, *repo,
                             "--json", "number,title,body,commits,headRefName"], cwd=cwd))
        parts += [pr.get("title") or "", pr.get("body") or ""]
        # The merge commit GitHub writes: "Merge pull request #N from
        # owner/<branch>", a blank line, then the title. That is what closed
        # #261: branch "claude/261-small-fixes" ended in "fixes" and the title
        # began "#261:", so the commit read "...small-fixes\n\n#261:".
        parts.append(f"Merge pull request #{pr.get('number')} from "
                     f"{pr.get('headRefName') or ''}\n\n{pr.get('title') or ''}")
        for c in pr.get("commits") or []:
            parts += [c.get("messageHeadline") or "", c.get("messageBody") or ""]
    return "\n\n".join(parts)


_ISSUE_LIMIT = 1000
_HEREDOC = re.compile(r"<<-?\s*['\"]?\w+|@['\"]\s*$", re.MULTILINE)
_XARGS = re.compile(r"\bxargs\b[^;&|\n]*\bgh\s+pr\s+(?:create|edit|merge)\b")
# `GH_REPO=o/r gh pr merge 46` and PowerShell's `$env:GH_REPO = "o/r"` point gh
# at another repo, and the gate read this one's PR #46 and open issues.
_PS_GH_REPO = re.compile(r"""\$env:GH_REPO\s*=\s*["']?([^"'\s;]+)""", re.IGNORECASE)


def _gh_repo(command: str, shell_vars: dict[str, str]) -> str | None:
    m = _PS_GH_REPO.search(command)
    return shell_vars.get("GH_REPO") or (m.group(1) if m else None)


# PowerShell is the primary shell in these sessions, and `gh` is on its PATH. A
# gate that answered only to Bash let any merge typed there through unread.
_SHELL_TOOLS = {"Bash", "PowerShell"}


def main() -> int:
    payload = json.loads(sys.stdin.buffer.read().decode("utf-8") or "{}")
    if payload.get("tool_name") not in _SHELL_TOOLS:
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    found = _pr_commands(command, payload.get("tool_name"))
    if not found:
        return 0
    if _XARGS.search(command):
        # `... | xargs -n1 gh pr merge` gives gh its PR on stdin, so the gate
        # would read the current branch's PR instead of the ones being merged.
        print("closing_keyword_gate: a `gh pr` command fed by xargs names PRs the "
              "gate cannot see. Run each `gh pr merge <n>` on its own.", file=sys.stderr)
        return 2
    verb = "/".join(dict.fromkeys(v for v, _, _ in found))
    shell_vars = _shell_vars(command)
    base = payload.get("cwd") or os.getcwd()
    checks = []
    try:
        for v, args, cd in found:
            target_dir = _local_path(_expand(cd, shell_vars)) if cd else None
            cwd = (os.path.normpath(os.path.join(base, os.path.expanduser(target_dir)))
                   if target_dir else base)
            repo_flag = _flag(args, "--repo", "-R") or _gh_repo(command, shell_vars)
            repo = ("-R", _expand(repo_flag, shell_vars)) if repo_flag else ()
            target = _target(v, args)
            if _flag(args, "--body-file", "-F") == "-" and not _HEREDOC.search(command):
                raise RuntimeError("--body-file - reads stdin, which the gate cannot see; "
                                   "write the body to a file or pass it as a heredoc")
            if not repo and (m := _PR_URL.match(target)):
                repo = ("-R", m.group(1))       # a PR URL names its own repo
            # The raw command as well as the parsed flags. shlex cannot read a
            # body written as --body "$(cat <<'EOF' ... EOF)": the first quote
            # inside the text ends the argument, and every line after it went
            # unscanned. The raw text holds that body verbatim, and a PowerShell
            # here-string the same way.
            checks.append(((repo, cwd), _repo_slug(repo, cwd),
                           text_to_scan(v, args, list(repo), shell_vars, cwd)
                           + "\n\n" + command))
        open_issues = {}
        for (repo, cwd), _, _ in checks:
            if (repo, cwd) not in open_issues:
                numbers = _gh(["issue", "list", *repo, "--state", "open", "--limit",
                               str(_ISSUE_LIMIT), "--json", "number", "--jq", ".[].number"],
                              cwd=cwd).split()
                # gh lists newest first, so a full page drops the oldest open
                # issues, and a close aimed at one of them would pass as clean.
                if len(numbers) >= _ISSUE_LIMIT:
                    raise RuntimeError(f"{len(numbers)} open issues reached the "
                                       f"{_ISSUE_LIMIT} listing limit; the list is incomplete")
                open_issues[(repo, cwd)] = {int(n) for n in numbers}
    except Exception as e:  # noqa: BLE001 - fail closed, with the reason
        print(f"closing_keyword_gate: could not check this `gh pr {verb}` for "
              f"accidental issue closes ({type(e).__name__}: {e}). Fix the cause "
              "and retry; this gate does not let an unchecked merge through.",
              file=sys.stderr)
        return 2
    hits = list(dict.fromkeys(hit for key, slug, text in checks
                              for hit in risky_references(text, open_issues[key], slug)))
    if not hits:
        return 0
    lines = "\n".join(f"  {n if isinstance(n, str) else f'#{n}'}: \"{snippet}\""
                      for n, snippet in hits)
    print(f"closing_keyword_gate: this `gh pr {verb}` would let GitHub close "
          f"open issue(s) by accident:\n{lines}\n"
          "Keep every close/fix/resolve word more than two words from the number "
          "(\"#N stays open\", \"(#N)\" at the end of a clause). If closing is "
          "intended, put it on a line of its own: `Closes #N`. For a merge: edit "
          "the PR body or title (gh pr edit); a branch name ending in fix/fixes "
          "next to a title starting with #N means retitling; a commit message "
          "needs a reworded commit.",
          file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
