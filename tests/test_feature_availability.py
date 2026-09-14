from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from tennis_genome.data.availability import (
    AvailabilityRule,
    FeatureAvailabilityContract,
    FeatureAvailabilityRegistry,
    FeatureObservation,
    ReliabilityGrade,
    RevisionPolicy,
)


def _contract(**overrides: object) -> FeatureAvailabilityContract:
    payload: dict[str, object] = {
        "feature_id": "rank",
        "version": "1",
        "source_ids": ("historical-rankings-v1",),
        "coverage_start": date(2000, 1, 1),
        "coverage_end": None,
        "availability_rule": AvailabilityRule.EXACT_AVAILABLE_AT,
        "timestamp_semantics": "published ranking snapshot timestamp",
        "revision_policy": RevisionPolicy.REVISION_TRACKED,
        "t0_legality_basis": "available_at must be no later than prediction cutoff",
        "reliability": ReliabilityGrade.VERIFIED,
        "known_missingness": (),
        "known_schema_drift": (),
        "derived_from_features": (),
        "notes": (),
    }
    payload.update(overrides)
    return FeatureAvailabilityContract(**payload)


def test_contract_is_content_addressable_and_immutable() -> None:
    first = _contract()
    second = _contract()

    assert first.semantic_sha256 == second.semantic_sha256
    with pytest.raises(ValidationError):
        first.version = "2"  # type: ignore[misc]


def test_unestablished_feature_must_be_explicitly_unverified() -> None:
    with pytest.raises(ValidationError, match="UNVERIFIED"):
        _contract(
            availability_rule=AvailabilityRule.NOT_ESTABLISHED,
            reliability=ReliabilityGrade.RESEARCH_ONLY,
        )


def test_retrospective_reconstruction_cannot_use_weak_prematch_assertion() -> None:
    with pytest.raises(ValidationError, match="retrospectively reconstructed"):
        _contract(
            revision_policy=RevisionPolicy.RETROSPECTIVE_RECONSTRUCTION,
            availability_rule=AvailabilityRule.SOURCE_ASSERTED_PREMATCH,
        )


def test_registry_rejects_conflicting_contract_for_same_feature() -> None:
    registry = FeatureAvailabilityRegistry((_contract(),))

    with pytest.raises(ValueError, match="different availability content"):
        registry.add(_contract(timestamp_semantics="changed semantics"))


def test_registry_identity_changes_with_availability_semantics() -> None:
    first = FeatureAvailabilityRegistry((_contract(),))
    second = FeatureAvailabilityRegistry((_contract(),))
    changed = FeatureAvailabilityRegistry(
        (_contract(known_schema_drift=("coverage changed in 2016",)),)
    )

    assert first.semantic_sha256 == second.semantic_sha256
    assert first.semantic_sha256 != changed.semantic_sha256


def test_feature_set_fails_closed_without_contract_or_with_unresolved_t0() -> None:
    registry = FeatureAvailabilityRegistry((_contract(),))

    with pytest.raises(ValueError, match="lacks availability contracts"):
        registry.assert_feature_set_research_legal(("rank", "duration"))
    registry.assert_feature_set_research_legal(("rank",))

    unresolved = _contract(
        feature_id="indoor",
        source_ids=("historical-events-v1",),
        availability_rule=AvailabilityRule.NOT_ESTABLISHED,
        revision_policy=RevisionPolicy.UNKNOWN,
        reliability=ReliabilityGrade.UNVERIFIED,
        t0_legality_basis="historical availability not audited",
    )
    unresolved_registry = FeatureAvailabilityRegistry((_contract(), unresolved))
    with pytest.raises(ValueError, match="unresolved T0"):
        unresolved_registry.assert_feature_set_research_legal(("rank", "indoor"))


