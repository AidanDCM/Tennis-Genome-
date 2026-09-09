from pathlib import Path

import pandas as pd
import pytest

from tennis_genome.data.manifest import verify_canonical_manifest
from tennis_genome.data.provenance import SourceMetadata, SourcePermissionError
from tennis_genome.pipeline.build_dataset import build_canonical_dataset


def _build_source(path: Path) -> None:
    pd.DataFrame(
        [
            {
                "tourney_id": "2026-020",
                "tourney_name": "Manifest Open",
                "surface": "Hard",
                "tourney_level": "A",
                "tourney_date": 20260301,
                "match_num": 1,
                "winner_id": 100,
                "winner_name": "Player A",
                "winner_rank": 10,
                "winner_rank_points": 2000,
                "loser_id": 200,
                "loser_name": "Player B",
                "loser_rank": 30,
                "loser_rank_points": 900,
                "score": "6-4 6-4",
                "best_of": 3,
                "round": "R32",
            }
        ]
    ).to_csv(path, index=False)


def test_manifest_verification_accepts_exact_research_dataset(tmp_path: Path):
    source = tmp_path / "source.csv"
    output = tmp_path / "canonical"
    _build_source(source)
    build_canonical_dataset(
        source_csv=source,
        tour="ATP",
        output_dir=output,
        source_metadata=SourceMetadata(
            source_id="research-v1",
            provider="Research Provider",
            allowed_use_status="research_allowed",
        ),
    )

    manifest = verify_canonical_manifest(
        manifest_path=output / "atp_manifest.json",
        pre_match_path=output / "atp_pre_match.parquet",
        outcome_path=output / "atp_outcomes.parquet",
    )

    assert manifest["source_metadata"]["source_id"] == "research-v1"


def test_manifest_verification_rejects_unknown_permission(tmp_path: Path):
    source = tmp_path / "source.csv"
    output = tmp_path / "canonical"
    _build_source(source)
    build_canonical_dataset(source_csv=source, tour="ATP", output_dir=output)

    with pytest.raises(SourcePermissionError):
        verify_canonical_manifest(
            manifest_path=output / "atp_manifest.json",
            pre_match_path=output / "atp_pre_match.parquet",
            outcome_path=output / "atp_outcomes.parquet",
        )


def test_manifest_verification_rejects_modified_parquet(tmp_path: Path):
    source = tmp_path / "source.csv"
    output = tmp_path / "canonical"
    _build_source(source)
    build_canonical_dataset(
        source_csv=source,
        tour="ATP",
        output_dir=output,
        source_metadata=SourceMetadata(
            source_id="research-v1",
            provider="Research Provider",
            allowed_use_status="research_allowed",
        ),
    )
    pre_match = output / "atp_pre_match.parquet"
    with pre_match.open("ab") as handle:
        handle.write(b"tampered")

    with pytest.raises(ValueError, match="hash does not match"):
        verify_canonical_manifest(
            manifest_path=output / "atp_manifest.json",
            pre_match_path=pre_match,
            outcome_path=output / "atp_outcomes.parquet",
        )
