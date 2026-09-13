from pathlib import Path

import pandas as pd
import pytest

from tennis_genome.data.sackmann import load_sackmann_csv, load_sackmann_csvs


def _write_match(
    path: Path,
    *,
    tourney_id: str,
    tourney_date: int,
    match_num: int,
    winner_id: int,
    loser_id: int,
) -> None:
    pd.DataFrame(
        [
            {
                "tourney_id": tourney_id,
                "tourney_name": "Test Open",
                "surface": "Hard",
                "tourney_level": "A",
                "tourney_date": tourney_date,
                "match_num": match_num,
                "winner_id": winner_id,
                "winner_name": f"Winner {winner_id}",
                "loser_id": loser_id,
                "loser_name": f"Loser {loser_id}",
                "score": "6-4 6-4",
                "best_of": 3,
                "round": "R32",
            }
        ]
    ).to_csv(path, index=False)


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


def test_legacy_entry_code_in_seed_cell_is_normalized(tmp_path: Path):
    path = tmp_path / "legacy_wta.csv"
    pd.DataFrame(
        [
            {
                "tourney_id": "2001-WTA",
                "tourney_name": "Legacy Open",
                "surface": "Hard",
                "tourney_level": "A",
                "tourney_date": 20010101,
                "match_num": 1,
                "winner_id": 200,
                "winner_name": "Winner",
                "winner_seed": "Q",
                "winner_entry": None,
                "loser_id": 100,
                "loser_name": "Loser",
                "loser_seed": 8,
                "loser_entry": None,
                "score": "6-4 6-4",
                "best_of": 3,
                "round": "R32",
            }
        ]
    ).to_csv(path, index=False)

    match = load_sackmann_csv(path, tour="WTA")[0]
    state = match.pre_match

    assert state.player_a_id == "wta:id:100"
    assert state.seed_a == 8
    assert state.entry_a is None
    assert state.player_b_id == "wta:id:200"
    assert state.seed_b is None
    assert state.entry_b == "Q"


def test_explicit_entry_takes_precedence_over_legacy_seed_code(tmp_path: Path):
    path = tmp_path / "legacy_wta_explicit.csv"
    pd.DataFrame(
        [
            {
                "tourney_id": "2001-WTA",
                "tourney_name": "Legacy Open",
                "surface": "Hard",
                "tourney_level": "A",
                "tourney_date": 20010101,
                "match_num": 1,
                "winner_id": 100,
                "winner_name": "Winner",
                "winner_seed": "Q",
                "winner_entry": "WC",
                "loser_id": 200,
                "loser_name": "Loser",
                "score": "6-4 6-4",
                "best_of": 3,
                "round": "R32",
            }
        ]
    ).to_csv(path, index=False)

    match = load_sackmann_csv(path, tour="WTA")[0]
    assert match.pre_match.seed_a is None
    assert match.pre_match.entry_a == "WC"


def test_unknown_nonnumeric_seed_token_is_rejected(tmp_path: Path):
    path = tmp_path / "bad_seed.csv"
    pd.DataFrame(
        [
            {
                "tourney_id": "2001-WTA",
                "tourney_name": "Legacy Open",
                "surface": "Hard",
                "tourney_level": "A",
                "tourney_date": 20010101,
                "match_num": 1,
                "winner_id": 100,
                "winner_name": "Winner",
                "winner_seed": "MYSTERY",
                "loser_id": 200,
                "loser_name": "Loser",
                "score": "6-4 6-4",
                "best_of": 3,
                "round": "R32",
            }
        ]
    ).to_csv(path, index=False)

    with pytest.raises(ValueError, match="unrecognized nonnumeric seed token"):
        load_sackmann_csv(path, tour="WTA")


def test_reused_match_numbers_are_disambiguated_without_row_order_dependence(tmp_path: Path):
    first_path = tmp_path / "first.csv"
    reversed_path = tmp_path / "reversed.csv"
    common = {
        "tourney_id": "2009-W-CHA-INA-01A-2009",
        "tourney_name": "Tournament of Champions",
        "surface": "Hard",
        "tourney_level": "F",
        "tourney_date": 20091102,
        "match_num": 1,
        "best_of": 3,
    }
    rows = [
        {
            **common,
            "winner_id": 201294,
            "winner_name": "Marion Bartoli",
            "loser_id": 200617,
            "loser_name": "Kimiko Date Krumm",
            "round": "SF",
            "score": "6-1 6-3",
        },
        {
            **common,
            "winner_id": 201294,
            "winner_name": "Marion Bartoli",
            "loser_id": 201424,
            "loser_name": "Shahar Peer",
            "round": "RR",
            "score": "6-3 6-2",
        },
    ]
    pd.DataFrame(rows).to_csv(first_path, index=False)
    pd.DataFrame(list(reversed(rows))).to_csv(reversed_path, index=False)

    first = load_sackmann_csv(first_path, tour="WTA")
    reversed_matches = load_sackmann_csv(reversed_path, tour="WTA")

    first_ids = {match.match_id for match in first}
    reversed_ids = {match.match_id for match in reversed_matches}
    assert len(first_ids) == 2
    assert first_ids == reversed_ids
    assert all(":d-" in match_id for match_id in first_ids)


def test_multi_file_adapter_is_independent_of_input_order(tmp_path: Path):
    older = tmp_path / "2024.csv"
    newer = tmp_path / "2025.csv"
    _write_match(
        older,
        tourney_id="2024-001",
        tourney_date=20240101,
        match_num=1,
        winner_id=100,
        loser_id=200,
    )
    _write_match(
        newer,
        tourney_id="2025-001",
        tourney_date=20250101,
        match_num=1,
        winner_id=300,
        loser_id=400,
    )

    forward = load_sackmann_csvs([older, newer], tour="ATP")
    reversed_inputs = load_sackmann_csvs([newer, older], tour="ATP")

    assert [match.match_id for match in forward] == [match.match_id for match in reversed_inputs]
    assert [match.pre_match.source_order for match in forward] == [0, 1]
    assert [match.pre_match.source_order for match in reversed_inputs] == [0, 1]
    assert [match.pre_match.event_date.year for match in forward] == [2024, 2025]
