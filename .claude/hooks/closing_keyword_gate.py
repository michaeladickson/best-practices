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

What it does not model, it blocks rather than parses. Four review rounds on
2026-10-26 each found another shell construct the parsing misread (#69), so
these fail closed with the reason: a `gh pr` command handed to another shell
(`bash -c`, `eval`, `ssh`, a heredoc fed to a shell, `Invoke-Expression`);
GH_REPO in any form but a `GH_REPO=o/r cmd` prefix; and more than one `gh pr`
command reading `--body-file -`. A shell counts only where it runs: as the
command a statement or pipeline stage runs, read from words that keep the
operators, newlines and quotes shlex.split drops. A shell word anywhere in the
statement blocked a read-only `wsl -- grep "gh pr merge"`, and `|bash` was not
a shell at all (#82).
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
            # A one-letter flag takes its value attached: `-Rowner/repo`. Unread,
            # the repo was dropped and the merge checked against this one.
            if len(name) == 2 and len(a) > 2 and a.startswith(name):
                return a[2:]
    return None


# gh pr's one-letter flags that take no value, and its long flags that take one,
# per verb (gh 2.90.0 `--help`). pflag reads a group such as `-sR c/d` letter by
# letter, and the first letter that takes a value takes the rest of the word
# (`-sRc/d`) or the next word: so `-dR o/r` names a repo while `-tRework` is a
# title (checked 2026-11-09). Per verb because `-m` is `--merge` (no value) on
# merge and `--milestone` on create and edit.
_NO_VALUE_SHORT = {"create": "defw", "edit": "", "merge": "dmrs"}
_LONG_WITH_VALUE = {
    "create": {"--assignee", "--base", "--body", "--body-file", "--head", "--label",
               "--milestone", "--project", "--recover", "--reviewer", "--template",
               "--title", "--repo"},
    "edit": {"--add-assignee", "--add-label", "--add-project", "--add-reviewer", "--base",
             "--body", "--body-file", "--milestone", "--remove-assignee", "--remove-label",
             "--remove-project", "--remove-reviewer", "--title", "--repo"},
    "merge": {"--author-email", "--body", "--body-file", "--match-head-commit",
              "--subject", "--repo"},
}


def _takes_next(verb: str, word: str) -> bool:
    """Whether `word` is a flag whose value is the next word: a long flag that
    takes one, written without `=`, or a one-letter group whose first letter that
    takes a value ends the word (`-R`, `-sR`, `-dt`). Every reader of the args
    splits them with this, so they agree on which word is which."""
    if word.startswith("--"):
        return "=" not in word and word in _LONG_WITH_VALUE.get(verb, ())
    return word.startswith("-") and len(word[1:].lstrip(_NO_VALUE_SHORT.get(verb, ""))) == 1


def _values(verb: str, args: list[str], long: str, short: str | None = None) -> list[str]:
    """Every value one flag is given in a command's args, in order, in each form
    gh takes: `--repo x`, `--repo=x`, `-R x`, `-Rx`, `-R=x`, and after other
    one-letter flags in a group (`-sR x`, `-dRx`).

    gh keeps the LAST of a repeated flag, and a reader that returned the first,
    or knew no groups, checked the wrong thing: `gh pr merge 46 -R a/b -R c/d`
    and `-R a/b -sR c/d` against a/b while gh merged c/d (the post-merge reviews
    of wealth-mgmt PRs 307 and 309), and `-sF b.md` never read b.md.
    """
    out, skip = [], False
    no_value = _NO_VALUE_SHORT.get(verb, "")
    for i, a in enumerate(args):
        nxt = args[i + 1] if i + 1 < len(args) else None
        if skip:
            skip = False
        elif a == long or a.startswith(long + "="):
            if "=" in a:
                out.append(a.split("=", 1)[1])
            elif nxt is not None:
                out.append(nxt)
                skip = True
        else:
            letters = a[1:].lstrip(no_value)
            if short and a.startswith("-") and not a.startswith("--") and letters[:1] == short:
                if value := letters[1:].removeprefix("="):
                    out.append(value)
                elif nxt is not None:
                    out.append(nxt)
            skip = _takes_next(verb, a)         # its value, or another flag's, is next
    return out


def _repos(verb: str, args: list[str]) -> list[str]:
    """Every -R/--repo value, in order. main() blocks a command that names two
    different repos, and checks the last, the one gh uses."""
    return _values(verb, args, "--repo", "R")


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

def _target(verb: str, args: list[str]) -> str:
    """The PR a merge or edit names, or "" (create has none; "" is the branch's):
    the first word that is neither a flag nor a flag's value, split as _values
    splits them. `gh pr merge -R owner/app 264` once read `owner/app` as the PR,
    and `gh pr merge -sR c/d 46` read `c/d` (the review of wealth-mgmt PR 311)."""
    if verb not in ("merge", "edit"):
        return ""
    skip = False
    for a in args:
        if skip:
            skip = False
        elif a.startswith("-"):
            skip = _takes_next(verb, a)
        else:
            return a
    return ""


# `gh` as a command word: alone, at the end of a path, or right after what
# shlex.split leaves attached: shell punctuation (`x&&gh`, `$(gh`), the newline
# of a `\` line continuation (`\ngh`, two sessions' commands in 90 days), or a
# quote the fallback split kept (`'gh` after a stray apostrophe). Not after
# `=`: `--grep=gh pr create` is a search, and a bare endswith("gh") ran it (#82).
_GH_WORD = re.compile(r"(?:^|[\s\\/;&|(`${}!'\"])gh(?:\.exe)?$", re.IGNORECASE)


# `gh pr new` is gh's alias for create (`gh pr create --help`, gh 2.90.0).
_VERBS = {"create": "create", "new": "create", "edit": "edit", "merge": "merge"}
# The same as text, for the shell, substitution, xargs and stdin checks. Each
# word before the verb is read as _verb_at reads it, one way only: `--x v` and
# `-x v` take the next word whatever it is (`-F -`, `-t -x`); `--x=v`, `-xv` and
# a lone `-` stand alone. A lone `-` once read as no value hid `bash -c 'gh pr
# -t - merge 46'` from every check (wealth-mgmt PR 311 review). A value is a
# quoted run, `\"` included, then the rest of its word; or a bare word.
_VALUE = r"""(?:(?:"(?:[^"\\]|\\.)*"|'[^']*')\S*|[^\s"']\S*)"""
_PRE_VERB_WORD = (r"(?:(?:--[^\s=]+|-[^\s-])\s+" + _VALUE   # --x v, -x v
                  + r"|--[^\s=]*=" + _VALUE + r"?"          # --x=v
                  + r"|-[^\s-]" + _VALUE                    # -xv, -sRo/r
                  + r"|-)")                                 # a lone -
_PR_VERB_TEXT = (r"gh(?:\.exe)?\s+pr\s+(?:" + _PRE_VERB_WORD + r"\s+)*"
                 r"(?:create|new|edit|merge)\b")


def _verb_at(tokens: list[str], i: int) -> tuple[int, list[str]] | None:
    """(the verb's index, the flags before it) when tokens[i:] is
    `gh pr [flags] <verb>`.

    gh finds the verb as cobra does: before it, `--x v` and `-x v` are pairs and
    `--x=v` and `-xv` single words; the verb then reads them all as its own
    flags. So `gh pr -R o/r merge 46` (#284 M1), `gh pr --subject s merge 46`
    and `gh pr -sRo/r merge 46` all merge, and each was a command the gate never
    found. Checked 2026-11-09: `gh pr --jq .url view 80` and `gh pr -cRo/r view
    80` work; `gh pr --comments view 80` and `gh pr -cR o/r view 80` fail.
    """
    if _GH_WORD.search(tokens[i]) is None or tokens[i + 1:i + 2] != ["pr"]:
        return None
    k = i + 2
    while k < len(tokens) and tokens[k].startswith("-") and tokens[k] != "--":
        t = tokens[k]
        k += 2 if "=" not in t and (t.startswith("--") or len(t) == 2) else 1
    return (k, tokens[i + 2:k]) if k < len(tokens) and tokens[k] in _VERBS else None


def _is_pr_verb(tokens: list[str], i: int) -> bool:
    return _verb_at(tokens, i) is not None


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


# A heredoc operator, not a here-string (`<<<`) or a shift (`n<<1`): `<<` after
# whitespace, a separator or `(`, and a delimiter that starts like a word. A
# here-string opener `@'` or `@"` ends its line and follows whitespace, `=` or
# `(`; "bot@" at the end of a quoted email is not one.
_HEREDOC_OPEN = re.compile(r"(?<![^\s|;&(])<<(?!<)-?\s*(['\"]?)([A-Za-z_]\w*)\1"
                           r"|(?<=[A-Za-z])<<(?!<)-?(['\"]?)([A-Za-z_]\w*)\3(?=\s*(?:$|[|;&>]))")
_HERESTRING_OPEN = re.compile(r"(?:^|[\s=(])@(['\"])\s*$")


def _top_level_ops(line: str, shell: str) -> list[tuple[int, int, str]]:
    """(start, end, kind) of each `&&`, `||`, `;` and `&` ("stmt") and each `|`
    ("pipe") in `line` outside quotes. A quote left open runs to the line's end,
    as in `bash -c "$(cat <<'EOF'`."""
    esc = "`" if shell == "PowerShell" else "\\"
    out, i, quote = [], 0, None
    while i < len(line):
        c = line[i]
        if quote:
            if c == esc and quote == '"':
                i += 1
            elif c == quote:
                quote = None
        elif c == esc:
            i += 1
        elif c in "'\"":
            quote = c
        elif line.startswith(("&&", "||"), i):
            out.append((i, i + 2, "stmt"))
            i += 1
        elif c == "|":
            out.append((i, i + 1, "pipe"))
        elif c == ";" or (c == "&" and line[i - 1:i] not in ("<", ">", "|")
                          and line[i + 1:i + 2] != ">"):
            out.append((i, i + 1, "stmt"))
        i += 1
    return out


def _owner(line: str, start: int, end: int, shell: str = "Bash") -> str:
    """What reads a heredoc opened at [start, end) of `line`: from the pipeline
    stage that holds the operator to the end of its statement. Later stages stay
    in, since a heredoc piped into a shell (`cat <<EOF | bash`) is run by that
    shell; earlier ones go, since `gh pr edit 5 | bash <<EOF` feeds bash, not
    the edit. Separators inside quotes do not count: `ssh host 'cd app && sh'
    <<EOF` runs sh (#82)."""
    ops = _top_level_ops(line, shell)
    left = max((e for s, e, _ in ops if s < start), default=0)
    right = min((s for s, _, k in ops if s >= end and k == "stmt"), default=len(line))
    return line[left:right]


def _heredocs(command: str, shell: str = "Bash") -> tuple[str, list[tuple[str, str]]]:
    """The command with heredoc and here-string BODIES removed, and each
    removed body as (what reads it on its opening line + the statement after
    its terminator, the body). Not the whole line: in `wsl -- bash -c "pytest"
    && cat > b.md <<'EOF'` the body is cat's, and reading the line as one
    statement had `bash` run a PR body that mentioned `gh pr create`. After the
    terminator because a PowerShell here-string's reader follows it: `'@ | iex`.

    Prose in a body written earlier in the command ("then gh pr merge -R
    owner/app 264") was parsed as a command, checked against the wrong PR,
    and failed closed (2026-10-26). Only command finding uses the stripped
    text; the raw text, bodies included, is still what gets scanned for
    closing words. The bodies are returned so main() can tell a body that is
    prose from one fed to a shell, which runs.

    A body whose terminator never comes is kept, not dropped: an opener read
    by mistake (`$((n<<1))`, `"a << b"`) hid every later line, so a merge
    after it passed with nothing checked (re-review, 2026-10-26).
    """
    out, ends, owners, held, bodies = [], [], [], [], []
    for line in command.split("\n"):
        if ends:
            end = ends[0]
            if line.strip() == end or (end.endswith("@") and line.lstrip().startswith(end)):
                ends.pop(0)
                out.append(line)
                after = "" if line.strip() == end else line.lstrip()[len(end):]
                bodies.append((f"{owners.pop(0)}\n{_owner(after, 0, 0, shell)}",
                               "\n".join(held)))
                held = []
            else:
                held.append(line)
            continue
        out.append(line)
        ends, owners = [], []
        for m in _HEREDOC_OPEN.finditer(line):
            ends.append(m.group(2) or m.group(4))
            owners.append(_owner(line, m.start(), m.end(), shell))
        if m := _HERESTRING_OPEN.search(line):
            ends.append(m.group(1) + "@")
            owners.append(_owner(line, m.start(), m.end(), shell))
    return "\n".join(out + held), bodies


def _strip_heredocs(command: str) -> str:
    return _heredocs(command)[0]


def _tokens(command: str, shell: str) -> list[str]:
    try:
        return _split(command, shell)
    except ValueError:
        # An odd apostrophe or quote outside a heredoc makes shlex raise. Plain
        # split kept the quotes on "$SP/body.md", and a correct create failed
        # closed on a path with quotes in it.
        return [_unquote(t) for t in command.split()]


_OPERATOR_CHARS = "();<>|&\n"


def _words(text: str, shell: str) -> list[str]:
    """`text` as words plus operator tokens (`|`, `&&`, `;`, `(`, a newline,
    `>&`), quotes respected. shlex.split drops newlines and leaves `|bash`,
    `x&&bash` and `(bash` as one word, so a shell there was no shell and two
    lines read as one statement (#82). Bash backticks are operators too. A
    newline after `|`, `&&` or `||` continues the statement, as in the shell:
    read as an end, it cut `echo '...' |` from the `bash` on the next line."""
    text = text.replace("`\n" if shell == "PowerShell" else "\\\n", " ")
    text = re.sub(r"(\|\||&&|\|&?)[ \t]*\n", r"\1 ", text)
    punct = _OPERATOR_CHARS + ("" if shell == "PowerShell" else "`")
    try:
        lex = shlex.shlex(text, posix=True, punctuation_chars=punct)
        lex.whitespace, lex.whitespace_split, lex.commenters = " \t\r", True, ""
        if shell == "PowerShell":
            lex.escape = ""
        return list(lex)
    except ValueError:
        # An open quote: operators still come apart, so a stray apostrophe
        # cannot glue a shell to the word before it.
        cls = re.escape(punct)
        return [_unquote(t) for t in re.findall(rf"[{cls}]+|[^\s{cls}]+", text)]


def _kind(token: str) -> str:
    """"word"; "redirect" (`>`, `<<`, `>&`); "pipe" (`|`, `|&`, `)|`); "stmt"
    (`&&`, `||`, `;`, `&`, a newline); or "group" (`(`, `)`, a backtick)."""
    if not token or token.strip(_OPERATOR_CHARS + "`"):
        return "word"
    if "<" in token or ">" in token:
        return "redirect"
    if "|" in token.replace("||", ""):
        return "pipe"
    return "stmt" if token.strip("()`") else "group"


def _prefix_on_gh_line(command: str, value: str) -> bool:
    return re.search(r"GH_REPO=['\"]?" + re.escape(value) + r"['\"]?"
                     r"(?:[ \t]+[A-Za-z_]\w*=\S*)*[ \t]+\S*gh[ \t]+pr\b", command) is not None


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
    # A line continuation joins two lines into one command. shlex kept its
    # newline as a token, so `GH_REPO=o/r \` on the line before the merge lost
    # its prefix, and the gate checked this repo's #46 while gh merged o/r's (#294).
    command = command.replace("`\n" if shell == "PowerShell" else "\\\n", " ")
    tokens = _tokens(command, shell)
    found = []
    cd = None
    for i in range(len(tokens)):
        if tokens[i] in ("cd", "Set-Location", "sl", "pushd") and i + 1 < len(tokens):
            cd = tokens[i + 1].rstrip(";")
        if (at := _verb_at(tokens, i)) is None:
            continue
        verb, args = at[0], list(at[1])
        # `GH_REPO=o/r gh pr merge 46` points this one command at o/r. A prefix
        # binds only the command it precedes; read as a whole-command setting,
        # it redirected a later merge in the same chain to the wrong repo.
        prefix = None
        k = i - 1
        while k >= 0 and re.match(r"^[A-Za-z_]\w*=", tokens[k]):
            if tokens[k].startswith("GH_REPO="):
                prefix = tokens[k].split("=", 1)[1]
            k -= 1
        for j in range(verb + 1, len(tokens)):
            t = tokens[j]
            if t in _SEPARATORS or _is_pr_verb(tokens, j):
                break
            if t.endswith(";"):                    # `... b.md; gh pr merge`
                args.append(t[:-1])
                break
            args.append(t)
        # shlex drops newlines, so `GH_REPO=o/r` alone on the line before looked
        # like a prefix; and gh lets an explicit -R win over the variable.
        if (prefix and not _repos(_VERBS[tokens[verb]], args)
                and _prefix_on_gh_line(command, prefix)):
            args += ["-R", prefix]
        found.append((_VERBS[tokens[verb]], args, cd))
    prose = _prose(tokens)
    for k, t in enumerate(tokens):
        # `out="$(gh pr merge 264 2>&1)"`: quoted, the substitution is one
        # token, and the merge in it ran with nothing found (#82). A title,
        # body or commit message is text, not a substitution the gate reads.
        if k in prose:
            continue
        for inner in _substitutions(t, shell):
            found += [(v, a, c or cd) for v, a, c in _pr_commands(inner, shell)]
    return found


def _substitutions(token: str, shell: str) -> list[str]:
    """The text of each unescaped `$(...)` in a token that names a `gh pr`
    verb and closes within it; an open one is a pattern (`grep -F '$(gh pr
    merge'`). Not backticks: once shlex drops the quotes, a Markdown code span
    in a PR body or a single-quoted sed pattern reads the same as a backtick
    substitution. In 90 days of commands, backticks and escaped `\\$(` gave 5
    false finds; the 2 real ones, merges looped inside `"$(...)"`, were not."""
    out = []
    for m in re.finditer(r"(?<!\\)\$\(", token):
        depth, rest = 1, token[m.end():]
        for i, ch in enumerate(rest):
            depth += (ch == "(") - (ch == ")")
            if depth == 0:
                out.append(rest[:i])
                break
    return [s for s in out if _PR_VERB.search(s)]


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
    parts = (_values(verb, args, "--title", "t") + _values(verb, args, "--body", "b")
             + _values(verb, args, "--subject"))
    # Every body file, not the first: gh reads the last of a repeated -F, and
    # one in a group (`-sF b.md`) was never read at all.
    for body_file in _values(verb, args, "--body-file", "F"):
        if body_file != "-":               # stdin: main() checks the heredoc
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
# The body on stdin is visible only when the heredoc belongs to the gh command
# itself (no `;`, `&` or `|` between them), a heredoc is piped straight into it
# (`cat <<'EOF' | gh pr create --body-file -`), or a PowerShell here-string is.
# A heredoc for another command later on the line let a piped body through.
_STDIN_BODY = re.compile(
    r"\b" + _PR_VERB_TEXT + r"[^\n;&|]*?(?<![^\s|;&(])<<(?!<)"
    r"|(?<![^\s|;&(])<<(?!<)-?\s*['\"]?\w+['\"]?[^\n;&|]*\|\s*gh\s+pr\b"
    r"|^\s*['\"]@\s*\|\s*gh\s+pr\b", re.MULTILINE)
_READS_STDIN = re.compile(r"(?:--body-file|-[A-Za-z]*F)(?:\s+|=)-(?!\S)")


def _stdin_visible(stripped: str) -> bool:
    """A heredoc or here-string reaches the command that reads `--body-file -`:
    the flag is in the match or in the rest of that command, so a heredoc on
    another `gh pr` command does not vouch for a body piped from a file (#69)."""
    for m in _STDIN_BODY.finditer(stripped):
        rest = re.match(r"[^\n;&|]*", stripped[m.end():]).group(0)
        if _READS_STDIN.search(m.group(0) + rest):
            return True
    return False


_XARGS = re.compile(r"\bxargs\b[^;&|\n]*\b" + _PR_VERB_TEXT)
_GH_HOST = re.compile(r"\bGH_HOST=|\$env:GH_HOST\s*=", re.IGNORECASE)

# A `gh pr` command written inside one argument to a shell (`bash -c '...'`,
# `eval "..."`, `ssh host '...'`, `Invoke-Expression "..."`) or in a heredoc fed
# to one runs, and the gate never sees its args. Text that only mentions one is
# fine: a title, body or commit message, a grep pattern, a heredoc written to a
# file or fed to gh as its body. Python is not counted as a shell: the live gate
# blocked a patch script whose comment mentioned a merge (2026-10-26).
_PR_VERB = re.compile(r"\b" + _PR_VERB_TEXT)
_SHELL = re.compile(r"(?:(?:ba|z|da|k|fi|s)?sh|wsl|pwsh|powershell|cmd|iex"
                    r"|invoke-expression|eval|source)(?:\.exe)?", re.IGNORECASE)
_PROSE_FLAGS = {"-t", "--title", "-b", "--body", "--subject", "-m", "--message"}


def _is_shell_word(token: str) -> bool:
    return _SHELL.fullmatch(re.split(r"[\\/]", token)[-1]) is not None


# Words that run the command after them (`env bash -c`, `wsl -- bash -c`,
# `timeout 60 sh -c`), each with its options that take a value. `timeout` also
# takes a duration. `wsl` with nothing after it runs the default shell.
_WRAPPERS = {
    "env": {"-u", "--unset", "-C", "--chdir"},
    "sudo": {"-u", "-g", "-h", "-p", "-C", "-D", "-r", "-t", "-U", "-T"},
    "doas": {"-u", "-C"},
    "nice": {"-n", "--adjustment"},
    "timeout": {"-s", "--signal", "-k", "--kill-after"},
    "stdbuf": {"-i", "-o", "-e"},
    "xargs": {"-I", "-n", "-P", "-L", "-d", "-E", "-s", "-a"},
    "time": {"-f", "-o"},
    "exec": {"-a"},
    "wsl": {"-d", "--distribution", "-u", "--user", "--cd", "--shell-type"},
    **{w: set() for w in ("nohup", "command", "builtin", "!", "{", "then", "do",
                          "else", "elif", "if", "while", "until")},
}


def _command_word(words: list[str], i: int) -> int | None:
    """The index of the command a simple command starting at i runs: past
    assignments, keywords and wrappers with their options. None when it runs
    nothing, except a bare `wsl`, which is its own shell."""
    while i < len(words) and _kind(words[i]) == "word":
        w = words[i]
        name = _command_name(w)
        if _ASSIGNMENT.match(w):
            i += 1
            continue
        if name not in _WRAPPERS:
            return i
        start, i, positional = i, i + 1, int(name == "timeout")
        while i < len(words) and _kind(words[i]) == "word":
            a = words[i]
            if a == "--" or (name == "wsl" and a in ("-e", "--exec")):
                i += 1
                break
            if a.startswith("-") and a != "-":
                i += 2 if a in _WRAPPERS[name] else 1
            elif name == "env" and _ASSIGNMENT.match(a):
                i += 1
            elif positional:
                positional, i = 0, i + 1
            else:
                break
        if name == "wsl" and (i >= len(words) or _kind(words[i]) != "word"):
            return start
    return None


def _command_words(words: list[str]) -> list[int]:
    """The index of every command word: the first word of each statement,
    pipeline stage and group, read through _command_word."""
    out, i, at = [], 0, True
    while i < len(words):
        k = _kind(words[i])
        if k == "redirect":
            i += 2                      # the operator and its target
        elif k != "word":
            at, i = True, i + 1
        elif not at:
            i += 1
        elif (c := _command_word(words, i)) is None:
            while i < len(words) and _kind(words[i]) == "word":
                i += 1
        else:
            out.append(c)
            at, i = False, c + 1
    return out


def _statement_start(words: list[str], c: int) -> int:
    """Where the statement holding words[c] begins: after the last `&&`, `||`,
    `;`, `&` or newline before it that is outside any `( )` or `{ }` group, or
    at the group that encloses it."""
    depth = 0
    for i in range(c - 1, -1, -1):
        t = words[i]
        if t == "}":
            depth += 1
        elif t == "{":
            if depth == 0:
                return i + 1
            depth -= 1
        elif _kind(t) in ("stmt", "pipe", "group"):
            # Right to left within the token: in `\n)` the newline is inside
            # the group the `)` closes; in `);` the `;` is outside it.
            for j in range(len(t) - 1, -1, -1):
                ch = t[j]
                if ch == ")":
                    depth += 1
                elif ch == "(":
                    if depth == 0:
                        return i + 1
                    depth -= 1
                elif depth == 0 and (ch in ";\n" or (ch == "&" and t[j - 1:j] != "|")
                                     or (ch == "|" and "||" in t[max(j - 1, 0):j + 2])):
                    return i + 1
    return 0


def _command_name(word: str) -> str:
    """`/usr/bin/env` -> `env`, `C:\\...\\WSL.EXE` -> `wsl`."""
    return re.sub(r"\.exe$", "", re.split(r"[\\/]", word)[-1].lower())


# Commands whose arguments are patterns, files or text, never a command to run.
# A shell word after one is data (`grep ... | grep -v bash`). After any other
# command it may be run (`setsid bash`, `find -exec sh -c`), so it counts.
_TEXT_TOOLS = {"grep", "egrep", "fgrep", "rg", "ag", "ack", "findstr", "select-string",
               "sls", "sed", "awk", "gawk", "head", "tail", "sort", "uniq", "wc", "cut",
               "tr", "cat", "tee", "less", "more", "echo", "printf", "jq", "ls", "dir",
               "diff", "write-output", "write-host"}


def _fed_by_pipe(words: list[str], c: int) -> int | None:
    """The index of the pipe that feeds the stage holding command word c, or
    None. It looks out through a group that opens the stage: in `echo '...' |
    ( bash )` and `| { bash; }` the pipe feeds the group's shell (#82)."""
    i = c - 1
    while i >= 0:
        t, k = words[i], _kind(words[i])
        if k == "word" or (k == "group" and set(t) <= {"("}):
            i -= 1                      # wrappers, assignments, `{`, `(`
        else:
            return i if k == "pipe" else None
    return None


def _runs_pr(text: str, shell: str, depth: int) -> bool:
    """`text`, run as a command, runs `gh pr create/edit/merge`: directly, or
    through one more shell inside it (`bash -c "bash -c '...'"`)."""
    if not _PR_VERB.search(text):
        return False
    if _pr_commands(text, shell):
        return True
    if depth <= 0:
        return False
    stripped, bodies = _heredocs(text, shell)
    words = _words(stripped, shell)
    return _run_by_another_shell(words, _prose(words), bodies, shell, depth - 1) is not None


def _prose(tokens: list[str]) -> set[int]:
    """Indices of tokens that are a title, body, subject or message value."""
    out = set()
    for i, t in enumerate(tokens):
        if t in _PROSE_FLAGS:
            out.add(i + 1)
        elif "=" in t and t.split("=", 1)[0] in _PROSE_FLAGS:
            out.add(i)
    return out


def _run_by_another_shell(words: list[str], prose: set[int], bodies: list[tuple[str, str]],
                          shell: str, depth: int = 2) -> str | None:
    """The first `gh pr` command another shell would run, or None.

    A shell counts in its own simple command, never across a pipe or `&&`:
    `grep "gh pr merge" f | grep -v bash` runs nothing. In a simple command it
    counts as the command word (_command_words) or as any later word, since a
    wrapper the gate does not list still runs it (`setsid bash -c`, `find
    -exec sh -c`), unless the command is a text tool (_TEXT_TOOLS). It runs the
    arguments after it (`bash -c '...'`, `ssh host '...'`, `eval`) and, when a
    pipe feeds its stage, every word before that pipe in its statement (`echo
    '...' | bash`, `| setsid bash`, `| ( bash )`). An argument counts when it parses as a
    `gh pr` command, not just text that names one (`bash -c 'grep "gh pr
    create" f'`). A heredoc body counts when any word in what reads it (_owner)
    is a shell, except a title or body.

    A `gh pr` command kept in a variable (`CMD='gh pr merge 5'`) runs wherever
    a shell expands it (`eval "$CMD"`, on the next line or after `;`). The gate
    cannot trace the variable, so such an assignment beside any shell word in
    the command fails closed. 79acb4ca blocked the newline and prefix forms by
    accident, and the first command-word reading lost them (#82).
    """
    held = [w for i, w in enumerate(words) if i not in prose and _kind(w) == "word"
            and _ASSIGNMENT.match(w) and _runs_pr(w.split("=", 1)[1], shell, depth)]
    if held and any(_kind(w) == "word" and _is_shell_word(w) for w in words):
        return held[0]
    for c in _command_words(words):
        end = c + 1
        while end < len(words) and _kind(words[end]) in ("word", "redirect"):
            end += 1
        later = _command_name(words[c]) not in _TEXT_TOOLS
        shells = [s for s in range(c, end) if s not in prose and (s == c or later)
                  and _kind(words[s]) == "word" and _is_shell_word(words[s])]
        if not shells:
            continue
        given = list(range(shells[0] + 1, end))
        if (pipe := _fed_by_pipe(words, c)) is not None:
            given += range(_statement_start(words, pipe), pipe)
        for i in given:
            if i not in prose and _kind(words[i]) == "word" and _runs_pr(words[i], shell, depth):
                return words[i]
    for around, body in bodies:
        if _runs_pr(body, shell, depth):
            reads = _words(around, shell)
            prose_here = _prose(reads)
            if any(_kind(w) == "word" and _is_shell_word(w) and i not in prose_here
                   and (i == 0 or _kind(reads[i - 1]) != "redirect")    # `<<SH`, `> sh.log`
                   for i, w in enumerate(reads)):
                return around.split("\n")[0]
    return None


_ASSIGNMENT = re.compile(r"^[A-Za-z_]\w*=")
# The variable, in any form a shell names it (`GH_REPO=`, `$GH_REPO`,
# `${GH_REPO}`, `$env:GH_REPO`, `unset GH_REPO`), not a path that contains the
# letters: `cd ~/gh_repos/x` and `notes/gh_repo.md` blocked as GH_REPO (#82).
_GH_REPO_NAME = re.compile(r"(?<![\w./\\-])GH_REPO(?![\w./\\-])", re.IGNORECASE)


def _unmodelled_gh_repo(words: list[str], prose: set[int]) -> bool:
    """True when GH_REPO appears in any form but a `GH_REPO=o/r cmd` prefix.

    The prefix binds the one command it precedes, and _pr_commands turns it
    into -R. Every other form (`export`, `declare -x`, `set -a`, `unset`,
    `$env:GH_REPO`, an assignment on its own line that updates an already
    exported GH_REPO) depends on order and on state the gate cannot see. Each
    was modelled or missed in turn, and each model had a gap (#69). The words
    keep newlines, so each assignment is judged where it stands: a regex over
    the whole command let a bare `GH_REPO=o/r` line pass when the same value
    was a real prefix elsewhere (#82).
    """
    for k, t in enumerate(words):
        if k in prose or _kind(t) != "word" or not _GH_REPO_NAME.search(t):
            continue
        if not t.startswith("GH_REPO="):
            return True
        j = k + 1
        while j < len(words) and _ASSIGNMENT.match(words[j]):
            j += 1
        if j >= len(words) or _kind(words[j]) != "word":
            return True
    return False


# PowerShell is the primary shell in these sessions, and `gh` is on its PATH. A
# gate that answered only to Bash let any merge typed there through unread.
_SHELL_TOOLS = {"Bash", "PowerShell"}


def main() -> int:
    payload = json.loads(sys.stdin.buffer.read().decode("utf-8") or "{}")
    if payload.get("tool_name") not in _SHELL_TOOLS:
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    shell = payload.get("tool_name")
    # Whole-command signals are read with heredoc bodies removed: a PR body that
    # says "GH_REPO=..." or "xargs gh pr merge" is prose, not a setting.
    stripped, bodies = _heredocs(command, shell)
    words = _words(stripped, shell)
    prose = _prose(words)
    if hidden := _run_by_another_shell(words, prose, bodies, shell):
        # Checked before `found`: a merge run this way is never found at all.
        print("closing_keyword_gate: a `gh pr create/edit/merge` is handed to another "
              f"shell (\"{' '.join(hidden.split())[:80]}\"), so the gate cannot read the "
              "command it runs. Run the `gh pr` command directly.", file=sys.stderr)
        return 2
    found = _pr_commands(command, shell)
    if not found:
        return 0
    if _unmodelled_gh_repo(words, prose):
        print("closing_keyword_gate: GH_REPO is set other than as a `GH_REPO=owner/repo "
              "gh pr ...` prefix, so the gate cannot tell which repo each `gh pr` command "
              "reaches. Pass -R owner/repo to the `gh pr` command instead.", file=sys.stderr)
        return 2
    named = next((r for r in (_repos(v, a) for v, a, _ in found) if len(set(r)) > 1), None)
    if named:
        print("closing_keyword_gate: one `gh pr` command names more than one repo "
              f"({', '.join(dict.fromkeys(named))}); gh uses the last, so the gate cannot "
              "tell which repo to check. Run it as a plain one-line command with one: "
              "gh pr <verb> <n> -R owner/repo", file=sys.stderr)
        return 2
    if sum("-" in _values(v, a, "--body-file", "F") for v, a, _ in found) > 1:
        # Whether stdin is visible was decided for the whole command, so one
        # command's heredoc vouched for another's piped body (#69).
        print("closing_keyword_gate: more than one `gh pr` command reads `--body-file -`; "
              "the gate cannot tell which body feeds which. Run each on its own.",
              file=sys.stderr)
        return 2
    if _GH_HOST.search(stripped):
        print("closing_keyword_gate: GH_HOST points gh at another host, whose issues "
              "the gate does not read. Run the `gh pr` command without it.", file=sys.stderr)
        return 2
    if _XARGS.search(stripped):
        # `... | xargs -n1 gh pr merge` gives gh its PR on stdin, so the gate
        # would read the current branch's PR instead of the ones being merged.
        print("closing_keyword_gate: a `gh pr` command fed by xargs names PRs the "
              "gate cannot see. Run each `gh pr merge <n>` on its own.", file=sys.stderr)
        return 2
    verb = "/".join(dict.fromkeys(v for v, _, _ in found))
    shell_vars = _shell_vars(stripped)
    base = payload.get("cwd") or os.getcwd()
    checks = []
    try:
        for v, args, cd in found:
            target_dir = _local_path(_expand(cd, shell_vars)) if cd else None
            cwd = (os.path.normpath(os.path.join(base, os.path.expanduser(target_dir)))
                   if target_dir else base)
            repo_flag = (_repos(v, args) or [None])[-1]    # the one gh uses: the last
            repo = ("-R", _expand(repo_flag, shell_vars)) if repo_flag else ()
            target = _target(v, args)
            if "-" in _values(v, args, "--body-file", "F") and not _stdin_visible(stripped):
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
