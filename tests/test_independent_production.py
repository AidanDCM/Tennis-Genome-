from __future__ import annotations

import gzip
import json
from datetime import date
from types import SimpleNamespace

import pytest

from tennis_genome.features.genome import GenomeVector
from tennis_genome.independent.production import (
    ACCEPTED_CANONICAL_CONTENT,
    CoreMappingArtifact,
    StandardizedLogisticArtifact,
    canonical_content_sha256,
    core_probability_from_artifact,
    standardized_logistic_probability,
    verify_accepted_canonical_content,
    write_neighbor_bank,
)
from tennis_genome.neighbors.historical import ResidualRecord


def test_accepted_canonical_content_fails_closed_on_feature_source_change() -> None:
    manifest = dict(ACCEPTED_CANONICAL_CONTENT["ATP"])
    accepted = verify_accepted_canonical_content("ATP", manifest)
    assert accepted == canonical_content_sha256(manifest)

    changed = dict(manifest)
    changed["stats_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="accepted GENOME-ADV-001 source"):
        verify_accepted_canonical_content("ATP", changed)


def test_core_artifact_reproduces_impute_scale_logistic_mapping() -> None:
    artifact = CoreMappingArtifact(
        feature_names=("x", "y"),
        training_n=10,
        imputer_statistics=(2.0, 4.0),
        imputer_indicator_features=(1,),
        scaler_mean=(1.0, 2.0, 0.25),
        scaler_scale=(2.0, 4.0, 0.5),
        coefficients=(0.5, -0.25, 0.75),
        intercept=0.1,
    )
    snapshot = SimpleNamespace(x=3.0, y=None)

    probability = core_probability_from_artifact(snapshot, artifact)  # type: ignore[arg-type]

    expanded = (3.0, 4.0, 1.0)
    standardized = tuple(
        (value - mean) / scale
        for value, mean, scale in zip(
            expanded,
            artifact.scaler_mean,
            artifact.scaler_scale,
            strict=True,
        )
    )
    expected_logit = artifact.intercept + sum(
        coefficient * value
        for coefficient, value in zip(
            artifact.coefficients,
            standardized,
            strict=True,
        )
    )
    expected = 1.0 / (1.0 + __import__("math").exp(-expected_logit))
    assert probability == pytest.approx(expected)


def test_standardized_logistic_probability_is_deterministic() -> None:
    artifact = StandardizedLogisticArtifact(
        input_names=("a", "b"),
        training_n=100,
        scaler_mean=(0.0, 2.0),
        scaler_scale=(2.0, 4.0),
        coefficients=(1.5, -0.5),
        intercept=-0.2,
    )
    first = standardized_logistic_probability((1.0, 6.0), artifact)
    second = standardized_logistic_probability((1.0, 6.0), artifact)
    assert first == pytest.approx(second)
    assert 0.0 < first < 1.0


def test_neighbor_bank_writer_is_byte_deterministic(tmp_path) -> None:
    records = [
        ResidualRecord(
            genome=GenomeVector(
                match_id="m2",
                event_date=date(2020, 2, 1),
                tour="ATP",
                player_a_id="a",
                player_b_id="b",
                orientation_sign=1,
                feature_names=("x", "y"),
                values=(1.0, None),
            ),
            residual_favorite=0.1,
        ),
        ResidualRecord(
            genome=GenomeVector(
                match_id="m1",
                event_date=date(2020, 1, 1),
                tour="ATP",
                player_a_id="c",
                player_b_id="d",
                orientation_sign=-1,
                feature_names=("x", "y"),
                values=(0.0, 2.0),
            ),
            residual_favorite=-0.2,
        ),
    ]
    first_path = tmp_path / "first.jsonl.gz"
    second_path = tmp_path / "second.jsonl.gz"
    first_sha = write_neighbor_bank(first_path, records)
    second_sha = write_neighbor_bank(second_path, list(reversed(records)))

    assert first_sha == second_sha
    assert first_path.read_bytes() == second_path.read_bytes()
    with gzip.open(first_path, "rt", encoding="utf-8") as handle:
        rows = [json.loads(line) for line in handle]
    assert [row["match_id"] for row in rows] == ["m1", "m2"]
