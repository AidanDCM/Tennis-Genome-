from pathlib import Path

import pandas as pd
import pytest

from tennis_genome.data.parquet import load_canonical_parquet
from tennis_genome.pipeline.build_dataset import build_canonical_dataset


def _source_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "tourney_id": "2026-010",
                "tourney_name": "Round Trip Open",
                "surface": "Clay",
                "tourney_level": "A",
                "tourney_date": 20260201,
                "match_num": 1,
                "winner_id": 100,
                "winner_name": "Player A",
                "winner_rank": 11,
                "winner_rank_points": 2500,
                "loser_id": 200,
                "loser_name": "Player B",
                "loser_rank": 22,
                "loser_rank_points": 1400,
                "score": "6-3 6-4",
                "best_of": 3,
                "round": "R32",
            }
        ]
    )


def _canonical_pre_row(match_id: object) -> dict[str, object]:
    return {
        "match_id": match_id,
        "tour": "ATP",
        "event_date": "2026-01-01",
        "source_order": 0,
        "tournament_id": "test",
        "tournament_name": "Test Open",
        "tournament_level": "A",
        "surface": "Hard",
        "round": "R32",
        "best_of": 3,
        "player_a_id": "a",
        "player_b_id": "b",
        "player_a_name": "A",
        "player_b_name": "B",
        "rank_a": 10,
        "rank_b": 20,
        "rank_points_a": 1000,
        "rank_points_b": 500,
    }


def _canonical_outcome_row(match_id: object) -> dict[str, object]:
    return {
        "match_id": match_id,
        "a_won": True,
        "score": "6-0 6-0",
        "retirement": False,
        "walkover": False,
    }


def test_canonical_parquet_round_trip(tmp_path: Path):
    source = tmp_path / "source.csv"
    output = tmp_path / "canonical"
    _source_frame().to_csv(source, index=False)
    build_canonical_dataset(source_csv=source, tour="ATP", output_dir=output)

    matches = load_canonical_parquet(
        pre_match_path=output / "atp_pre_match.parquet",
        outcome_path=output / "atp_outcomes.parquet",
    )

    assert len(matches) == 1
    match = matches[0]
    assert match.pre_match.surface == "Clay"
    assert match.pre_match.rank_a == 11
    assert match.outcome.a_won is True
    assert match.outcome.score == "6-3 6-4"


def test_loader_rejects_outcome_leakage_in_pre_match_table(tmp_path: Path):
    pre_match = tmp_path / "pre.parquet"
    outcomes = tmp_path / "outcomes.parquet"
    leaked = _canonical_pre_row("m1")
    leaked["a_won"] = True
    pd.DataFrame([leaked]).to_parquet(pre_match, index=False)
    pd.DataFrame([_canonical_outcome_row("m1")]).to_parquet(outcomes, index=False)

    with pytest.raises(ValueError, match="outcome fields leaked"):
        load_canonical_parquet(pre_match_path=pre_match, outcome_path=outcomes)


def test_loader_rejects_mismatched_match_populations(tmp_path: Path):
    pre_match = tmp_path / "pre.parquet"
    outcomes = tmp_path / "outcomes.parquet"
    pd.DataFrame([_canonical_pre_row("m1")]).to_parquet(pre_match, index=False)
    pd.DataFrame([_canonical_outcome_row("m2")]).to_parquet(outcomes, index=False)

    with pytest.raises(ValueError, match="match IDs differ"):
        load_canonical_parquet(pre_match_path=pre_match, outcome_path=outcomes)


def test_loader_normalizes_match_ids_to_strings(tmp_path: Path):
    pre_match = tmp_path / "pre.parquet"
    outcomes = tmp_path / "outcomes.parquet"
    pd.DataFrame([_canonical_pre_row(123)]).to_parquet(pre_match, index=False)
    pd.DataFrame([_canonical_outcome_row(123)]).to_parquet(outcomes, index=False)

    matches = load_canonical_parquet(pre_match_path=pre_match, outcome_path=outcomes)

    assert matches[0].match_id == "123"


def test_loader_rejects_missing_outcome_boolean(tmp_path: Path):
    pre_match = tmp_path / "pre.parquet"
    outcomes = tmp_path / "outcomes.parquet"
    outcome = _canonical_outcome_row("m1")
    outcome["a_won"] = None
    pd.DataFrame([_canonical_pre_row("m1")]).to_parquet(pre_match, index=False)
    pd.DataFrame([outcome]).to_parquet(outcomes, index=False)

    with pytest.raises(ValueError, match="a_won is missing"):
        load_canonical_parquet(pre_match_path=pre_match, outcome_path=outcomes)
