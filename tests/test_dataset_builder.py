from pathlib import Path

import pandas as pd

from tennis_genome.data.provenance import SourceMetadata
from tennis_genome.pipeline.build_dataset import build_canonical_dataset


def test_builder_separates_pre_match_and_outcome_tables(tmp_path: Path):
    source = tmp_path / "source.csv"
    output = tmp_path / "out"
    pd.DataFrame(
        [
            {
                "tourney_id": "2026-001",
                "tourney_name": "Test Open",
                "surface": "Hard",
                "tourney_level": "A",
                "tourney_date": 20260105,
                "match_num": 1,
                "winner_id": 100,
                "winner_name": "Player A",
                "winner_rank": 10,
                "winner_rank_points": 3000,
                "loser_id": 200,
                "loser_name": "Player B",
                "loser_rank": 20,
                "loser_rank_points": 1800,
                "score": "6-4 6-4",
                "best_of": 3,
                "round": "R32",
            }
        ]
    ).to_csv(source, index=False)

    metadata = SourceMetadata(
        source_id="test-source",
        provider="Test Provider",
        source_version="v1",
        license_name="Test License",
        allowed_use_status="research_allowed",
    )
    manifest = build_canonical_dataset(
        source_csv=source,
        tour="ATP",
        output_dir=output,
        source_metadata=metadata,
    )
    pre_match = pd.read_parquet(output / "atp_pre_match.parquet")
    outcomes = pd.read_parquet(output / "atp_outcomes.parquet")

    assert manifest["row_count"] == 1
    assert "a_won" not in pre_match.columns
    assert "score" not in pre_match.columns
    assert "rank_a" in pre_match.columns
    assert "a_won" in outcomes.columns
    assert "rank_a" not in outcomes.columns
    assert manifest["source_metadata"]["source_id"] == "test-source"
    assert manifest["source_metadata"]["allowed_use_status"] == "research_allowed"
    assert (output / "atp_manifest.json").exists()


def test_builder_defaults_unknown_sources_to_fail_closed(tmp_path: Path):
    source = tmp_path / "source.csv"
    output = tmp_path / "out"
    pd.DataFrame(
        [
            {
                "tourney_id": "2026-002",
                "tourney_name": "Test Open",
                "tourney_date": 20260106,
                "winner_name": "Player A",
                "loser_name": "Player B",
            }
        ]
    ).to_csv(source, index=False)

    manifest = build_canonical_dataset(source_csv=source, tour="ATP", output_dir=output)

    assert manifest["source_metadata"]["allowed_use_status"] == "unknown_do_not_use"
