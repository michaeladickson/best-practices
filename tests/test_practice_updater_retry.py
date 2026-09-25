"""The practice updater's one retry on a title-level validation rejection.

llm-evaluation.md was blocked on 2026-08-28 and 2026-09-18 because the model wrote
two new practice titles sharing a 3-word lead. A rejection discards the doc's whole
week and needs a human, so a title rejection now gets one retry with the reason
attached. Structural rejections must still block. No network, no Gemini calls.
"""
from digest import practice_updater as pu

DOC = """# Topic

## Best Practices

### Keep the existing practice

Body.

## Sources

- **Some Article** (Somebody) — a phrase. Digest: 2026-09-01. [link](https://example.test/x)
"""
POSTS = [{"link": "https://example.test/a", "title": "a", "content_preview": "x"}]


def _with_practices(*titles):
    added = "".join(f"### {t}\n\nBody.\n\n" for t in titles)
    return DOC.replace("## Sources", added + "## Sources")


DUPED = _with_practices("Evaluate agent performance under production load",
                        "Evaluate agent performance against business outcomes")
FIXED = _with_practices("Evaluate agent performance under production load",
                        "Tie agent evaluation to business outcomes")
LINKS_DROPPED = _with_practices("A new practice").replace(
    "[link](https://example.test/x)", "[link]")


def _run(tmp_path, monkeypatch, *outputs):
    (tmp_path / "doc.md").write_text(DOC, encoding="utf-8")
    calls = []
    script = list(outputs)

    def fake_integrate(client, doc_text, topic, candidates, fix_note=""):
        calls.append(fix_note)
        return script.pop(0)

    monkeypatch.setattr(pu, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(pu, "_keyword_prefilter", lambda posts, kw: posts)
    monkeypatch.setattr(pu, "_extract_candidates",
                        lambda *a, **k: [{"doc": "doc.md", "practice": "p", "source_url": "u"}])
    monkeypatch.setattr(pu, "_integrate", fake_integrate)
    doc = {"path": "doc.md", "topic": "Topic", "keywords": []}
    [result] = pu._run_docs([doc], [], POSTS, {}, dry_run=True, get_client=lambda: None)
    return result, calls


def test_duplicate_title_is_retried_with_the_reason_and_can_succeed(tmp_path, monkeypatch):
    result, calls = _run(tmp_path, monkeypatch, DUPED, FIXED)
    assert result["status"] == "would_update"
    assert len(calls) == 2
    assert calls[0] == "" and calls[1].startswith("new duplicate practice heading")


def test_a_second_title_rejection_still_blocks(tmp_path, monkeypatch):
    result, calls = _run(tmp_path, monkeypatch, DUPED, DUPED)
    assert result["status"].startswith("rejected:new duplicate practice heading")
    assert len(calls) == 2, "exactly one retry, not a loop"


def test_dropping_where_used_content_is_rejected():
    old = DOC + "\n## Where Used\n\n- **crumbl-ops** — hand-written.\n\n### Audit\n\n- detail\n"
    grown_but_lossy = _with_practices("A new practice") + "\n## Where Used\n\n- detail\n"
    ok, reason = pu._validate(old, grown_but_lossy, [])
    assert not ok and reason.startswith("Where Used content dropped")
    kept = _with_practices("A new practice") + old[len(DOC):]
    assert pu._validate(old, kept, [])[0]


def test_structural_rejection_is_not_retried(tmp_path, monkeypatch):
    result, calls = _run(tmp_path, monkeypatch, LINKS_DROPPED)
    assert result["status"].startswith("rejected:markdown links dropped")
    assert len(calls) == 1
