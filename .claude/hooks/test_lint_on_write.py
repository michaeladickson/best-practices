"""End-to-end tests for lint_on_write.py: real git, real ruff, harness-shaped stdin.

Canonical copy lives next to the hook in best-practices/.claude/hooks/; repos that
carry the hook carry this file too. It finds the hook by walking up from its own
location to `.claude/hooks/lint_on_write.py`, so it runs unchanged in either place.

Each case builds a throwaway git repo, commits a baseline, edits the file, and
pipes the PostToolUse payload to the hook exactly as Claude Code would.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

if os.environ.get("CI"):
    # In CI a missing ruff must FAIL collection, not skip: a skipped suite is a
    # green check that tested nothing, which is how this would have shipped in a
    # repo whose CI installs only its runtime lock (wealth-mgmt, 2026-09-21).
    import ruff  # noqa: F401
else:
    pytest.importorskip("ruff", reason="lint_on_write needs ruff in the test interpreter")


def _find_hook() -> Path:
    for d in [Path(__file__).resolve().parent, *Path(__file__).resolve().parents]:
        cand = d / ".claude" / "hooks" / "lint_on_write.py"
        if cand.is_file():
            return cand
        cand = d / "lint_on_write.py"
        if cand.is_file():
            return cand
    raise FileNotFoundError("lint_on_write.py not found above this test")


HOOK = _find_hook()


@pytest.fixture
def repo(tmp_path):
    def git(*a):
        subprocess.run(["git", *a], cwd=tmp_path, check=True, capture_output=True)
    git("init", "-q")
    git("config", "user.email", "t@t")
    git("config", "user.name", "t")
    git("config", "core.autocrlf", "false")

    class R:
        root = tmp_path

        def write(self, name, text):
            (tmp_path / name).write_text(text, encoding="utf-8")
            return str(tmp_path / name)

        def commit(self):
            git("add", "-A")
            git("commit", "-qm", "c")
    return R()


def run(fp, *, no_ruff=False, session="s"):
    # `-S` drops site-packages, which is where ruff lives: a faithful stand-in
    # for "the interpreter the harness called has no ruff".
    cmd = [sys.executable, *(["-S"] if no_ruff else []), str(HOOK)]
    p = subprocess.run(cmd, input=json.dumps({"session_id": session, "tool_name": "Edit",
                       "tool_input": {"file_path": fp}}), capture_output=True, text=True)
    return p.returncode, p.stderr


def test_non_python_ignored(repo):
    assert run(repo.write("notes.md", "x"))[0] == 0


def test_new_file_invented_name_blocks(repo):
    rc, err = run(repo.write("new.py", "def f():\n    return undefined_thing\n"))
    assert rc == 2 and "F821" in err and "undefined_thing" in err


def test_legacy_debt_clean_edit_is_silent(repo):
    repo.write("m.py", "import os\n\n\ndef g():\n    return 1\n")
    repo.commit()
    assert run(repo.write("m.py", "import os\n\n\ndef g():\n    return 2\n"))[0] == 0


def test_new_violation_reported_legacy_not(repo):
    repo.write("m.py", "import os\n\n\ndef g():\n    return 1\n")
    repo.commit()
    rc, err = run(repo.write("m.py", "import os\n\n\ndef g():\n    unused = 5\n    return 2\n"))
    assert rc == 2 and "F841" in err and "F401" not in err


def test_shifted_lines_do_not_read_as_new(repo):
    repo.write("m.py", "import os\n\n\ndef g():\n    return 1\n")
    repo.commit()
    shifted = '"""doc."""\n' + "\n" * 8 + "import os\n\n\ndef g():\n    return 2\n"
    assert run(repo.write("m.py", shifted))[0] == 0


def test_removing_last_use_flags_untouched_import_line(repo):
    """The case a changed-lines filter misses: the edit never touches line 1."""
    repo.write("m.py", "import json\n\n\ndef h():\n    return json.dumps(1)\n")
    repo.commit()
    rc, err = run(repo.write("m.py", "import json\n\n\ndef h():\n    return 1\n"))
    assert rc == 2 and "F401" in err and "json" in err


def test_line_number_in_message_is_normalised(repo):
    """F811 says 'from line N'; a shift must not make legacy F811 look new."""
    repo.write("m.py", "def a():\n    return 1\n\n\ndef a():\n    return 2\n")
    repo.commit()
    shifted = "\n\n\ndef a():\n    return 1\n\n\ndef a():\n    return 2\n"
    assert run(repo.write("m.py", shifted))[0] == 0


def test_second_instance_of_same_kind_is_new(repo):
    repo.write("m.py", "import os\n")
    repo.commit()
    rc, err = run(repo.write("m.py", "import os\nimport sys\n"))
    assert rc == 2 and "`sys`" in err and "`os`" not in err


def test_syntax_error_blocks(repo):
    repo.write("m.py", "x = 1\n")
    repo.commit()
    rc, err = run(repo.write("m.py", "def g(:\n    return 2\n"))
    assert rc == 2 and "syntax" in err


def test_ruff_missing_notices_once_then_quiet(repo):
    fp = repo.write("m.py", "x = 1\n")
    sess = f"nr{os.getpid()}{id(repo)}"
    rc1, err1 = run(fp, no_ruff=True, session=sess)
    rc2, _ = run(fp, no_ruff=True, session=sess)
    assert (rc1, rc2) == (1, 0) and "OFF this session" in err1


def test_unseen_path_is_loud_not_a_silent_pass():
    rc, err = run("/definitely/not/a/real/place.py", session=f"up{os.getpid()}")
    assert rc == 1 and "cannot see" in err


def test_outside_any_repo_all_violations_are_new(tmp_path):
    fp = tmp_path / "o.py"
    fp.write_text("import os\n", encoding="utf-8")
    rc, err = run(str(fp))
    assert rc == 2 and "F401" in err


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
