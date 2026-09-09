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
    pd.DataFrame(
        [
            {
                "match_id": "m1",
                "a_won": True,
            }
        ]
    ).to_parquet(pre_match, index=False)
    pd.DataFrame(
        [
            {
                "match_id": "m1",
                "a_won": True,
                "score": "6-0 6-0",
                "retirement": False,
                "walkover": False,
            }
        ]
    ).to_parquet(outcomes, index=False)

    with pytest.raises(ValueError, match="outcome fields leaked"):
        load_canonical_parquet(pre_match_path=pre_match, outcome_path=outcomes)


def test_loader_rejects_mismatched_match_populations(tmp_path: Path):
    pre_match = tmp_path / "pre.parquet"
    outcomes = tmp_path / "outcomes.parquet"
    pd.DataFrame(
        [
            {
                "match_id": "m1",
                "tour": "ATP",
                "event_date": "2026-01-01",
            }
        ]
    ).to_parquet(pre_match, index=False)
    pd.DataFrame(
        [
            {
                "match_id": "m2",
                "a_won": True,
                "score": None,
                "retirement": False,
                "walkover": False,
            }
        ]
    ).to_parquet(outcomes, index=False)

    with pytest.raises(ValueError, match="match IDs differ"):
        load_canonical_parquet(pre_match_path=pre_match, outcome_path=outcomes)
