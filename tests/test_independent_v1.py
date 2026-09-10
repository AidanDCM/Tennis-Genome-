from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from tennis_genome.independent.prediction import (
    IndependentPrediction,
    reject_market_or_outcome_fields,
)
from tennis_genome.independent.spec import (
    MODEL_VERSION,
    TGE_INDEPENDENT_V1,
    architecture_hash,
    canonical_spec_json,
    tour_spec,
)


def _prediction(**overrides: object) -> IndependentPrediction:
    cutoff = datetime(2026, 9, 10, 14, 0, tzinfo=UTC)
    values: dict[str, object] = {
        "prediction_id": "pred-1",
        "match_id": "match-1",
        "tour": "ATP",
        "created_at": cutoff + timedelta(seconds=2),
        "prediction_cutoff_at": cutoff,
        "p_player_a": 0.63,
        "p_player_b": 0.37,
        "source_manifest_hashes": ("a" * 64,),
    }
    values.update(overrides)
    return IndependentPrediction(**values)  # type: ignore[arg-type]


def test_architecture_hash_is_deterministic_and_sensitive_to_spec() -> None:
    first = architecture_hash()
    second = architecture_hash()
    assert first == second
    assert len(first) == 64

    mutated = replace(TGE_INDEPENDENT_V1, spec_version="1.0.1")
    assert architecture_hash(mutated) != first
    assert canonical_spec_json() == canonical_spec_json(TGE_INDEPENDENT_V1)


def test_committed_manifest_matches_frozen_architecture_hash() -> None:
    manifest = json.loads(
        Path("artifacts/tge_independent_v1_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["model_version"] == MODEL_VERSION
    assert manifest["architecture_hash"] == architecture_hash()
    assert manifest["development_data_end_year"] == 2025
    assert manifest["market_blind"] is True


def test_tour_architectures_are_intentionally_asymmetric() -> None:
    atp = tour_spec("ATP")
    wta = tour_spec("WTA")

    assert "full_genome_historical_alignment_k100" in atp.probability_path
    assert "pointsim_conditional_meta_component" not in atp.probability_path

    assert "strict_core_geometry_historical_alignment_k100" in wta.probability_path
    assert "pointsim_conditional_meta_component" in wta.probability_path
    assert "profile_aware_genome_geometry" in wta.excluded_components


def test_independent_prediction_is_complementary_and_market_blind() -> None:
    prediction = _prediction()
    payload = prediction.to_dict()

    assert prediction.model_version == MODEL_VERSION
    assert prediction.architecture_hash == architecture_hash()
    assert prediction.p_player_a + prediction.p_player_b == pytest.approx(1.0)
    reject_market_or_outcome_fields(payload)


def test_independent_prediction_rejects_wrong_architecture_hash() -> None:
    with pytest.raises(ValueError, match="architecture_hash"):
        _prediction(architecture_hash="0" * 64)


def test_independent_prediction_rejects_invalid_probability_sum() -> None:
    with pytest.raises(ValueError, match="sum to one"):
        _prediction(p_player_a=0.7, p_player_b=0.4)


def test_independent_prediction_allows_creation_at_or_after_cutoff() -> None:
    cutoff = datetime(2026, 9, 10, 14, 0, tzinfo=UTC)
    _prediction(created_at=cutoff, prediction_cutoff_at=cutoff)
    _prediction(created_at=cutoff + timedelta(minutes=1), prediction_cutoff_at=cutoff)

    with pytest.raises(ValueError, match="before prediction_cutoff_at"):
        _prediction(created_at=cutoff - timedelta(seconds=1), prediction_cutoff_at=cutoff)


def test_independent_prediction_requires_aware_timestamps() -> None:
    naive = datetime(2026, 9, 10, 14, 0)
    aware = datetime(2026, 9, 10, 14, 0, tzinfo=UTC)

    with pytest.raises(ValueError, match="created_at must be timezone-aware"):
        _prediction(created_at=naive, prediction_cutoff_at=aware)
    with pytest.raises(ValueError, match="prediction_cutoff_at must be timezone-aware"):
        _prediction(created_at=aware, prediction_cutoff_at=naive)


def test_source_manifest_hashes_are_required_and_validated() -> None:
    with pytest.raises(ValueError, match="at least one"):
        _prediction(source_manifest_hashes=())
    with pytest.raises(ValueError, match="lowercase SHA-256"):
        _prediction(source_manifest_hashes=("not-a-hash",))
    with pytest.raises(ValueError, match="unique"):
        _prediction(source_manifest_hashes=("a" * 64, "a" * 64))


def test_market_and_outcome_fields_fail_closed_recursively() -> None:
    for forbidden in (
        "odds",
        "bookmaker",
        "market_snapshot_id",
        "edge_pp",
        "expected_value_per_unit",
        "stake_units",
        "outcome_player_a_won",
        "realized_profit_units",
        "sportsbook_odds",
        "market_price",
        "closing_line_price",
    ):
        with pytest.raises(ValueError, match="forbidden"):
            reject_market_or_outcome_fields({"match_id": "m1", forbidden: 1})
        with pytest.raises(ValueError, match="forbidden"):
            reject_market_or_outcome_fields({"diagnostics": {forbidden: 1}})


def test_prediction_rejects_market_data_hidden_in_diagnostics() -> None:
    with pytest.raises(ValueError, match="forbidden"):
        _prediction(diagnostics={"sportsbook_odds": 2.1})


def test_independent_schema_contains_no_market_or_outcome_properties() -> None:
    schema_path = Path("schemas/independent_prediction.schema.json")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    properties = set(schema["properties"])

    forbidden = {
        "market_snapshot_id",
        "market_novig_p_player_a",
        "edge_pp",
        "expected_value_per_unit",
        "stake_units",
        "outcome_player_a_won",
        "realized_profit_units",
        "closing_line_value",
    }
    assert not properties.intersection(forbidden)
    assert schema["additionalProperties"] is False


def test_model_schema_freezes_market_blind_status_and_cutoff() -> None:
    schema = json.loads(
        Path("schemas/tge_independent_model.schema.json").read_text(encoding="utf-8")
    )
    properties = schema["properties"]

    assert properties["model_version"]["const"] == MODEL_VERSION
    assert properties["development_data_end_year"]["const"] == 2025
    assert properties["market_blind"]["const"] is True
    assert properties["hard_pass_policy_promoted"]["const"] is False
