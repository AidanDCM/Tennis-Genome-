from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from enum import StrEnum

from pydantic import field_validator, model_validator

from .contracts import WorkbenchRecord


class TimestampSemantics(StrEnum):
    """What time meaning the upstream source actually preserves."""

    EXACT_AVAILABLE_AT = "EXACT_AVAILABLE_AT"
    EVENT_DATE_ONLY = "EVENT_DATE_ONLY"
    SNAPSHOT_TIME = "SNAPSHOT_TIME"
    STATIC_REFERENCE = "STATIC_REFERENCE"


class RevisionSemantics(StrEnum):
    """Whether historical values can change after first observation."""

    IMMUTABLE_SNAPSHOT = "IMMUTABLE_SNAPSHOT"
    APPEND_ONLY = "APPEND_ONLY"
    RETROSPECTIVELY_REVISED = "RETROSPECTIVELY_REVISED"
    LATEST_ONLY_UNKNOWN_HISTORY = "LATEST_ONLY_UNKNOWN_HISTORY"


class T0Policy(StrEnum):
    """How a feature may legally enter a forecasting procedure."""

    VERIFIED_PREMATCH = "VERIFIED_PREMATCH"
    CONSERVATIVE_PRIOR_DATE_ONLY = "CONSERVATIVE_PRIOR_DATE_ONLY"
    POST_MATCH_STATE_UPDATE_ONLY = "POST_MATCH_STATE_UPDATE_ONLY"
    RESEARCH_ONLY_UNVERIFIED = "RESEARCH_ONLY_UNVERIFIED"
    FORBIDDEN = "FORBIDDEN"


