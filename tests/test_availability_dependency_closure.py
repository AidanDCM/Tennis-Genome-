from __future__ import annotations

from datetime import date

import pytest

from tennis_genome.research_workbench import (
    FeatureAvailabilityContract,
    FeatureAvailabilityRegistry,
    ReliabilityGrade,
    RevisionSemantics,
    T0Policy,
    TimestampSemantics,
    sackmann_research_availability_registry,
)


def _contract(
    feature_id: str,
    *,
    dependencies: tuple[str, ...] = (),
    policy: T0Policy = T0Policy.CONSERVATIVE_PRIOR_DATE_ONLY,
) -> FeatureAvailabilityContract:
    return FeatureAvailabilityContract(
        feature_id=feature_id,
        version="dependency-test-v1",
        source_id="test-source",
        source_manifest_sha256="a" * 64,
        timestamp_semantics=TimestampSemantics.EVENT_DATE_ONLY,
        revision_semantics=RevisionSemantics.IMMUTABLE_SNAPSHOT,
        t0_policy=policy,
        reliability=ReliabilityGrade.MEDIUM,
        coverage_start=date(2000, 1, 1),
        coverage_end=date(2026, 12, 31),
        derived_from_features=dependencies,
    )


def test_dependency_closure_is_transitive_and_deterministic() -> None:
    registry = FeatureAvailabilityRegistry(
        (
            _contract("raw_points"),
            _contract("serve_state", dependencies=("raw_points",)),
            _contract("matchup_state", dependencies=("serve_state",)),
        )
    )

    assert registry.dependency_closure(("matchup_state",)) == (
        "matchup_state",
        "raw_points",
        "serve_state",
    )
    registry.assert_canonical_eligible(("matchup_state",))


def test_unregistered_dependency_fails_registry_construction() -> None:
    with pytest.raises(ValueError, match="dependency is unregistered"):
        FeatureAvailabilityRegistry(
            (_contract("derived", dependencies=("missing_source",)),)
        )


def test_dependency_cycle_fails_registry_construction() -> None:
    with pytest.raises(ValueError, match="dependency cycle"):
        FeatureAvailabilityRegistry(
            (
                _contract("a", dependencies=("b",)),
                _contract("b", dependencies=("a",)),
            )
        )


def test_unverified_dependency_blocks_otherwise_canonical_derived_feature() -> None:
    registry = FeatureAvailabilityRegistry(
        (
            _contract("target_context", policy=T0Policy.RESEARCH_ONLY_UNVERIFIED),
            _contract("derived_state", dependencies=("target_context",)),
        )
    )

    with pytest.raises(ValueError, match="target_context"):
        registry.assert_canonical_eligible(("derived_state",))


def test_sackmann_canonical_state_closure_includes_only_audited_inputs() -> None:
    registry = sackmann_research_availability_registry(
        source_manifest_sha256="b" * 64,
        coverage_start=date(2000, 1, 1),
        coverage_end=date(2025, 12, 31),
    )

    closure = registry.dependency_closure(("elo_state", "serve_return_state"))
    assert closure == (
        "elo_state",
        "prior_match_outcome",
        "prior_match_stats",
        "serve_return_state",
    )
    registry.assert_canonical_eligible(("elo_state", "serve_return_state"))
    assert "target_ranking" not in closure
    assert "target_event_context" not in closure
