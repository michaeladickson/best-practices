"""The practice updater extracts once across every doc and routes each idea to one.

It used to run extraction per doc, blind to the others, so one article whose keywords
matched several docs was mined once per doc. The 2026-09-18 run wrote comprehension
debt, the coordinator agent, compaction integrity and provider variability into two
docs each. No network, no Gemini calls.
"""
import json

from digest import practice_updater as pu

DOC = """# {title}

## Best Practices

### {practice}

Body.

## Sources

- **Old Article** (Somebody) — a phrase. Digest: 2026-09-01.
"""
A = {"path": "a.md", "topic": "A", "keywords": ["alpha"]}
B = {"path": "b.md", "topic": "B", "keywords": ["beta"]}
POST_AB = {"link": "https://example.test/ab", "title": "alpha beta", "content_preview": "x"}
POST_B = {"link": "https://example.test/b", "title": "beta only", "content_preview": "x"}


class _Resp:
    def __init__(self, text):
        self.text = text


class _Client:
    """Records extraction prompts and replies with a fixed JSON body."""

    def __init__(self, body):
        self.body, self.prompts = body, []
        self.models = self

    def generate_content(self, model, contents, config=None):
        self.prompts.append(contents)
        return _Resp(self.body)


def _setup(tmp_path, monkeypatch, body):
    (tmp_path / "a.md").write_text(DOC.format(title="A", practice="Keep alpha tidy"), encoding="utf-8")
    (tmp_path / "b.md").write_text(DOC.format(title="B", practice="Prune the beta toolkit"), encoding="utf-8")
    monkeypatch.setattr(pu, "REPO_ROOT", tmp_path)
    integrated = {}

    def fake_integrate(client, doc_text, topic, candidates, fix_note=""):
        integrated[topic] = [c["practice"] for c in candidates]
        return doc_text.replace("## Sources", "### New thing\n\nBody.\n\n## Sources")

    monkeypatch.setattr(pu, "_integrate", fake_integrate)
    client = _Client(body)
    return client, integrated


def _cand(doc, url, practice="Do the new thing", confidence="high"):
    return {"doc": doc, "practice": practice, "source_url": url, "confidence": confidence}


def test_one_extraction_call_sees_every_doc(tmp_path, monkeypatch):
    client, _ = _setup(tmp_path, monkeypatch, json.dumps({"candidates": []}))
    pu._run_docs([A, B], [], [POST_AB, POST_B], {}, True, lambda: client)
    assert len(client.prompts) == 1
    assert "Keep alpha tidy" in client.prompts[0] and "Prune the beta toolkit" in client.prompts[0]


def test_candidate_lands_only_in_its_routed_doc(tmp_path, monkeypatch):
    body = json.dumps({"candidates": [_cand("b.md", POST_AB["link"])]})
    client, integrated = _setup(tmp_path, monkeypatch, body)
    results = pu._run_docs([A, B], [], [POST_AB, POST_B], {}, True, lambda: client)
    by_doc = {r["doc"]: r["status"] for r in results}
    assert by_doc == {"a.md": "no_candidates", "b.md": "would_update"}
    assert integrated == {"B": ["Do the new thing"]}


def test_candidate_from_an_article_the_doc_already_saw_is_dropped(tmp_path, monkeypatch):
    # b.md's ledger already holds the article, so routing it there would integrate the
    # same source into the same doc twice.
    body = json.dumps({"candidates": [_cand("b.md", POST_AB["link"])]})
    client, integrated = _setup(tmp_path, monkeypatch, body)
    ledger = {"b.md": [POST_AB["link"]]}
    pu._run_docs([A, B], [], [POST_AB, POST_B], ledger, True, lambda: client)
    assert integrated == {}


def test_unknown_doc_and_low_confidence_are_dropped(tmp_path, monkeypatch):
    body = json.dumps({"candidates": [_cand("nope.md", POST_AB["link"]),
                                      _cand("a.md", POST_AB["link"], confidence="low")]})
    client, integrated = _setup(tmp_path, monkeypatch, body)
    pu._run_docs([A, B], [], [POST_AB, POST_B], {}, True, lambda: client)
    assert integrated == {}


def test_doc_with_nothing_new_is_still_shown_as_covered(tmp_path, monkeypatch):
    # a.md has no unseen articles, so it is not a target, but its practices must still
    # be in the prompt or the model re-proposes them for b.md.
    client, _ = _setup(tmp_path, monkeypatch, json.dumps({"candidates": []}))
    results = pu._run_docs([A, B], [], [POST_B], {}, True, lambda: client)
    assert {r["doc"]: r["status"] for r in results}["a.md"] == "no_new_articles"
    assert "Keep alpha tidy" in client.prompts[0]
    assert "Covered-only" in client.prompts[0]


def test_unparseable_extraction_blocks_and_marks_nothing_seen(tmp_path, monkeypatch):
    client, _ = _setup(tmp_path, monkeypatch, "not json at all")
    ledger = {}
    results = pu._run_docs([A, B], [], [POST_AB, POST_B], ledger, False, lambda: client)
    assert all(r["status"].startswith("error:") for r in results)
    assert ledger == {}, "a parse failure must not mark the week's articles seen"


def test_quiet_week_marks_considered_articles_seen(tmp_path, monkeypatch):
    client, _ = _setup(tmp_path, monkeypatch, json.dumps({"candidates": []}))
    ledger = {}
    pu._run_docs([A, B], [], [POST_AB, POST_B], ledger, False, lambda: client)
    assert ledger == {"a.md": [POST_AB["link"]],
                      "b.md": sorted([POST_AB["link"], POST_B["link"]])}


def test_no_targets_means_no_llm_call(tmp_path, monkeypatch):
    client, _ = _setup(tmp_path, monkeypatch, json.dumps({"candidates": []}))
    pu._run_docs([A, B], [], [], {}, True, lambda: client)
    assert client.prompts == []
