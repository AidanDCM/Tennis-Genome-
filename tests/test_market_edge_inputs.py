from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from tennis_genome.experiments.market_edge_inputs import (
    build_market_signal_rows,
    load_closing_market_rows,
    load_genome_values,
    load_profile_gap_values,
    load_settled_outcomes,
)


def _market_record(*, match_id: str = "m1") -> dict[str, object]:
    return {
        "source_market_id": "1.100",
        "source_event_id": "e1",
        "source_file": "1.100.bz2",
        "source_file_sha256": "a" * 64,
        "data_package": "ADVANCED",
        "join_status": "MATCHED",
        "normalized_runner_names": ["alpha", "beta"],
        "candidate_match_ids": [match_id],
        "join": {
            "join_hash": "b" * 64,
            "resolver_version": "test",
            "source_market_id": "1.100",
            "source_event_id": "e1",
            "source_market_time": "2024-01-02T12:00:00+00:00",
            "match_id": match_id,
            "tour": "ATP",
            "source_selection_a_id": 1,
            "source_selection_b_id": 2,
            "source_selection_a_name": "Alpha",
            "source_selection_b_name": "Beta",
            "player_a_id": "a",
            "player_b_id": "b",
            "tournament_date_offset_days": 1,
            "days_before_window": 4,
            "days_after_window": 21,
        },
        "checkpoints": [
            {
                "record_hash": "c" * 64,
                "checkpoint_id": "d" * 64,
                "join_hash": "b" * 64,
                "source_market_id": "1.100",
                "source_event_id": "e1",
                "match_id": match_id,
                "tour": "ATP",
                "checkpoint_name": "CLOSE_PREPLAY",
                "published_at": "2024-01-02T11:59:00+00:00",
                "market_time": "2024-01-02T12:00:00+00:00",
                "seconds_to_start": 60.0,
                "checkpoint_lag_seconds": 0.0,
                "data_package": "ADVANCED",
                "market_base_rate": 5.0,
                "market_total_matched": 10000.0,
                "source_file_sha256": "a" * 64,
                "source_message_sha256": "e" * 64,
                "selection_a_id": 1,
                "selection_b_id": 2,
                "selection_a_name": "Alpha",
                "selection_b_name": "Beta",
                "best_back_a": 1.80,
                "best_back_size_a": 100.0,
                "best_lay_a": 1.82,
                "best_lay_size_a": 90.0,
                "last_traded_a": 1.81,
                "best_back_b": 2.20,
                "best_back_size_b": 80.0,
                "best_lay_b": 2.24,
                "best_lay_size_b": 70.0,
                "last_traded_b": 2.22,
                "executable_two_way": True,
            }
        ],
    }


def test_closing_market_loader_derives_frozen_fair_probability(tmp_path: Path) -> None:
    path = tmp_path / "records.jsonl"
    path.write_text(json.dumps(_market_record()) + "\n", encoding="utf-8")
    rows = load_closing_market_rows(path)
    assert set(rows) == {"m1"}
    row = rows["m1"]
    assert row.market_probability_a + row.market_probability_b == pytest.approx(1.0)
    assert row.market_probability_a > 0.5
    assert row.best_back_a == pytest.approx(1.80)


def test_closing_market_loader_rejects_duplicate_joined_markets(tmp_path: Path) -> None:
    path = tmp_path / "records.jsonl"
    first = _market_record()
    second = _market_record()
    second["source_market_id"] = "1.200"
    path.write_text(
        json.dumps(first) + "\n" + json.dumps(second) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="multiple executable Betfair closing markets"):
        load_closing_market_rows(path)


def test_signal_loaders_ignore_embedded_outcome_fields(tmp_path: Path) -> None:
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(
        json.dumps(
            {
                "experiment_id": "PROFILE-GAP-001",
                "tour": "ATP",
                "predictions": [
                    {
                        "match_id": "m1",
                        "outcome_a": True,
                        "profile_gap_match": 0.12,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    genome_path = tmp_path / "genome.json"
    genome_path.write_text(
        json.dumps(
            {
                "experiment_id": "GENOME-ADV-001",
                "tour": "ATP",
                "predictions": [
                    {
                        "match_id": "m1",
                        "outcome_a": False,
                        "full_neighbor_residual": 0.04,
                        "core_neighbor_residual": -0.99,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    profile = load_profile_gap_values(profile_path, tour="ATP")
    genome = load_genome_values(genome_path, tour="ATP")
    assert profile["m1"].signal == pytest.approx(0.12)
    assert genome["m1"].signal == pytest.approx(0.04)


def test_wta_genome_loader_uses_core_geometry_signal(tmp_path: Path) -> None:
    path = tmp_path / "genome.json"
    path.write_text(
        json.dumps(
            {
                "experiment_id": "GENOME-ADV-001",
                "tour": "WTA",
                "predictions": [
                    {
                        "match_id": "m1",
                        "core_neighbor_residual": 0.03,
                        "full_neighbor_residual": 0.90,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    values = load_genome_values(path, tour="WTA")
    assert values["m1"].signal == pytest.approx(0.03)


def test_settled_outcomes_drop_walkovers_but_keep_retirements(tmp_path: Path) -> None:
    frame = pd.DataFrame(
        [
            {"match_id": "m1", "a_won": True, "retirement": False, "walkover": False},
            {"match_id": "m2", "a_won": False, "retirement": True, "walkover": False},
            {"match_id": "m3", "a_won": True, "retirement": False, "walkover": True},
        ]
    )
    path = tmp_path / "outcomes.parquet"
    frame.to_parquet(path, index=False)
    outcomes = load_settled_outcomes(path)
    assert set(outcomes) == {"m1", "m2"}


def test_market_signal_builder_uses_canonical_outcome_not_signal_report(tmp_path: Path) -> None:
    records_path = tmp_path / "records.jsonl"
    records_path.write_text(json.dumps(_market_record()) + "\n", encoding="utf-8")
    close_rows = load_closing_market_rows(records_path)
    outcomes_path = tmp_path / "outcomes.parquet"
    pd.DataFrame(
        [{"match_id": "m1", "a_won": False, "retirement": False, "walkover": False}]
    ).to_parquet(outcomes_path, index=False)
    outcomes = load_settled_outcomes(outcomes_path)
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(
        json.dumps(
            {
                "experiment_id": "PROFILE-GAP-001",
                "tour": "ATP",
                "predictions": [
                    {
                        "match_id": "m1",
                        "outcome_a": True,
                        "profile_gap_match": 0.2,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    signals = load_profile_gap_values(profile_path, tour="ATP")
    rows = build_market_signal_rows(
        close_rows=close_rows,
        outcomes=outcomes,
        signals=signals,
        years_by_match={"m1": 2024},
        tour="ATP",
        signal_name="profile_gap",
    )
    assert len(rows) == 1
    assert rows[0].outcome_a is False
    assert rows[0].signal == pytest.approx(0.2)