class ReliabilityGrade(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


class FeatureAvailabilityContract(WorkbenchRecord):
    """Point-in-time legality contract for one feature or source-derived state input."""

    feature_id: str
    version: str
    source_id: str
    source_manifest_sha256: str
    timestamp_semantics: TimestampSemantics
    revision_semantics: RevisionSemantics
    t0_policy: T0Policy
    reliability: ReliabilityGrade
    coverage_start: date | None = None
    coverage_end: date | None = None
    known_missingness: tuple[str, ...] = ()
    known_schema_breaks: tuple[str, ...] = ()
    derived_from_features: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    @field_validator(
        "feature_id",
        "version",
        "source_id",
    )
    @classmethod
    def _nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("feature availability identifiers must be nonblank")
        return value

    @field_validator("source_manifest_sha256")
    @classmethod
    def _sha256(cls, value: str) -> str:
        if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
            raise ValueError("source_manifest_sha256 must be lowercase SHA-256")
        return value

    @field_validator("known_missingness", "known_schema_breaks", "derived_from_features", "notes")
    @classmethod
    def _unique_text(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("availability text fields must not contain duplicates")
        if any(not item.strip() for item in value):
            raise ValueError("availability text fields must not contain blanks")
        return value

    @model_validator(mode="after")
    def _validate_contract(self) -> FeatureAvailabilityContract:
        if (
            self.coverage_start is not None
            and self.coverage_end is not None
            and self.coverage_end < self.coverage_start
        ):
            raise ValueError("feature availability coverage bounds are reversed")

        if (
            self.t0_policy == T0Policy.VERIFIED_PREMATCH
            and self.timestamp_semantics == TimestampSemantics.EVENT_DATE_ONLY
        ):
            raise ValueError(
                "date-only source cannot claim VERIFIED_PREMATCH without exact availability"
            )

        if (
            self.t0_policy == T0Policy.POST_MATCH_STATE_UPDATE_ONLY
            and self.timestamp_semantics == TimestampSemantics.STATIC_REFERENCE
        ):
            raise ValueError("static reference data cannot be a post-match state update")
        return self


class FeatureAvailabilityRegistry:
    """Deterministic registry identity for an audited feature-availability set."""

    def __init__(self, contracts: tuple[FeatureAvailabilityContract, ...] = ()) -> None:
        self._contracts: dict[str, FeatureAvailabilityContract] = {}
        for contract in contracts:
            self.add(contract)

    def add(self, contract: FeatureAvailabilityContract) -> None:
        existing = self._contracts.get(contract.feature_id)
        if existing is not None:
            if existing.semantic_sha256 != contract.semantic_sha256:
                raise ValueError(
                    f"feature_id {contract.feature_id!r} already has different availability content"
                )
            return
        self._contracts[contract.feature_id] = contract

    def get(self, feature_id: str) -> FeatureAvailabilityContract:
        try:
            return self._contracts[feature_id]
        except KeyError as exc:
            raise KeyError(f"unknown feature availability contract {feature_id!r}") from exc

    def contracts(self) -> tuple[FeatureAvailabilityContract, ...]:
        return tuple(self._contracts[key] for key in sorted(self._contracts))

    @property
    def semantic_sha256(self) -> str:
        payload = {
            "kind": "tennis-feature-availability-registry-v1",
            "contracts": [
                {
                    "semantic_sha256": contract.semantic_sha256,
                    "contract": contract.canonical_payload(),
                }
                for contract in self.contracts()
            ],
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def assert_registered(self, feature_ids: tuple[str, ...]) -> None:
        missing = sorted(set(feature_ids) - set(self._contracts))
        if missing:
            raise ValueError(
                "feature set lacks availability contracts: " + ", ".join(missing)
            )

    def assert_canonical_eligible(self, feature_ids: tuple[str, ...]) -> None:
        self.assert_registered(feature_ids)
        blocked = sorted(
            feature_id
            for feature_id in feature_ids
            if self._contracts[feature_id].t0_policy
            in {T0Policy.RESEARCH_ONLY_UNVERIFIED, T0Policy.FORBIDDEN}
        )
        if blocked:
            raise ValueError(
                "feature set contains non-canonical availability contracts: "
                + ", ".join(blocked)
            )


class FeatureObservation(WorkbenchRecord):
    """Evidence describing when one source observation became available."""

    feature_id: str
    source_match_id: str | None = None
    source_event_date: date | None = None
    available_at: datetime | None = None
    source_snapshot_at: datetime | None = None

    @field_validator("available_at", "source_snapshot_at")
    @classmethod
    def _aware_datetime(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("availability timestamps must be timezone-aware")
        return value.astimezone(UTC)


class TargetBoundary(WorkbenchRecord):
    """The target match boundary against which T0 legality is judged."""

    match_id: str
    event_date: date
    event_start_at: datetime | None = None

    @field_validator("event_start_at")
    @classmethod
    def _aware_start(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("target event_start_at must be timezone-aware")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def _date_matches_start(self) -> TargetBoundary:
        if (
            self.event_start_at is not None
            and self.event_start_at.date() != self.event_date
        ):
            raise ValueError("target event_date must equal event_start_at UTC date")
        return self


class AvailabilityDecision(WorkbenchRecord):
    """Deterministic result of applying one feature contract at one target boundary."""

    feature_id: str
    target_match_id: str
    legal: bool
    reason: str


def evaluate_feature_availability(
    *,
    contract: FeatureAvailabilityContract,
    observation: FeatureObservation,
    target: TargetBoundary,
) -> AvailabilityDecision:
    """Evaluate one feature observation against a target T0 boundary.

    The function deliberately does not infer timing facts that the source does not carry.
    Date-only historical observations may influence only later UTC dates unless the
    contract declares a different, externally verified timing policy.
    """

    if observation.feature_id != contract.feature_id:
        raise ValueError("observation feature_id does not match availability contract")

    if (
        contract.coverage_start is not None
        and target.event_date < contract.coverage_start
    ):
        return AvailabilityDecision(
            feature_id=contract.feature_id,
            target_match_id=target.match_id,
            legal=False,
            reason="target predates feature coverage",
        )
    if contract.coverage_end is not None and target.event_date > contract.coverage_end:
        return AvailabilityDecision(
            feature_id=contract.feature_id,
            target_match_id=target.match_id,
            legal=False,
            reason="target postdates feature coverage",
        )

    if contract.t0_policy == T0Policy.FORBIDDEN:
        return AvailabilityDecision(
            feature_id=contract.feature_id,
            target_match_id=target.match_id,
            legal=False,
            reason="feature is forbidden for forecasting",
        )
    if contract.t0_policy == T0Policy.RESEARCH_ONLY_UNVERIFIED:
        return AvailabilityDecision(
            feature_id=contract.feature_id,
            target_match_id=target.match_id,
            legal=False,
            reason="feature point-in-time legality is unverified",
        )

    if contract.t0_policy == T0Policy.VERIFIED_PREMATCH:
        if observation.available_at is None or target.event_start_at is None:
            return AvailabilityDecision(
                feature_id=contract.feature_id,
                target_match_id=target.match_id,
                legal=False,
                reason="verified pre-match policy requires exact availability and start times",
            )
        if observation.available_at >= target.event_start_at:
            return AvailabilityDecision(
                feature_id=contract.feature_id,
                target_match_id=target.match_id,
                legal=False,
                reason="feature was not available strictly before target start",
            )
        return AvailabilityDecision(
            feature_id=contract.feature_id,
            target_match_id=target.match_id,
            legal=True,
            reason="exact availability precedes target start",
        )

    if contract.t0_policy in {
        T0Policy.CONSERVATIVE_PRIOR_DATE_ONLY,
        T0Policy.POST_MATCH_STATE_UPDATE_ONLY,
    }:
        if observation.source_event_date is None:
            return AvailabilityDecision(
                feature_id=contract.feature_id,
                target_match_id=target.match_id,
                legal=False,
                reason="date-level policy requires source_event_date",
            )
        if observation.source_event_date >= target.event_date:
            return AvailabilityDecision(
                feature_id=contract.feature_id,
                target_match_id=target.match_id,
                legal=False,
                reason="date-level source may influence only a later UTC date",
            )
        return AvailabilityDecision(
            feature_id=contract.feature_id,
            target_match_id=target.match_id,
            legal=True,
            reason="source observation is from an earlier UTC date",
        )

    raise AssertionError(f"unhandled T0 policy: {contract.t0_policy}")


def assert_features_available(
    *,
    contracts: tuple[FeatureAvailabilityContract, ...],
    observations: tuple[FeatureObservation, ...],
    target: TargetBoundary,
) -> tuple[AvailabilityDecision, ...]:
    """Fail closed unless every registered feature observation is legal at T0."""

    by_feature = {contract.feature_id: contract for contract in contracts}
    if len(by_feature) != len(contracts):
        raise ValueError("feature availability contracts must have unique feature_id values")

    by_observation = {observation.feature_id: observation for observation in observations}
    if len(by_observation) != len(observations):
        raise ValueError("feature observations must have unique feature_id values")

    missing = sorted(set(by_feature) - set(by_observation))
    extra = sorted(set(by_observation) - set(by_feature))
    if missing:
        raise ValueError("missing feature availability observations: " + ", ".join(missing))
    if extra:
        raise ValueError("unregistered feature availability observations: " + ", ".join(extra))

    decisions = tuple(
        evaluate_feature_availability(
            contract=by_feature[feature_id],
            observation=by_observation[feature_id],
            target=target,
        )
        for feature_id in sorted(by_feature)
    )
    illegal = [decision for decision in decisions if not decision.legal]
    if illegal:
        detail = "; ".join(
            f"{decision.feature_id}: {decision.reason}" for decision in illegal
        )
        raise ValueError("feature availability contract violation: " + detail)
    return decisions
