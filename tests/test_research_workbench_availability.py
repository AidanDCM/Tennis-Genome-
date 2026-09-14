from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from tennis_genome.research_workbench import (
    FeatureAvailabilityContract,
    FeatureObservation,
    ReliabilityGrade,
    RevisionSemantics,
    T0Policy,
    TargetBoundary,
    TimestampSemantics,
    assert_features_available,
    evaluate_feature_availability,
)


def _contract(
    *,
    feature_id: str = "serve_state",
    timestamp_semantics: TimestampSemantics = TimestampSemantics.EVENT_DATE_ONLY,
    t0_policy: T0Policy = T0Policy.CONSERVATIVE_PRIOR_DATE_ONLY,
) -> FeatureAvailabilityContract:
    return FeatureAvailabilityContract(
        feature_id=feature_id,
        version="1",
        source_id="historical-source-v1",
        source_manifest_sha256="a" * 64,
        timestamp_semantics=timestamp_semantics,
        revision_semantics=RevisionSemantics.IMMUTABLE_SNAPSHOT,
        t0_policy=t0_policy,
        reliability=ReliabilityGrade.MEDIUM,
        coverage_start=date(2000, 1, 1),
        coverage_end=date(2026, 12, 31),
        known_missingness=("point stats incomplete in some eras",),
    )


def test_date_only_source_may_influence_later_date() -> None:
    decision = evaluate_feature_availability(
        contract=_contract(),
        observation=FeatureObservation(
            feature_id="serve_state",
            source_match_id="prior",
            source_event_date=date(2026, 1, 1),
        ),
        target=TargetBoundary(
            match_id="target",
            event_date=date(2026, 1, 2),
        ),
    )

    assert decision.legal is True
    assert "earlier UTC date" in decision.reason


def test_date_only_source_cannot_leak_same_day() -> None:
    decision = evaluate_feature_availability(
        contract=_contract(),
        observation=FeatureObservation(
            feature_id="serve_state",
            source_match_id="prior",
            source_event_date=date(2026, 1, 2),
        ),
        target=TargetBoundary(
            match_id="target",
            event_date=date(2026, 1, 2),
        ),
    )

    assert decision.legal is False
    assert "later UTC date" in decision.reason


def test_post_match_state_update_is_prior_date_only() -> None:
    contract = _contract(
        feature_id="prior_match_points",
        t0_policy=T0Policy.POST_MATCH_STATE_UPDATE_ONLY,
    )
    same_day = evaluate_feature_availability(
        contract=contract,
        observation=FeatureObservation(
            feature_id="prior_match_points",
            source_event_date=date(2026, 2, 1),
        ),
        target=TargetBoundary(match_id="target", event_date=date(2026, 2, 1)),
    )
    later = evaluate_feature_availability(
        contract=contract,
        observation=FeatureObservation(
            feature_id="prior_match_points",
            source_event_date=date(2026, 2, 1),
        ),
        target=TargetBoundary(match_id="target", event_date=date(2026, 2, 2)),
    )

    assert same_day.legal is False
    assert later.legal is True


def test_verified_prematch_requires_exact_time_and_strict_prestart() -> None:
    contract = _contract(
        feature_id="provider_ranking",
        timestamp_semantics=TimestampSemantics.EXACT_AVAILABLE_AT,
        t0_policy=T0Policy.VERIFIED_PREMATCH,
    )
    target = TargetBoundary(
        match_id="target",
        event_date=date(2026, 3, 1),
        event_start_at=datetime(2026, 3, 1, 15, 0, tzinfo=UTC),
    )

    legal = evaluate_feature_availability(
        contract=contract,
        observation=FeatureObservation(
            feature_id="provider_ranking",
            available_at=datetime(2026, 3, 1, 14, 59, tzinfo=UTC),
        ),
        target=target,
    )
    late = evaluate_feature_availability(
        contract=contract,
        observation=FeatureObservation(
            feature_id="provider_ranking",
            available_at=datetime(2026, 3, 1, 15, 0, tzinfo=UTC),
        ),
        target=target,
    )

    assert legal.legal is True
    assert late.legal is False


def test_verified_prematch_cannot_be_claimed_from_date_only_source() -> None:
    with pytest.raises(ValidationError, match="date-only source"):
        _contract(
            timestamp_semantics=TimestampSemantics.EVENT_DATE_ONLY,
            t0_policy=T0Policy.VERIFIED_PREMATCH,
        )


def test_unverified_feature_is_blocked_from_canonical_forecast() -> None:
    decision = evaluate_feature_availability(
        contract=_contract(t0_policy=T0Policy.RESEARCH_ONLY_UNVERIFIED),
        observation=FeatureObservation(
            feature_id="serve_state",
            source_event_date=date(2026, 1, 1),
        ),
        target=TargetBoundary(
            match_id="target",
            event_date=date(2026, 1, 2),
        ),
    )

    assert decision.legal is False
    assert "unverified" in decision.reason


def test_feature_contract_enforces_coverage_window() -> None:
    decision = evaluate_feature_availability(
        contract=_contract(),
        observation=FeatureObservation(
            feature_id="serve_state",
            source_event_date=date(1999, 12, 30),
        ),
        target=TargetBoundary(
            match_id="target",
            event_date=date(1999, 12, 31),
        ),
    )
    assert decision.legal is False
    assert "predates feature coverage" in decision.reason


def test_assert_features_available_fails_closed_on_missing_or_illegal_feature() -> None:
    contracts = (
        _contract(feature_id="elo_state"),
        _contract(feature_id="serve_state"),
    )
    target = TargetBoundary(match_id="target", event_date=date(2026, 4, 2))

    with pytest.raises(ValueError, match="missing feature availability observations"):
        assert_features_available(
            contracts=contracts,
            observations=(
                FeatureObservation(
                    feature_id="elo_state",
                    source_event_date=date(2026, 4, 1),
                ),
            ),
            target=target,
        )

    with pytest.raises(ValueError, match="feature availability contract violation"):
        assert_features_available(
            contracts=contracts,
            observations=(
                FeatureObservation(
                    feature_id="elo_state",
                    source_event_date=date(2026, 4, 1),
                ),
                FeatureObservation(
                    feature_id="serve_state",
                    source_event_date=date(2026, 4, 2),
                ),
            ),
            target=target,
        )


def test_assert_features_available_accepts_complete_legal_set() -> None:
    contracts = (
        _contract(feature_id="elo_state"),
        _contract(feature_id="serve_state"),
    )
    decisions = assert_features_available(
        contracts=contracts,
        observations=(
            FeatureObservation(
                feature_id="elo_state",
                source_event_date=date(2026, 4, 1),
            ),
            FeatureObservation(
                feature_id="serve_state",
                source_event_date=date(2026, 4, 1),
            ),
        ),
        target=TargetBoundary(match_id="target", event_date=date(2026, 4, 2)),
    )

    assert all(decision.legal for decision in decisions)


def test_target_exact_time_must_match_utc_event_date() -> None:
    with pytest.raises(ValidationError, match="event_date must equal"):
        TargetBoundary(
            match_id="target",
            event_date=date(2026, 5, 1),
            event_start_at=datetime(2026, 5, 2, 0, 30, tzinfo=UTC),
        )
