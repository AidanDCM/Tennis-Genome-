from pathlib import Path

import pandas as pd
import pytest

from tennis_genome.data.manifest import verify_canonical_manifest
from tennis_genome.data.parquet import load_canonical_parquet
from tennis_genome.data.provenance import SourceMetadata
from tennis_genome.data.sackmann import load_sackmann_csv
from tennis_genome.pipeline.build_dataset import build_canonical_dataset


def _stats_source(path: Path) -> None:
    pd.DataFrame(
        [
            {
                "tourney_id": "2026-STAT",
                "tourney_name": "Stats Open",
                "surface": "Hard",
                "tourney_level": "A",
                "tourney_date": 20260105,
                "match_num": 1,
                "winner_id": 200,
                "winner_name": "Player 200",
                "winner_rank": 10,
                "loser_id": 100,
                "loser_name": "Player 100",
                "loser_rank": 20,
                "score": "6-4 6-4",
                "best_of": 3,
                "round": "R32",
                "w_ace": 7,
                "w_df": 2,
                "w_svpt": 60,
                "w_1stIn": 38,
                "w_1stWon": 30,
                "w_2ndWon": 12,
                "w_SvGms": 10,
                "w_bpSaved": 3,
                "w_bpFaced": 4,
                "l_ace": 3,
                "l_df": 5,
                "l_svpt": 70,
                "l_1stIn": 40,
                "l_1stWon": 25,
                "l_2ndWon": 10,
                "l_SvGms": 10,
                "l_bpSaved": 5,
                "l_bpFaced": 8,
            }
        ]
    ).to_csv(path, index=False)


def test_source_stats_follow_canonical_player_orientation(tmp_path: Path):
    source = tmp_path / "source.csv"
    _stats_source(source)

    match = load_sackmann_csv(source, tour="ATP")[0]

    assert match.pre_match.player_a_id == "atp:id:100"
    assert match.pre_match.player_b_id == "atp:id:200"
    assert match.outcome.a_won is False
    assert match.stats is not None
    assert match.stats.service_points_a == 70
    assert match.stats.service_points_b == 60
    assert match.stats.service_points_won_a == 35
    assert match.stats.service_points_won_b == 42
    assert match.stats.aces_a == 3
    assert match.stats.aces_b == 7


def test_builder_writes_separate_verified_stats_table(tmp_path: Path):
    source = tmp_path / "source.csv"
    output = tmp_path / "canonical"
    _stats_source(source)
    manifest = build_canonical_dataset(
        source_csv=source,
        tour="ATP",
        output_dir=output,
        source_metadata=SourceMetadata(
            source_id="stats-research",
            provider="Test Provider",
            allowed_use_status="research_allowed",
        ),
    )

    stats_path = output / "atp_stats.parquet"
    stats = pd.read_parquet(stats_path)
    pre_match = pd.read_parquet(output / "atp_pre_match.parquet")

    assert manifest["schema_version"] == "canonical-v3"
    assert manifest["stats_filename"] == "atp_stats.parquet"
    assert stats_path.exists()
    assert "a_won" not in stats.columns
    assert "service_points_a" in stats.columns
    assert "service_points_a" not in pre_match.columns

    verify_canonical_manifest(
        manifest_path=output / "atp_manifest.json",
        pre_match_path=output / "atp_pre_match.parquet",
        outcome_path=output / "atp_outcomes.parquet",
        stats_path=stats_path,
    )
    matches = load_canonical_parquet(
        pre_match_path=output / "atp_pre_match.parquet",
        outcome_path=output / "atp_outcomes.parquet",
        stats_path=stats_path,
    )
    assert matches[0].stats is not None
    assert matches[0].stats.service_points_won_a == 35


def test_manifest_rejects_tampered_stats_table(tmp_path: Path):
    source = tmp_path / "source.csv"
    output = tmp_path / "canonical"
    _stats_source(source)
    build_canonical_dataset(
        source_csv=source,
        tour="ATP",
        output_dir=output,
        source_metadata=SourceMetadata(
            source_id="stats-research",
            provider="Test Provider",
            allowed_use_status="research_allowed",
        ),
    )
    stats_path = output / "atp_stats.parquet"
    with stats_path.open("ab") as handle:
        handle.write(b"tampered")

    with pytest.raises(ValueError, match="stats Parquet hash does not match"):
        verify_canonical_manifest(
            manifest_path=output / "atp_manifest.json",
            pre_match_path=output / "atp_pre_match.parquet",
            outcome_path=output / "atp_outcomes.parquet",
            stats_path=stats_path,
        )
