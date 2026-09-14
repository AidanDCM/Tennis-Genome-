from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from tennis_genome.research_workbench import (
    FeatureObservation,
    T0Policy,
    TargetBoundary,
    evaluate_feature_availability,
    sackmann_research_availability_registry,
)


def _registry():
    return sackmann_research_availability_registry(
        source_manifest_sha256="a" * 64,
        coverage_start=date(2000, 1, 1),
        coverage_end=date(2026, 6, 30),
    )


def test_sackmann_audit_allows_only_conservative_derived_state_for_canonical_v2() -> None:
    registry = _registry()

    legal = (
        "prior_match_outcome",
        "prior_match_stats",
        "prior_match_duration",
        "elo_state",
        "serve_return_state",
        "form_result_state",
        "form_point_state",
        "workload_state",
    )
    registry.assert_canonical_eligible(legal)

    for feature_id in (
        "target_ranking",
        "target_ranking_points",
        "target_age",
        "target_event_context",
        "target_player_reference",
    ):
        assert registry.get(feature_id).t0_policy == T0Policy.RESEARCH_ONLY_UNVERIFIED
        with pytest.raises(ValueError, match="non-canonical"):
            registry.assert_canonical_eligible((feature_id,))


def test_sackmann_prior_match_stats_cannot_update_same_day_target() -> None:
    registry = _registry()
    contract = registry.get("prior_match_stats")

    same_day = evaluate_feature_availability(
        contract=contract,
        observation=FeatureObservation(
            feature_id="prior_match_stats",
            source_match_id="prior",
            source_event_date=date(2026, 5, 1),
        ),
        target=TargetBoundary(
            match_id="target",
            event_date=date(2026, 5, 1),
        ),
    )
    next_day = evaluate_feature_availability(
        contract=contract,
        observation=FeatureObservation(
            feature_id="prior_match_stats",
            source_match_id="prior",
            source_event_date=date(2026, 5, 1),
        ),
        target=TargetBoundary(
            match_id="target",
            event_date=date(2026, 5, 2),
        ),
    )

    assert same_day.legal is False
    assert next_day.legal is True


def test_sackmann_target_ranking_does_not_gain_legality_from_exact_target_time() -> None:
    registry = _registry()
    contract = registry.get("target_ranking")

    decision = evaluate_feature_availability(
        contract=contract,
        observation=FeatureObservation(
            feature_id="target_ranking",
            source_event_date=date(2026, 5, 4),
        ),
        target=TargetBoundary(
            match_id="target",
            event_date=date(2026, 5, 4),
            event_start_at=datetime(2026, 5, 4, 15, 0, tzinfo=UTC),
        ),
    )

    assert decision.legal is False
    assert "unverified" in decision.reason


def test_sackmann_registry_identity_binds_source_snapshot_and_coverage() -> None:
    first = _registry()
    second = _registry()
    changed_manifest = sackmann_research_availability_registry(
        source_manifest_sha256="b" * 64,
        coverage_start=date(2000, 1, 1),
        coverage_end=date(2026, 6, 30),
    )
    changed_coverage = sackmann_research_availability_registry(
        source_manifest_sha256="a" * 64,
        coverage_start=date(2001, 1, 1),
        coverage_end=date(2026, 6, 30),
    )

    assert first.semantic_sha256 == second.semantic_sha256
    assert first.semantic_sha256 != changed_manifest.semantic_sha256
    assert first.semantic_sha256 != changed_coverage.semantic_sha256


def test_sackmann_audit_records_derived_feature_dependencies() -> None:
    registry = _registry()

    assert registry.get("elo_state").derived_from_features == ("prior_match_outcome",)
    assert registry.get("serve_return_state").derived_from_features == (
        "prior_match_stats",
    )
    assert registry.get("workload_state").derived_from_features == (
        "prior_match_duration",
    )
