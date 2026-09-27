"""End-to-end tests for lint_on_write.py: real git, real ruff, harness-shaped stdin.

Canonical copy lives next to the hook in best-practices/.claude/hooks/; repos that
carry the hook carry this file too. It finds the hook by walking up from its own
location to `.claude/hooks/lint_on_write.py`, so it runs unchanged in either place.

Each case builds a throwaway git repo, commits a baseline, edits the file, and
pipes the hook payloads to the hook exactly as Claude Code would: a PostToolUse
Edit records the file, and a later Bash call or Stop settles it. The hook keeps
its per-session state in the temp dir, which each test points at its own
tmp_path, so no two tests share a pending list.
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
_STATE: dict[str, str] = {}


@pytest.fixture(autouse=True)
def _own_temp_dir(tmp_path):
    state = tmp_path / "hook-state"
    state.mkdir()
    _STATE["dir"] = str(state)


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()

    def git(*a):
        subprocess.run(["git", *a], cwd=root, check=True, capture_output=True)
    git("init", "-q")
    git("config", "user.email", "t@t")
    git("config", "user.name", "t")
    git("config", "core.autocrlf", "false")

    class R:
        def write(self, name, text):
            (root / name).write_text(text, encoding="utf-8")
            return str(root / name)

        def remove(self, name):
            (root / name).unlink()

        def commit(self):
            git("add", "-A")
            git("commit", "-qm", "c")
    return R()


def hook(payload: dict, *, no_ruff=False, session="s"):
    # `-S` drops site-packages, which is where ruff lives: a faithful stand-in
    # for "the interpreter the harness called has no ruff".
    cmd = [sys.executable, *(["-S"] if no_ruff else []), str(HOOK)]
    d = _STATE["dir"]
    env = {**os.environ, "TMPDIR": d, "TEMP": d, "TMP": d}
    p = subprocess.run(cmd, input=json.dumps({"session_id": session, **payload}),
                       capture_output=True, text=True, env=env)
    return p.returncode, p.stderr


def edit(fp, **kw):
    return hook({"hook_event_name": "PostToolUse", "tool_name": "Edit",
                 "tool_input": {"file_path": fp}}, **kw)


def bash(**kw):
    return hook({"hook_event_name": "PostToolUse", "tool_name": "Bash",
                 "tool_input": {"command": "pytest -q"}}, **kw)


def stop(**kw):
    return hook({"hook_event_name": "Stop", "stop_hook_active": False}, **kw)


def run(fp, *, no_ruff=False, session="s"):
    """One edit then the end of the turn: what a single-edit change reports."""
    rc, err = edit(fp, no_ruff=no_ruff, session=session)
    if rc != 0:
        return rc, err
    return stop(no_ruff=no_ruff, session=session)


# ── What counts as new (unchanged from the per-edit hook) ────────────────────
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
    rc1, err1 = run(fp, no_ruff=True)
    rc2, _ = run(fp, no_ruff=True)
    assert (rc1, rc2) == (1, 0) and "OFF this session" in err1


def test_unseen_path_is_loud_not_a_silent_pass():
    rc, err = run("/definitely/not/a/real/place.py")
    assert rc == 1 and "cannot see" in err


def test_outside_any_repo_all_violations_are_new(tmp_path):
    fp = tmp_path / "o.py"
    fp.write_text("import os\n", encoding="utf-8")
    rc, err = run(str(fp))
    assert rc == 2 and "F401" in err


# ── Settling at the end of a batch (#2913) ───────────────────────────────────
def test_an_edit_alone_reports_nothing(repo):
    assert edit(repo.write("m.py", "def f():\n    return json.dumps(1)\n")) == (0, "")


def test_an_import_added_one_edit_after_its_use_is_never_reported(repo):
    """The #2913 case: the use lands first, the import one edit later."""
    repo.write("m.py", "def f():\n    return 1\n")
    repo.commit()
    assert edit(repo.write("m.py", "def f():\n    return json.dumps(1)\n"))[0] == 0
    assert edit(repo.write("m.py", "import json\n\n\ndef f():\n    return json.dumps(1)\n"))[0] == 0
    assert bash() == (0, "")


