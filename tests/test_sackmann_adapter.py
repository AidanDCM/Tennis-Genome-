from pathlib import Path

import pandas as pd

from tennis_genome.data.sackmann import load_sackmann_csv


def test_adapter_splits_pre_match_state_from_outcome(tmp_path: Path):
    path = tmp_path / "matches.csv"
    pd.DataFrame(
        [
            {
                "tourney_id": "2026-001",
                "tourney_name": "Test Open",
                "surface": "Hard",
                "tourney_level": "A",
                "tourney_date": 20260105,
                "match_num": 1,
                "winner_id": 200,
                "winner_name": "Winner Player",
                "winner_rank": 10,
                "winner_rank_points": 3000,
                "loser_id": 100,
                "loser_name": "Loser Player",
                "loser_rank": 20,
                "loser_rank_points": 1800,
                "score": "6-4 6-4",
                "best_of": 3,
                "round": "R32",
            }
        ]
    ).to_csv(path, index=False)

    match = load_sackmann_csv(path, tour="ATP")[0]

    assert match.pre_match.player_a_id == "atp:id:100"
    assert match.pre_match.player_b_id == "atp:id:200"
    assert match.pre_match.rank_a == 20
    assert match.pre_match.rank_b == 10
    assert match.outcome.a_won is False
    assert match.outcome.score == "6-4 6-4"


def test_adapter_marks_retirements_and_walkovers(tmp_path: Path):
    path = tmp_path / "matches.csv"
    base = {
        "tourney_id": "2026-001",
        "tourney_name": "Test Open",
        "surface": "Clay",
        "tourney_date": 20260105,
        "winner_id": 100,
        "winner_name": "A",
        "loser_id": 200,
        "loser_name": "B",
    }
    rows = [
        {**base, "match_num": 1, "score": "6-2 1-0 RET"},
        {**base, "match_num": 2, "score": "W/O"},
    ]
    pd.DataFrame(rows).to_csv(path, index=False)

    matches = load_sackmann_csv(path, tour="ATP")
    assert matches[0].outcome.retirement is True
    assert matches[0].outcome.walkover is False
    assert matches[1].outcome.walkover is True