def test_exact_availability_requires_timestamp_before_cutoff() -> None:
    registry = FeatureAvailabilityRegistry((_contract(),))
    cutoff = datetime(2026, 9, 14, 15, 0, tzinfo=UTC)

    registry.assert_observation_legal(
        observation=FeatureObservation(
            feature_id="rank",
            source_id="historical-rankings-v1",
            source_record_id="rank-001",
            event_time=datetime(2026, 9, 14, 0, 0, tzinfo=UTC),
            available_at=datetime(2026, 9, 14, 8, 0, tzinfo=UTC),
        ),
        prediction_cutoff_at=cutoff,
    )

    with pytest.raises(ValueError, match="after prediction cutoff"):
        registry.assert_observation_legal(
            observation=FeatureObservation(
                feature_id="rank",
                source_id="historical-rankings-v1",
                source_record_id="rank-002",
                event_time=datetime(2026, 9, 14, 0, 0, tzinfo=UTC),
                available_at=datetime(2026, 9, 14, 16, 0, tzinfo=UTC),
            ),
            prediction_cutoff_at=cutoff,
        )

    with pytest.raises(ValueError, match="requires available_at"):
        registry.assert_observation_legal(
            observation=FeatureObservation(
                feature_id="rank",
                source_id="historical-rankings-v1",
                source_record_id="rank-003",
                event_time=datetime(2026, 9, 14, 0, 0, tzinfo=UTC),
            ),
            prediction_cutoff_at=cutoff,
        )


def test_date_only_contract_enforces_prior_calendar_date_freeze() -> None:
    contract = _contract(
        feature_id="prior_match_duration",
        source_ids=("match-history-v1",),
        availability_rule=AvailabilityRule.PRIOR_CALENDAR_DATE_ONLY,
        timestamp_semantics="source provides event date but no trustworthy match start time",
        revision_policy=RevisionPolicy.IMMUTABLE_SNAPSHOT,
        t0_legality_basis="only dates strictly before target UTC date may update state",
        reliability=ReliabilityGrade.CONSTRAINED,
    )
    registry = FeatureAvailabilityRegistry((contract,))
    cutoff = datetime(2026, 9, 14, 18, 0, tzinfo=UTC)

    registry.assert_observation_legal(
        observation=FeatureObservation(
            feature_id="prior_match_duration",
            source_id="match-history-v1",
            source_record_id="m-previous",
            event_time=datetime(2026, 9, 13, 23, 0, tzinfo=UTC),
        ),
        prediction_cutoff_at=cutoff,
    )

    with pytest.raises(ValueError, match="prior calendar date"):
        registry.assert_observation_legal(
            observation=FeatureObservation(
                feature_id="prior_match_duration",
                source_id="match-history-v1",
                source_record_id="m-same-day",
                event_time=datetime(2026, 9, 14, 9, 0, tzinfo=UTC),
            ),
            prediction_cutoff_at=cutoff,
        )


def test_observation_rejects_wrong_source_and_out_of_coverage_date() -> None:
    contract = _contract(coverage_end=date(2025, 12, 31))
    registry = FeatureAvailabilityRegistry((contract,))
    cutoff = datetime(2026, 1, 2, 12, 0, tzinfo=UTC)

    with pytest.raises(ValueError, match="not authorized"):
        registry.assert_observation_legal(
            observation=FeatureObservation(
                feature_id="rank",
                source_id="other-source",
                source_record_id="x",
                event_time=datetime(2025, 12, 30, 0, 0, tzinfo=UTC),
                available_at=datetime(2025, 12, 30, 1, 0, tzinfo=UTC),
            ),
            prediction_cutoff_at=cutoff,
        )

    with pytest.raises(ValueError, match="outside contracted historical coverage"):
        registry.assert_observation_legal(
            observation=FeatureObservation(
                feature_id="rank",
                source_id="historical-rankings-v1",
                source_record_id="y",
                event_time=datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
                available_at=datetime(2026, 1, 1, 1, 0, tzinfo=UTC),
            ),
            prediction_cutoff_at=cutoff,
        )


def test_source_asserted_prematch_requires_known_revision_semantics() -> None:
    contract = _contract(
        feature_id="seed",
        source_ids=("draw-source-v1",),
        availability_rule=AvailabilityRule.SOURCE_ASSERTED_PREMATCH,
        revision_policy=RevisionPolicy.UNKNOWN,
        timestamp_semantics="source row labels value as pre-match",
        t0_legality_basis="source assertion pending revision audit",
        reliability=ReliabilityGrade.RESEARCH_ONLY,
    )
    registry = FeatureAvailabilityRegistry((contract,))

    with pytest.raises(ValueError, match="revision semantics"):
        registry.assert_observation_legal(
            observation=FeatureObservation(
                feature_id="seed",
                source_id="draw-source-v1",
                source_record_id="seed-1",
                event_time=datetime(2025, 1, 1, 0, 0, tzinfo=UTC),
            ),
            prediction_cutoff_at=datetime(2025, 1, 2, 0, 0, tzinfo=UTC),
        )
