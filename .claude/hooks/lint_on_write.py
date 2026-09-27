#!/usr/bin/env python3
"""Hook: report pyflakes errors that a batch of edits INTRODUCED and left in place.

Canonical copy lives in best-practices/.claude/hooks/lint_on_write.py; repos carry
an identical copy. Change it there first.

What it does
------------
Two halves, one script, dispatched on the hook payload:

- **Record** (PostToolUse on Edit / Write / MultiEdit): note the ``.py`` file in a
  per-session pending list and say nothing.
- **Settle** (PostToolUse on Bash, and Stop / SubagentStop): for every pending
  file, run ``ruff check --select F,E9`` on the file as it is now AND as it is at
  ``HEAD``, and report only the violations that are new. Exit 2 puts the report
  in front of Claude, so an invented name (F821), a leftover import (F401), a dead
  variable (F841) or a shadowed redefinition (F811) is fixed in the same turn
  instead of surfacing in CI, in review, or never. The pending list is cleared,
  so each finding is reported once.

Why settle later instead of after every edit
--------------------------------------------
A change often spans several edits, and the file is wrong in between: the use of
a name lands one edit before its import. Checked after every edit, that
intermediate state read as a blocking error dozens of times a day across five
sessions (2026-09-26, crumbl-ops#2913), and sessions learned to skim the
message. Bash (tests, a commit) and the end of a turn are the points where the
file's state starts to matter, and reads between edits are not. So the check
waits for those, and an error a later edit already fixed is never shown.

Why new-only, and why not "lines I changed"
-------------------------------------------
Three of the four repos this was written for carry an F-rule backlog (crumbl-ops
107 across 46 files, 2026-09-21). Linting the whole file would re-report that
backlog on every edit, and a gate that is always red gets ignored. So the
baseline is subtracted.

Filtering by changed line numbers was rejected: removing the last use of an
import creates an F401 on a line the edit never touched, and a line filter
misses exactly that. Instead violations are matched as a multiset on
``(code, message)`` with line numbers normalised out of the message, so shifted
lines do not read as new and a genuinely new instance of an old kind still does.

Failure modes are deliberately loud-but-harmless
------------------------------------------------
- ruff not importable, or a path this interpreter cannot see: one non-blocking
  notice per session (exit 1) at record time, then silence. A gate that quietly
  does not exist is the failure this hook family was written to end; a gate that
  nags on every edit gets deleted.
- any internal error: exit 1 (non-blocking, visible in the transcript). An edit
  or a command is never blocked because the linter broke.
"""
from __future__ import annotations

import collections
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

RULES = "F,E9"
TIMEOUT = 20
EDIT_TOOLS = frozenset({"Edit", "Write", "MultiEdit"})
SETTLE_EVENTS = frozenset({"Stop", "SubagentStop"})
_LINE_REF = re.compile(r"\bline \d+\b")
_UNSAFE = re.compile(r"[^A-Za-z0-9_.-]")


def _ruff_bin() -> list[str]:
    # Call the ruff binary directly: `python -m ruff` starts a second interpreter
    # only to exec the same binary, which was ~200ms per call, twice per edit.
    try:
        from ruff.__main__ import find_ruff_bin
        return [str(find_ruff_bin())]
    except Exception:  # noqa: BLE001 — older/odd installs: fall back, never fail
        return [sys.executable, "-m", "ruff"]


def _ruff(args: list[str], stdin: str | None = None, cwd: str | None = None):
    return subprocess.run(
        [*_ruff_bin(), *args],
        input=stdin, capture_output=True, text=True, encoding="utf-8",
        timeout=TIMEOUT, cwd=cwd,
    )


def _ruff_available() -> bool:
    # In-process check of the same interpreter that `-m ruff` will use: spawning
    # `ruff --version` for this cost ~300ms on every .py edit.
    return importlib.util.find_spec("ruff") is not None


def _check(path: str, cwd: str, content: str | None = None) -> list[dict]:
    """Violations for `path`; when `content` is given, lint it via stdin as if it
    were `path`, so per-file-ignores and excludes resolve exactly as for the file."""
    base = ["check", "--no-cache", "--force-exclude", "--select", RULES,
            "--output-format", "json", "--exit-zero"]
    if content is None:
        p = _ruff(base + [path], cwd=cwd)
    else:
        p = _ruff(base + ["--stdin-filename", path, "-"], stdin=content, cwd=cwd)
    out = (p.stdout or "").strip()
    return json.loads(out) if out else []


def _key(v: dict) -> tuple[str, str]:
    return (v.get("code") or "syntax", _LINE_REF.sub("line N", v.get("message", "")))


