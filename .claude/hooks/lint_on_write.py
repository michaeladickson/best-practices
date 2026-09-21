#!/usr/bin/env python3
"""PostToolUse hook: report pyflakes errors that an edit INTRODUCED, at write time.

Canonical copy lives in best-practices/.claude/hooks/lint_on_write.py; repos carry
an identical copy. Change it there first.

What it does
------------
After Edit/Write on a ``.py`` file, run ``ruff check --select F,E9`` on the file as
it is now AND on the file as it is at ``HEAD``, and report only the violations
that are new. Exit 2 puts the report in front of Claude immediately, so an
invented name (F821), a leftover import (F401), a dead variable (F841) or a
shadowed redefinition (F811) is fixed in the same turn instead of surfacing in CI,
in review, or never (most repos do not lint scripts/ at all).

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
- ruff not importable: one non-blocking notice per session (exit 1), then
  silence. A gate that quietly does not exist is the failure this hook family
  was written to end; a gate that nags on every edit gets deleted.
- any internal error: exit 1 (non-blocking, visible in the transcript). The
  edit is never blocked because the linter broke.
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
_LINE_REF = re.compile(r"\bline \d+\b")


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


def _notice_once(session: str, msg: str) -> int:
    marker = Path(tempfile.gettempdir()) / f"lint_on_write_{session or 'nosession'}.notice"
    if marker.exists():
        return 0
    try:
        marker.write_text("1", encoding="utf-8")
    except OSError:
        pass
    print(msg, file=sys.stderr)
    return 1


def main() -> int:
    data = json.load(sys.stdin)
    fp = (data.get("tool_input") or {}).get("file_path") or ""
    if not fp.endswith(".py"):
        return 0
    path = Path(fp)
    if not path.is_file():
        # The tool just wrote this file, so "not found" means this interpreter
        # sees paths differently (an MSYS /tmp path under a Windows Python, a WSL
        # path under a Windows harness). Returning 0 here made the gate vanish
        # silently -- found by exactly that mismatch in testing. Say so, once.
        return _notice_once(data.get("session_id", ""),
                            f"lint_on_write: {sys.executable} cannot see {fp} "
                            "(path translation?); write-time pyflakes checks are OFF "
                            "for paths like this one this session.")
    if not _ruff_available():
        return _notice_once(data.get("session_id", ""),
                            f"lint_on_write: ruff is not importable by {sys.executable}; "
                            "write-time pyflakes checks are OFF this session "
                            "(install with `python3 -m pip install ruff`).")

    cwd = str(path.parent)
    now = _check(str(path), cwd)
    if not now:
        return 0
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
    if not new:
        return 0

    lines = [f"  {path.name}:{v['location']['row']}:{v['location']['column']}  "
             f"{v.get('code') or 'syntax'}  {v.get('message', '')}" for v in new]
    print(f"lint_on_write: your edit introduced {len(new)} pyflakes error(s) in {fp} "
          f"(not present at HEAD). Fix them before moving on:\n" + "\n".join(lines),
          file=sys.stderr)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001 — never block an edit because the linter broke
        print(f"lint_on_write: internal error, check skipped ({type(e).__name__}: {e})",
              file=sys.stderr)
        sys.exit(1)
