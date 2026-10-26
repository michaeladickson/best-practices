"""Only models we run or might migrate to file a pricing issue.

Five issues in five weeks (2026-09-18 to 2026-10-24) carried kimi-k3 re-rates, and four
carried nothing else. Every group still reaches the weekly table. No network.
"""
from digest import model_pricing as mp


def _snap(**rows):
    return {"models": rows}


def _row(group, inp, out):
    return {"group": group, "input": inp, "output": out}


OLD = _snap(**{
    "moonshotai/kimi-k3": _row("Open weight", 2.70, 13.50),
    "google/gemini-3.8-flash": _row("Google (migration targets)", 0.75, 3.75),
    "google/gemini-2.5-flash": _row("Google (in use)", 0.30, 2.50),
})


def test_open_weight_moves_are_reported_but_not_filed():
    new = {"moonshotai/kimi-k3": _row("Open weight", 0.30, 11.94),
           "google/gemini-3.8-flash": _row("Google (migration targets)", 0.75, 3.75),
           "google/gemini-2.5-flash": _row("Google (in use)", 0.30, 2.50)}
    assert len(mp.diff(OLD, new)) == 2
    assert mp.diff(OLD, new, mp.ISSUE_GROUPS) == []


def test_a_move_on_a_model_we_run_or_target_is_filed():
    new = {"moonshotai/kimi-k3": _row("Open weight", 0.30, 11.94),
           "google/gemini-3.8-flash": _row("Google (migration targets)", 0.83, 4.12),
           "google/gemini-2.5-flash": _row("Google (in use)", 0.30, 3.00)}
    filed = mp.diff(OLD, new, mp.ISSUE_GROUPS)
    assert len(filed) == 3
    assert not any("kimi" in c for c in filed)


def test_every_issue_group_exists_in_the_watchlist():
    # A renamed group would silently stop filing for every model in it.
    assert mp.ISSUE_GROUPS <= set(mp.WATCHLIST)