def _git(args: list[str], cwd: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=TIMEOUT)


def _head_content(path: Path) -> str | None:
    """The file at HEAD, or None if it is new, untracked, or not in a repo."""
    d = str(path.parent)
    top = _git(["rev-parse", "--show-toplevel"], d)
    if top.returncode != 0:
        return None
    rel = os.path.relpath(path, top.stdout.strip()).replace(os.sep, "/")
    show = _git(["show", f"HEAD:{rel}"], top.stdout.strip())
    return show.stdout if show.returncode == 0 else None


def _state_file(session: str, suffix: str) -> Path:
    name = _UNSAFE.sub("_", session or "nosession")
    return Path(tempfile.gettempdir()) / f"lint_on_write_{name}.{suffix}"


def _notice_once(session: str, msg: str) -> int:
    marker = _state_file(session, "notice")
    if marker.exists():
        return 0
    try:
        marker.write_text("1", encoding="utf-8")
    except OSError:
        pass
    print(msg, file=sys.stderr)
    return 1


def _new_violations(path: Path) -> list[dict]:
    """Violations in `path` now that are not in its HEAD version."""
    cwd = str(path.parent)
    now = _check(str(path), cwd)
    if not now:
        return []
    head = _head_content(path)
    before: collections.Counter = collections.Counter()
    if head:
        before.update(_key(v) for v in _check(str(path), cwd, head))
    new: list[dict] = []
    for v in sorted(now, key=lambda v: (v["location"]["row"], v["location"]["column"])):
        k = _key(v)
        if before[k] > 0:
            before[k] -= 1          # a pre-existing instance; consume one
        else:
            new.append(v)
    return new


def _record(data: dict) -> int:
    fp = (data.get("tool_input") or {}).get("file_path") or ""
    if not fp.endswith(".py"):
        return 0
    session = data.get("session_id", "")
    if not Path(fp).is_file():
        # The tool just wrote this file, so "not found" means this interpreter
        # sees paths differently (an MSYS /tmp path under a Windows Python, a WSL
        # path under a Windows harness). Returning 0 here made the gate vanish
        # silently -- found by exactly that mismatch in testing. Say so, once.
        return _notice_once(session,
                            f"lint_on_write: {sys.executable} cannot see {fp} "
                            "(path translation?); write-time pyflakes checks are OFF "
                            "for paths like this one this session.")
    if not _ruff_available():
        return _notice_once(session,
                            f"lint_on_write: ruff is not importable by {sys.executable}; "
                            "write-time pyflakes checks are OFF this session "
                            "(install with `python3 -m pip install ruff`).")
    # One line per edit, appended: parallel tool calls each add their own line
    # rather than racing a read-modify-write of a shared list.
    with open(_state_file(session, "pending"), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(fp) + "\n")
    return 0


def _settle(data: dict) -> int:
    pending = _state_file(data.get("session_id", ""), "pending")
    if not pending.exists():
        return 0
    # Claim the list before reading it, so an edit recorded while this runs goes
    # to a fresh list and is settled next time instead of being lost.
    claimed = pending.with_name(f"{pending.name}.{os.getpid()}")
    try:
        os.replace(pending, claimed)
    except OSError:
        return 0
    try:
        lines = claimed.read_text(encoding="utf-8").splitlines()
    finally:
        claimed.unlink(missing_ok=True)
    files = list(dict.fromkeys(json.loads(line) for line in lines if line.strip()))
    if not _ruff_available():
        return 0

    report: list[str] = []
    count = 0
    for fp in files:
        path = Path(fp)
        if not path.is_file():      # deleted or renamed since the edit
            continue
        new = _new_violations(path)
        count += len(new)
        report += [f"  {fp}:{v['location']['row']}:{v['location']['column']}  "
                   f"{v.get('code') or 'syntax'}  {v.get('message', '')}" for v in new]
    if not report:
        return 0
    print(f"lint_on_write: your edits left {count} pyflakes error(s) that are not "
          f"present at HEAD. Fix them before moving on:\n" + "\n".join(report),
          file=sys.stderr)
    return 2


def main() -> int:
    data = json.load(sys.stdin)
    if (data.get("hook_event_name") not in SETTLE_EVENTS
            and data.get("tool_name") in EDIT_TOOLS):
        return _record(data)
    return _settle(data)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001 — never block an edit because the linter broke
        print(f"lint_on_write: internal error, check skipped ({type(e).__name__}: {e})",
              file=sys.stderr)
        sys.exit(1)
