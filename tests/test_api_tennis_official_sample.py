from __future__ import annotations

from scripts.select_api_tennis_official_sample import select_sample


def test_selection_is_order_and_outcome_independent() -> None:
    candidates = [
        {"tour": "WTA", "event_date": "2026-05-02", "event_key": 1, "winner_side": "A"},
        {"tour": "WTA", "event_date": "2026-05-03", "event_key": 2, "winner_side": "B"},
        {"tour": "WTA", "event_date": "2026-06-01", "event_key": 3, "winner_side": "A"},
        {"tour": "ATP", "event_date": "2026-05-02", "event_key": 4, "winner_side": "B"},
    ]
    selected, denominators = select_sample(candidates, seed="fixed", per_tour_month=1)
    changed = [dict(row, winner_side="A") for row in reversed(candidates)]
    repeated, _ = select_sample(changed, seed="fixed", per_tour_month=1)
    assert [(row["tour"], row["event_key"]) for row in selected] == [
        (row["tour"], row["event_key"]) for row in repeated
    ]
    assert denominators == {"ATP:2026-05": 1, "WTA:2026-05": 2, "WTA:2026-06": 1}


def test_selection_requires_a_fixed_seed_and_positive_size() -> None:
    for seed, count in (("", 1), ("fixed", 0)):
        try:
            select_sample([], seed=seed, per_tour_month=count)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid selection parameters were accepted")
