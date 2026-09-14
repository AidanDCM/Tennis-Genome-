from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class AvailabilityRule(StrEnum):
    """How a feature proves that its value was legal at prediction time."""

    EXACT_AVAILABLE_AT = "EXACT_AVAILABLE_AT"
    PRIOR_CALENDAR_DATE_ONLY = "PRIOR_CALENDAR_DATE_ONLY"
    SOURCE_ASSERTED_PREMATCH = "SOURCE_ASSERTED_PREMATCH"
    NOT_ESTABLISHED = "NOT_ESTABLISHED"


class RevisionPolicy(StrEnum):
    IMMUTABLE_SNAPSHOT = "IMMUTABLE_SNAPSHOT"
    REVISION_TRACKED = "REVISION_TRACKED"
    RETROSPECTIVE_RECONSTRUCTION = "RETROSPECTIVE_RECONSTRUCTION"
    UNKNOWN = "UNKNOWN"


class ReliabilityGrade(StrEnum):
    VERIFIED = "VERIFIED"
    CONSTRAINED = "CONSTRAINED"
    RESEARCH_ONLY = "RESEARCH_ONLY"
    UNVERIFIED = "UNVERIFIED"


class FeatureAvailabilityContract(BaseModel):
    """Point-in-time legality contract for one research feature.

    Presence in a historical row is not evidence that the feature was knowable at T0.
    This contract records the source, coverage, timestamp semantics, revision behavior,
    known missingness/schema drift, and the exact rule used to decide legality.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    feature_id: str
    version: str
    source_ids: tuple[str, ...]
    coverage_start: date
    coverage_end: date | None = None
    availability_rule: AvailabilityRule
    timestamp_semantics: str
    revision_policy: RevisionPolicy
    t0_legality_basis: str
    reliability: ReliabilityGrade
    known_missingness: tuple[str, ...] = ()
    known_schema_drift: tuple[str, ...] = ()
    derived_from_features: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    @field_validator(
        "source_ids",
        "known_missingness",
        "known_schema_drift",
        "derived_from_features",
        "notes",
    )
    @classmethod
    def _validate_tuple_fields(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("feature-availability tuple fields must be unique")
        if any(not item.strip() for item in value):
            raise ValueError("feature-availability tuple fields must be nonblank")
        return value

    @model_validator(mode="after")
    def _validate_contract(self) -> FeatureAvailabilityContract:
        for label, value in (
            ("feature_id", self.feature_id),
            ("version", self.version),
            ("timestamp_semantics", self.timestamp_semantics),
            ("t0_legality_basis", self.t0_legality_basis),
        ):
            if not value.strip():
                raise ValueError(f"{label} must be nonblank")
        if not self.source_ids:
            raise ValueError("feature availability requires at least one source_id")
        if self.coverage_end is not None and self.coverage_end < self.coverage_start:
            raise ValueError("coverage_end cannot precede coverage_start")
        if (
            self.availability_rule == AvailabilityRule.NOT_ESTABLISHED
            and self.reliability != ReliabilityGrade.UNVERIFIED
        ):
            raise ValueError(
                "NOT_ESTABLISHED availability must carry UNVERIFIED reliability"
            )
        if (
            self.revision_policy == RevisionPolicy.RETROSPECTIVE_RECONSTRUCTION
            and self.availability_rule == AvailabilityRule.SOURCE_ASSERTED_PREMATCH
        ):
            raise ValueError(
                "retrospectively reconstructed fields cannot rely only on source pre-match assertion"
            )
        return self

    def canonical_payload(self) -> dict[str, object]:
        return self.model_dump(mode="json")

    @property
    def semantic_sha256(self) -> str:
        encoded = json.dumps(
            self.canonical_payload(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def covers(self, event_date: date) -> bool:
        if event_date < self.coverage_start:
            return False
        if self.coverage_end is not None and event_date > self.coverage_end:
            return False
        return True


class FeatureObservation(BaseModel):
    """One source observation considered for use in a target prediction."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    feature_id: str
    source_id: str
    source_record_id: str
    event_time: datetime
    available_at: datetime | None = None

    @field_validator("feature_id", "source_id", "source_record_id")
    @classmethod
    def _nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("feature observation identifiers must be nonblank")
        return value

    @field_validator("event_time", "available_at")
    @classmethod
    def _aware_time(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("feature observation timestamps must be timezone-aware")
        return value.astimezone(UTC)


class FeatureAvailabilityRegistry:
    """Immutable-by-identity registry used to fail closed on illegal research features."""

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
            raise KeyError(f"no availability contract for feature_id {feature_id!r}") from exc

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

    def assert_feature_set_research_legal(self, feature_ids: tuple[str, ...]) -> None:
        missing = sorted(set(feature_ids) - set(self._contracts))
        if missing:
            raise ValueError(
                "feature set lacks availability contracts: " + ", ".join(missing)
            )
        unresolved = sorted(
            feature_id
            for feature_id in feature_ids
            if self._contracts[feature_id].availability_rule
            == AvailabilityRule.NOT_ESTABLISHED
        )
        if unresolved:
            raise ValueError(
                "feature set contains unresolved T0 availability: " + ", ".join(unresolved)
            )

    def assert_observation_legal(
        self,
        *,
        observation: FeatureObservation,
        prediction_cutoff_at: datetime,
    ) -> None:
        if prediction_cutoff_at.tzinfo is None or prediction_cutoff_at.utcoffset() is None:
            raise ValueError("prediction_cutoff_at must be timezone-aware")
        cutoff = prediction_cutoff_at.astimezone(UTC)
        contract = self.get(observation.feature_id)
        if observation.source_id not in contract.source_ids:
            raise ValueError("feature observation source is not authorized by its contract")
        if not contract.covers(observation.event_time.date()):
            raise ValueError("feature observation falls outside contracted historical coverage")

        rule = contract.availability_rule
        if rule == AvailabilityRule.NOT_ESTABLISHED:
            raise ValueError("feature T0 availability is not established")

        if rule == AvailabilityRule.EXACT_AVAILABLE_AT:
            if observation.available_at is None:
                raise ValueError("exact-availability feature requires available_at")
            if observation.available_at > cutoff:
                raise ValueError("feature became available after prediction cutoff")
            return

        if rule == AvailabilityRule.PRIOR_CALENDAR_DATE_ONLY:
            if observation.event_time.date() >= cutoff.date():
                raise ValueError(
                    "date-only feature may update state only from a prior calendar date"
                )
            if observation.available_at is not None and observation.available_at > cutoff:
                raise ValueError("feature became available after prediction cutoff")
            return

        if rule == AvailabilityRule.SOURCE_ASSERTED_PREMATCH:
            if contract.revision_policy in {
                RevisionPolicy.UNKNOWN,
                RevisionPolicy.RETROSPECTIVE_RECONSTRUCTION,
            }:
                raise ValueError(
                    "source-asserted pre-match feature lacks acceptable revision semantics"
                )
            if observation.available_at is not None and observation.available_at > cutoff:
                raise ValueError("feature became available after prediction cutoff")
            return

        raise AssertionError(f"unsupported availability rule: {rule}")
