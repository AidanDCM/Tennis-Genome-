from __future__ import annotations

from datetime import date

from .availability import (
    FeatureAvailabilityContract,
    FeatureAvailabilityRegistry,
    ReliabilityGrade,
    RevisionSemantics,
    T0Policy,
    TimestampSemantics,
)

SACKMANN_RESEARCH_SOURCE_ID = "sackmann-style-match-csv"


def sackmann_research_availability_registry(
    *,
    source_manifest_sha256: str,
    coverage_start: date,
    coverage_end: date,
) -> FeatureAvailabilityRegistry:
    """Conservative v2 availability profile for the current Sackmann-style source.

    This profile deliberately distinguishes what the source can support safely from what
    merely appears in a target row. Match-level outcomes/statistics may update historical
    state only on a later UTC date because the source does not provide trusted match-start
    chronology. Direct target-row ranking/context fields remain research-only/unverified
    until historical publication/availability semantics are independently established.
    """

    common = {
        "source_id": SACKMANN_RESEARCH_SOURCE_ID,
        "source_manifest_sha256": source_manifest_sha256,
        "coverage_start": coverage_start,
        "coverage_end": coverage_end,
    }

    contracts = (
        FeatureAvailabilityContract(
            feature_id="prior_match_outcome",
            version="sackmann-audit-001",
            timestamp_semantics=TimestampSemantics.EVENT_DATE_ONLY,
            revision_semantics=RevisionSemantics.RETROSPECTIVELY_REVISED,
            t0_policy=T0Policy.POST_MATCH_STATE_UPDATE_ONLY,
            reliability=ReliabilityGrade.MEDIUM,
            known_schema_breaks=(
                "source rows do not provide trustworthy per-match start chronology",
            ),
            notes=(
                "May update derived outcome state only for target dates strictly after the source event date.",
            ),
            **common,
        ),
        FeatureAvailabilityContract(
            feature_id="prior_match_stats",
            version="sackmann-audit-001",
            timestamp_semantics=TimestampSemantics.EVENT_DATE_ONLY,
            revision_semantics=RevisionSemantics.RETROSPECTIVELY_REVISED,
            t0_policy=T0Policy.POST_MATCH_STATE_UPDATE_ONLY,
            reliability=ReliabilityGrade.MEDIUM,
            known_missingness=(
                "match-stat coverage is incomplete and changes materially across eras and competitions",
            ),
            known_schema_breaks=(
                "coverage and completeness vary through history",
                "source rows do not provide trustworthy per-match start chronology",
            ),
            notes=(
                "Stats are post-match observations and may influence only later UTC target dates.",
            ),
            **common,
        ),
        FeatureAvailabilityContract(
            feature_id="prior_match_duration",
            version="sackmann-audit-001",
            timestamp_semantics=TimestampSemantics.EVENT_DATE_ONLY,
            revision_semantics=RevisionSemantics.RETROSPECTIVELY_REVISED,
            t0_policy=T0Policy.POST_MATCH_STATE_UPDATE_ONLY,
            reliability=ReliabilityGrade.LOW,
            known_missingness=(
                "duration is absent for many historical rows and coverage changes by era",
            ),
            notes=(
                "Missing duration must remain unknown rather than being imputed as zero.",
            ),
            **common,
        ),
        FeatureAvailabilityContract(
            feature_id="elo_state",
            version="sackmann-audit-001",
            timestamp_semantics=TimestampSemantics.EVENT_DATE_ONLY,
            revision_semantics=RevisionSemantics.RETROSPECTIVELY_REVISED,
            t0_policy=T0Policy.CONSERVATIVE_PRIOR_DATE_ONLY,
            reliability=ReliabilityGrade.MEDIUM,
            derived_from_features=("prior_match_outcome",),
            notes=(
                "State must freeze for the full target date and update only from earlier dates.",
            ),
            **common,
        ),
        FeatureAvailabilityContract(
            feature_id="serve_return_state",
            version="sackmann-audit-001",
            timestamp_semantics=TimestampSemantics.EVENT_DATE_ONLY,
            revision_semantics=RevisionSemantics.RETROSPECTIVELY_REVISED,
            t0_policy=T0Policy.CONSERVATIVE_PRIOR_DATE_ONLY,
            reliability=ReliabilityGrade.MEDIUM,
            derived_from_features=("prior_match_stats",),
            notes=(
                "Opponent-adjusted point state is legal only when built entirely from earlier UTC dates.",
            ),
            **common,
        ),
        FeatureAvailabilityContract(
            feature_id="form_result_state",
            version="sackmann-audit-001",
            timestamp_semantics=TimestampSemantics.EVENT_DATE_ONLY,
            revision_semantics=RevisionSemantics.RETROSPECTIVELY_REVISED,
            t0_policy=T0Policy.CONSERVATIVE_PRIOR_DATE_ONLY,
            reliability=ReliabilityGrade.MEDIUM,
            derived_from_features=("prior_match_outcome",),
            **common,
        ),
        FeatureAvailabilityContract(
            feature_id="form_point_state",
            version="sackmann-audit-001",
            timestamp_semantics=TimestampSemantics.EVENT_DATE_ONLY,
            revision_semantics=RevisionSemantics.RETROSPECTIVELY_REVISED,
            t0_policy=T0Policy.CONSERVATIVE_PRIOR_DATE_ONLY,
            reliability=ReliabilityGrade.MEDIUM,
            derived_from_features=("prior_match_stats",),
            **common,
        ),
        FeatureAvailabilityContract(
            feature_id="workload_state",
            version="sackmann-audit-001",
            timestamp_semantics=TimestampSemantics.EVENT_DATE_ONLY,
            revision_semantics=RevisionSemantics.RETROSPECTIVELY_REVISED,
            t0_policy=T0Policy.CONSERVATIVE_PRIOR_DATE_ONLY,
            reliability=ReliabilityGrade.LOW,
            derived_from_features=("prior_match_duration",),
            known_missingness=(
                "duration completeness is insufficiently stable for exact workload reconstruction",
            ),
            **common,
        ),
        FeatureAvailabilityContract(
            feature_id="target_ranking",
            version="sackmann-audit-001",
            timestamp_semantics=TimestampSemantics.EVENT_DATE_ONLY,
            revision_semantics=RevisionSemantics.LATEST_ONLY_UNKNOWN_HISTORY,
            t0_policy=T0Policy.RESEARCH_ONLY_UNVERIFIED,
            reliability=ReliabilityGrade.LOW,
            notes=(
                "Upstream documentation says ranking is as of tourney_date, usually near event start; exact historical publication availability for the target match is not established.",
            ),
            **common,
        ),
        FeatureAvailabilityContract(
            feature_id="target_ranking_points",
            version="sackmann-audit-001",
            timestamp_semantics=TimestampSemantics.EVENT_DATE_ONLY,
            revision_semantics=RevisionSemantics.LATEST_ONLY_UNKNOWN_HISTORY,
            t0_policy=T0Policy.RESEARCH_ONLY_UNVERIFIED,
            reliability=ReliabilityGrade.LOW,
            notes=(
                "Exact target-match availability semantics remain unresolved.",
            ),
            **common,
        ),
        FeatureAvailabilityContract(
            feature_id="target_age",
            version="sackmann-audit-001",
            timestamp_semantics=TimestampSemantics.EVENT_DATE_ONLY,
            revision_semantics=RevisionSemantics.LATEST_ONLY_UNKNOWN_HISTORY,
            t0_policy=T0Policy.RESEARCH_ONLY_UNVERIFIED,
            reliability=ReliabilityGrade.LOW,
            notes=(
                "Upstream documentation says age is as of tourney_date, not an exact match-start observation.",
            ),
            **common,
        ),
        FeatureAvailabilityContract(
            feature_id="target_event_context",
            version="sackmann-audit-001",
            timestamp_semantics=TimestampSemantics.EVENT_DATE_ONLY,
            revision_semantics=RevisionSemantics.LATEST_ONLY_UNKNOWN_HISTORY,
            t0_policy=T0Policy.RESEARCH_ONLY_UNVERIFIED,
            reliability=ReliabilityGrade.LOW,
            notes=(
                "Surface, round, seed, entry, best-of and related target context require a separate historical availability audit before canonical v2 use.",
            ),
            **common,
        ),
        FeatureAvailabilityContract(
            feature_id="target_player_reference",
            version="sackmann-audit-001",
            timestamp_semantics=TimestampSemantics.STATIC_REFERENCE,
            revision_semantics=RevisionSemantics.LATEST_ONLY_UNKNOWN_HISTORY,
            t0_policy=T0Policy.RESEARCH_ONLY_UNVERIFIED,
            reliability=ReliabilityGrade.LOW,
            notes=(
                "Hand, height and IOC may be retrospectively maintained; historical point-in-time semantics are not yet established.",
            ),
            **common,
        ),
    )
    return FeatureAvailabilityRegistry(contracts)
