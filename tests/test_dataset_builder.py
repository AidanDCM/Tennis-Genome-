from pathlib import Path

import pandas as pd
import pytest

from tennis_genome.data.manifest import sha256_file
from tennis_genome.data.provenance import SourceMetadata
from tennis_genome.pipeline.build_dataset import (
    build_canonical_dataset,
    build_canonical_dataset_from_files,
)


def _source_row(
    *,
    tourney_id: str,
    tourney_date: int,
    match_num: int,
    winner_id: int,
    loser_id: int,
) -> dict[str, object]:
    return {
        "tourney_id": tourney_id,
        "tourney_name": "Test Open",
        "surface": "Hard",
        "tourney_level": "A",
        "tourney_date": tourney_date,
        "match_num": match_num,
        "winner_id": winner_id,
        "winner_name": f"Player {winner_id}",
        "winner_rank": 10,
        "winner_rank_points": 3000,
        "loser_id": loser_id,
        "loser_name": f"Player {loser_id}",
        "loser_rank": 20,
        "loser_rank_points": 1800,
        "score": "6-4 6-4",
        "best_of": 3,
        "round": "R32",
    }


def test_builder_separates_pre_match_and_outcome_tables(tmp_path: Path):
    source = tmp_path / "source.csv"
    output = tmp_path / "out"
    pd.DataFrame(
        [
            _source_row(
                tourney_id="2026-001",
                tourney_date=20260105,
                match_num=1,
                winner_id=100,
                loser_id=200,
            )
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
    assert manifest["source_format"] == "sackmann_style_csv"
    assert "a_won" not in pre_match.columns
    assert "score" not in pre_match.columns
    assert "rank_a" in pre_match.columns
    assert "a_won" in outcomes.columns
    assert "rank_a" not in outcomes.columns
    assert manifest["source_metadata"]["source_id"] == "test-source"
    assert manifest["source_metadata"]["allowed_use_status"] == "research_allowed"
    assert manifest["source_file_count"] == 1
    assert manifest["source_files"] == [
        {"filename": "source.csv", "sha256": sha256_file(source)}
    ]
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


def test_multi_file_builder_records_every_source_and_is_order_invariant(tmp_path: Path):
    older = tmp_path / "2024.csv"
    newer = tmp_path / "2025.csv"
    pd.DataFrame(
        [
            _source_row(
                tourney_id="2024-001",
                tourney_date=20240101,
                match_num=1,
                winner_id=100,
                loser_id=200,
            )
        ]
    ).to_csv(older, index=False)
    pd.DataFrame(
        [
            _source_row(
                tourney_id="2025-001",
                tourney_date=20250101,
                match_num=1,
                winner_id=300,
                loser_id=400,
            )
        ]
    ).to_csv(newer, index=False)

    first_output = tmp_path / "first"
    second_output = tmp_path / "second"
    first = build_canonical_dataset_from_files(
        source_csvs=[newer, older],
        tour="ATP",
        output_dir=first_output,
    )
    second = build_canonical_dataset_from_files(
        source_csvs=[older, newer],
        tour="ATP",
        output_dir=second_output,
    )

    expected_files = [
        {"filename": "2024.csv", "sha256": sha256_file(older)},
        {"filename": "2025.csv", "sha256": sha256_file(newer)},
    ]
    assert first["row_count"] == 2
    assert first["source_format"] == "sackmann_style_csv_bundle"
    assert first["source_file_count"] == 2
    assert first["source_files"] == expected_files
    assert second["source_files"] == expected_files
    assert first["source_bundle_sha256"] == second["source_bundle_sha256"]
    assert first["source_sha256"] == first["source_bundle_sha256"]

    pre_match = pd.read_parquet(first_output / "atp_pre_match.parquet")
    outcomes = pd.read_parquet(first_output / "atp_outcomes.parquet")
    assert list(pre_match["source_order"]) == [0, 1]
    assert len(pre_match) == 2
    assert len(outcomes) == 2


def test_multi_file_builder_rejects_cross_file_duplicate_match_ids(tmp_path: Path):
    first = tmp_path / "first.csv"
    second = tmp_path / "second.csv"
    duplicate = _source_row(
        tourney_id="2026-DUP",
        tourney_date=20260105,
        match_num=1,
        winner_id=100,
        loser_id=200,
    )
    pd.DataFrame([duplicate]).to_csv(first, index=False)
    pd.DataFrame([{**duplicate, "tourney_date": 20260106}]).to_csv(second, index=False)

    with pytest.raises(ValueError, match="duplicate_match_id"):
        build_canonical_dataset_from_files(
            source_csvs=[first, second],
            tour="ATP",
            output_dir=tmp_path / "out",
        )