def test_bash_settles_the_batch_and_reports_once(repo):
    fp = repo.write("m.py", "def f():\n    return undefined_thing\n")
    edit(fp)
    rc, err = bash()
    assert rc == 2 and "F821" in err and fp in err
    assert bash() == (0, "") and stop() == (0, "")


def test_stop_and_subagent_stop_both_settle(repo):
    edit(repo.write("a.py", "def f():\n    return nope\n"))
    assert stop()[0] == 2
    edit(repo.write("b.py", "def f():\n    return nope\n"))
    assert hook({"hook_event_name": "SubagentStop", "stop_hook_active": False})[0] == 2


def test_every_pending_file_is_reported_together(repo):
    a = repo.write("a.py", "def f():\n    return nope\n")
    b = repo.write("b.py", "import os\n")
    edit(a)
    edit(b)
    edit(a)
    rc, err = stop()
    assert rc == 2 and "2 pyflakes error(s)" in err and a in err and b in err
    assert err.count(a) == 1


def test_a_file_deleted_before_the_settle_is_skipped(repo):
    edit(repo.write("gone.py", "def f():\n    return nope\n"))
    repo.remove("gone.py")
    assert stop() == (0, "")


def test_sessions_do_not_settle_each_other(repo):
    edit(repo.write("m.py", "def f():\n    return nope\n"), session="one")
    assert stop(session="two") == (0, "")
    assert stop(session="one")[0] == 2


def test_nothing_pending_is_silent():
    assert bash() == (0, "") and stop() == (0, "")


def test_a_subagent_keeps_its_own_batch(repo):
    """Subagent hooks carry the parent's session_id plus their own agent_id."""
    fp = repo.write("m.py", "def f():\n    return nope\n")
    hook({"hook_event_name": "PostToolUse", "tool_name": "Edit", "agent_id": "a1",
          "tool_input": {"file_path": fp}})
    assert bash() == (0, "") and stop() == (0, "")          # the parent's settles
    rc, err = hook({"hook_event_name": "SubagentStop", "agent_id": "a1",
                    "stop_hook_active": False})
    assert rc == 2 and fp in err


def _pending(name="lint_on_write_s.pending") -> Path:
    return Path(_STATE["dir"]) / name


def test_an_entry_that_raises_is_dropped_and_the_rest_requeued(repo):
    fp = repo.write("m.py", "def f():\n    return nope\n")
    _pending().write_text("123\n" + json.dumps(fp) + "\n", encoding="utf-8")
    rc, err = stop()
    assert rc == 1 and "internal error" in err
    rc, err = stop()
    assert rc == 2 and fp in err
    assert stop() == (0, "")


def test_a_stale_claim_from_a_killed_settle_is_adopted(repo):
    fp = repo.write("m.py", "def f():\n    return nope\n")
    orphan = _pending("lint_on_write_s.pending.99999")
    orphan.write_text(json.dumps(fp) + "\n", encoding="utf-8")
    os.utime(orphan, (1, 1))
    rc, err = stop()
    assert rc == 2 and fp in err and not orphan.exists()


def test_a_fresh_claim_belongs_to_a_live_settle_and_is_left_alone(repo):
    fp = repo.write("m.py", "def f():\n    return nope\n")
    live = _pending("lint_on_write_s.pending.99999")
    live.write_text(json.dumps(fp) + "\n", encoding="utf-8")
    assert stop() == (0, "") and live.exists()


def test_settings_wire_both_halves():
    """Recording without a settle wired would silence the gate entirely."""
    settings = HOOK.parent.parent / "settings.json"
    if not settings.is_file():
        pytest.skip("no .claude/settings.json beside the hook")
    hooks = json.loads(settings.read_text(encoding="utf-8"))["hooks"]

    def matchers(event):
        return [m.get("matcher", "") for m in hooks.get(event, [])
                if any("lint_on_write.py" in h.get("command", "") for h in m["hooks"])]
    post = matchers("PostToolUse")
    assert len(post) == 1, post
    tools = set(post[0].split("|"))
    assert {"Edit", "Write", "MultiEdit", "Bash"} <= tools, post
    assert matchers("Stop") and matchers("SubagentStop")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
