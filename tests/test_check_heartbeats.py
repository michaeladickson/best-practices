"""check_heartbeats: a state file that exists must never read as "never run".

On 2026-11-09 the skills-sync run wrote state.json with a UTF-8 byte order mark.
json.load rejected it, the error was swallowed, and the job read PENDING ("no
state yet (never run?)"), which never alerts, so its dead-man's tell was blind.
"""
import json
from datetime import datetime, timedelta, timezone

import pytest

from scripts import check_heartbeats as hb


def _check(monkeypatch, path, max_age_days=9):
    monkeypatch.setattr(hb, "CHECKS", [{"name": "job", "type": "json_last_run",
                                        "path": str(path), "max_age_days": max_age_days}])
    return hb.run_checks()[0]


def _today():
    return datetime.now(timezone.utc).date().isoformat()


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig"])
def test_a_fresh_state_file_reads_ok_with_or_without_a_bom(monkeypatch, tmp_path, encoding):
    p = tmp_path / "state.json"
    p.write_text(json.dumps({"last_run": _today()}), encoding=encoding)
    assert _check(monkeypatch, p)[1] == "OK"


def test_an_old_state_file_with_a_bom_goes_stale(monkeypatch, tmp_path):
    p = tmp_path / "state.json"
    old = (datetime.now(timezone.utc) - timedelta(days=30)).date().isoformat()
    p.write_text(json.dumps({"last_run": old}), encoding="utf-8-sig")
    assert _check(monkeypatch, p)[1] == "STALE"


@pytest.mark.parametrize("content", ["{not json", "[]", '{"repos": {}}', '{"last_run": "soon"}'])
def test_a_state_file_that_cannot_be_read_is_unreadable_not_pending(monkeypatch, tmp_path,
                                                                    content):
    p = tmp_path / "state.json"
    p.write_text(content, encoding="utf-8")
    name, status, detail = _check(monkeypatch, p)
    assert status == "UNREADABLE" and str(p) in detail


def test_a_missing_state_file_is_still_pending(monkeypatch, tmp_path):
    assert _check(monkeypatch, tmp_path / "state.json")[1] == "PENDING"


def test_one_unreadable_file_in_a_glob_is_not_hidden_by_a_fresh_one(monkeypatch, tmp_path):
    (tmp_path / "a.json").write_text(json.dumps({"last_run": _today()}), encoding="utf-8")
    (tmp_path / "b.json").write_text("{not json", encoding="utf-8")
    assert _check(monkeypatch, tmp_path / "*.json")[1] == "UNREADABLE"


def test_unreadable_alerts_like_stale(monkeypatch, tmp_path, capsys):
    p = tmp_path / "state.json"
    p.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(hb, "CHECKS", [{"name": "job", "type": "json_last_run",
                                        "path": str(p), "max_age_days": 9}])
    filed = []
    monkeypatch.setattr(hb, "file_issue", lambda rows: filed.append(rows))
    monkeypatch.setattr(hb.sys, "argv", ["check_heartbeats.py"])
    with pytest.raises(SystemExit) as e:
        hb.main()
    assert e.value.code == 1 and filed and filed[0][0][1] == "UNREADABLE"
