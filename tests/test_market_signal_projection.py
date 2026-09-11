from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tennis_genome.experiments.market_signal_projection import (
    ProjectionSpec,
    project_signal_report,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_parent(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "experiment_id": "PROFILE-GAP-001",
                "tour": "ATP",
                "comparison": {"brier": 0.1},
                "predictions": [
                    {
                        "match_id": "m2",
                        "profile_gap_match": -0.25,
                        "outcome_a": False,
                        "strict_core_probability": 0.7,
                    },
                    {
                        "match_id": "m1",
                        "profile_gap_match": 0.5,
                        "outcome_a": True,
                        "strict_core_probability": 0.4,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )


def test_projection_is_deterministic_and_physically_outcome_free(tmp_path: Path) -> None:
    parent = tmp_path / "parent.json"
    _write_parent(parent)
    spec = ProjectionSpec(
        name="test",
        experiment_id="PROFILE-GAP-001",
        tour="ATP",
        signal_name="profile_gap",
        signal_field="profile_gap_match",
        expected_parent_sha256=_sha256(parent),
    )

    first = project_signal_report(parent, spec=spec)
    second = project_signal_report(parent, spec=spec)
    assert first == second
    assert [row["match_id"] for row in first["predictions"]] == ["m1", "m2"]
    assert first["predictions"] == [
        {"match_id": "m1", "profile_gap_match": 0.5},
        {"match_id": "m2", "profile_gap_match": -0.25},
    ]
    serialized = json.dumps(first, sort_keys=True)
    for forbidden in (
        "outcome_a",
        "comparison",
        "strict_core_probability",
        "winner",
        "score",
        "brier",
        "log_loss",
    ):
        assert forbidden not in serialized


def test_projection_fails_closed_on_parent_hash_mismatch(tmp_path: Path) -> None:
    parent = tmp_path / "parent.json"
    _write_parent(parent)
    spec = ProjectionSpec(
        name="test",
        experiment_id="PROFILE-GAP-001",
        tour="ATP",
        signal_name="profile_gap",
        signal_field="profile_gap_match",
        expected_parent_sha256="0" * 64,
    )
    with pytest.raises(ValueError, match="parent SHA-256 mismatch"):
        project_signal_report(parent, spec=spec)


def test_projection_rejects_duplicate_match_ids(tmp_path: Path) -> None:
    parent = tmp_path / "parent.json"
    parent.write_text(
        json.dumps(
            {
                "experiment_id": "GENOME-ADV-001",
                "tour": "WTA",
                "predictions": [
                    {"match_id": "m1", "core_neighbor_residual": 0.1},
                    {"match_id": "m1", "core_neighbor_residual": 0.2},
                ],
            }
        ),
        encoding="utf-8",
    )
    spec = ProjectionSpec(
        name="test",
        experiment_id="GENOME-ADV-001",
        tour="WTA",
        signal_name="genome",
        signal_field="core_neighbor_residual",
        expected_parent_sha256=_sha256(parent),
    )
    with pytest.raises(ValueError, match="duplicate match_id"):
        project_signal_report(parent, spec=spec)
