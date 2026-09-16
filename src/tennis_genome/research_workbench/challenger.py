from __future__ import annotations

import math
import re
from datetime import datetime
from typing import Any, Literal, Self

from pydantic import Field, field_validator, model_validator

from tennis_genome.independent.prediction import reject_market_or_outcome_fields

from .contracts import ForecastingProcedureSpec, WorkbenchRecord

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _require_sha256(value: str, *, field_name: str) -> str:
    if not _SHA256_RE.fullmatch(value):
        raise ValueError(f"{field_name} must be a lowercase 64-character SHA-256")
    return value


def _require_aware(value: datetime, *, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value


class ChallengerRegistration(WorkbenchRecord):
    """Frozen identity and governance contract for one shadow challenger."""

    challenger_id: str
    challenger_version: str
    procedure: ForecastingProcedureSpec
    parent_champion_model_version: str
    mode: Literal["SHADOW_ONLY"] = "SHADOW_ONLY"
    feature_schema_sha256: str
    code_sha256: str
    training_population_sha256: str
    training_window: str
    eligibility_contract: str
    promotion_contract: str
    registered_at: datetime

    @field_validator(
        "challenger_id",
        "challenger_version",
        "parent_champion_model_version",
        "training_window",
        "eligibility_contract",
        "promotion_contract",
    )
    @classmethod
    def _nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("challenger string fields must be nonblank")
        return value

    @field_validator("feature_schema_sha256", "code_sha256", "training_population_sha256")
    @classmethod
    def _sha256(cls, value: str, info: Any) -> str:
        return _require_sha256(value, field_name=info.field_name)

    @field_validator("registered_at")
    @classmethod
    def _registered_at_aware(cls, value: datetime) -> datetime:
        return _require_aware(value, field_name="registered_at")

    @model_validator(mode="after")
    def _bind_identity(self) -> Self:
        if self.procedure.procedure_id != self.challenger_id:
            raise ValueError("procedure_id must exactly match challenger_id")
        return self


class CommonPreMatchSnapshot(WorkbenchRecord):
    """Outcome-free, market-blind snapshot shared by champion and challengers."""

    snapshot_id: str
    match_id: str
    provider_event_id: str
    tour: Literal["ATP", "WTA"]
    player_a_id: str
    player_b_id: str
    scheduled_start: datetime
    prediction_cutoff_at: datetime
    captured_at: datetime
    source_manifest_hashes: tuple[str, ...]
    feature_payload_sha256: str
    feature_schema_sha256: str
    feature_payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("snapshot_id", "match_id", "provider_event_id", "player_a_id", "player_b_id")
    @classmethod
    def _identity_nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("snapshot identity fields must be nonblank")
        return value

    @field_validator("scheduled_start", "prediction_cutoff_at", "captured_at")
    @classmethod
    def _aware_datetimes(cls, value: datetime, info: Any) -> datetime:
        return _require_aware(value, field_name=info.field_name)

    @field_validator("feature_payload_sha256", "feature_schema_sha256")
    @classmethod
    def _snapshot_sha256(cls, value: str, info: Any) -> str:
        return _require_sha256(value, field_name=info.field_name)

    @field_validator("source_manifest_hashes")
    @classmethod
    def _source_hashes(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("at least one source manifest hash is required")
        if len(value) != len(set(value)):
            raise ValueError("source manifest hashes must be unique")
        for item in value:
            _require_sha256(item, field_name="source_manifest_hashes")
        return value

    @field_validator("feature_payload")
    @classmethod
    def _outcome_market_firewall(cls, value: dict[str, Any]) -> dict[str, Any]:
        reject_market_or_outcome_fields(value)
        return value

    @model_validator(mode="after")
    def _chronology(self) -> Self:
        if self.player_a_id == self.player_b_id:
            raise ValueError("player identities must differ")
        if self.prediction_cutoff_at > self.captured_at:
            raise ValueError("prediction_cutoff_at cannot be after captured_at")
        if self.captured_at >= self.scheduled_start:
            raise ValueError("pre-match snapshot must be captured before scheduled_start")
        return self


class ShadowModelOutput(WorkbenchRecord):
    """One challenger's probability output computed from the common snapshot."""

    challenger_id: str
    p_player_a: float
    p_player_b: float
    component_probabilities: dict[str, float] = Field(default_factory=dict)
    diagnostics: dict[str, float | int | bool | None] = Field(default_factory=dict)

    @field_validator("challenger_id")
    @classmethod
    def _challenger_nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("challenger_id must be nonblank")
        return value

    @field_validator("p_player_a", "p_player_b")
    @classmethod
    def _probability(cls, value: float) -> float:
        if not math.isfinite(value) or not 0.0 <= value <= 1.0:
            raise ValueError("probabilities must be finite and in [0, 1]")
        return float(value)

    @field_validator("component_probabilities")
    @classmethod
    def _component_probabilities(cls, value: dict[str, float]) -> dict[str, float]:
        reject_market_or_outcome_fields(value)
        for name, probability in value.items():
            if not name.strip():
                raise ValueError("component probability names must be nonblank")
            if not math.isfinite(probability) or not 0.0 <= probability <= 1.0:
                raise ValueError("component probabilities must be finite and in [0, 1]")
        return value

    @field_validator("diagnostics")
    @classmethod
    def _diagnostics_firewall(
        cls, value: dict[str, float | int | bool | None]
    ) -> dict[str, float | int | bool | None]:
        reject_market_or_outcome_fields(value)
        return value

    @model_validator(mode="after")
    def _sum_to_one(self) -> Self:
        if abs((self.p_player_a + self.p_player_b) - 1.0) > 1e-9:
            raise ValueError("player probabilities must sum to one")
        return self


class ShadowPredictionRecord(WorkbenchRecord):
    """Immutable pre-result record for one registered challenger on one snapshot."""

    shadow_prediction_id: str
    registration_sha256: str
    snapshot_sha256: str
    snapshot_id: str
    match_id: str
    provider_event_id: str
    tour: Literal["ATP", "WTA"]
    player_a_id: str
    player_b_id: str
    prediction_cutoff_at: datetime
    scheduled_start: datetime
    created_at: datetime
    output: ShadowModelOutput
    source_manifest_hashes: tuple[str, ...]

    @field_validator("shadow_prediction_id", "snapshot_id", "match_id", "provider_event_id")
    @classmethod
    def _record_identity_nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("shadow prediction identity fields must be nonblank")
        return value

    @field_validator("registration_sha256", "snapshot_sha256")
    @classmethod
    def _record_sha256(cls, value: str, info: Any) -> str:
        return _require_sha256(value, field_name=info.field_name)

    @field_validator("prediction_cutoff_at", "scheduled_start", "created_at")
    @classmethod
    def _record_datetimes(cls, value: datetime, info: Any) -> datetime:
        return _require_aware(value, field_name=info.field_name)

    @field_validator("source_manifest_hashes")
    @classmethod
    def _record_source_hashes(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("at least one source manifest hash is required")
        if len(value) != len(set(value)):
            raise ValueError("source manifest hashes must be unique")
        for item in value:
            _require_sha256(item, field_name="source_manifest_hashes")
        return value

    @model_validator(mode="after")
    def _pre_start(self) -> Self:
        if self.created_at < self.prediction_cutoff_at:
            raise ValueError("created_at cannot be before prediction_cutoff_at")
        if self.created_at >= self.scheduled_start:
            raise ValueError("late challenger prediction is not prospective")
        return self


class ShadowPredictionAnchor(WorkbenchRecord):
    """External pre-start commitment for one immutable shadow prediction."""

    shadow_prediction_id: str
    shadow_prediction_sha256: str
    provider: Literal["GITHUB_ACTIONS"] = "GITHUB_ACTIONS"
    actor: Literal["github-actions[bot]"] = "github-actions[bot]"
    anchor_id: str
    workflow_run_id: int
    created_at: datetime
    updated_at: datetime

    @field_validator("shadow_prediction_id", "anchor_id")
    @classmethod
    def _anchor_identity_nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("anchor identity fields must be nonblank")
        return value

    @field_validator("shadow_prediction_sha256")
    @classmethod
    def _anchor_sha256(cls, value: str) -> str:
        return _require_sha256(value, field_name="shadow_prediction_sha256")

    @field_validator("created_at", "updated_at")
    @classmethod
    def _anchor_datetimes(cls, value: datetime, info: Any) -> datetime:
        return _require_aware(value, field_name=info.field_name)

    @model_validator(mode="after")
    def _unedited(self) -> Self:
        if self.workflow_run_id <= 0:
            raise ValueError("workflow_run_id must be positive")
        if self.created_at != self.updated_at:
            raise ValueError("trusted shadow anchor must be unedited")
        return self


class ShadowSettlementRecord(WorkbenchRecord):
    """Post-result scoring record linked to one immutable shadow prediction."""

    shadow_prediction_id: str
    shadow_prediction_sha256: str
    snapshot_sha256: str
    match_id: str
    provider_event_id: str
    player_a_id: str
    player_b_id: str
    winner_player_id: str
    settled_at: datetime
    settlement_evidence_sha256: str
    correctness: int
    brier: float
    log_loss: float

    @field_validator("shadow_prediction_id", "match_id", "provider_event_id")
    @classmethod
    def _settlement_identity_nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("settlement identity fields must be nonblank")
        return value

    @field_validator(
        "shadow_prediction_sha256", "snapshot_sha256", "settlement_evidence_sha256"
    )
    @classmethod
    def _settlement_sha256(cls, value: str, info: Any) -> str:
        return _require_sha256(value, field_name=info.field_name)

    @field_validator("settled_at")
    @classmethod
    def _settled_at_aware(cls, value: datetime) -> datetime:
        return _require_aware(value, field_name="settled_at")

    @field_validator("correctness")
    @classmethod
    def _binary_correctness(cls, value: int) -> int:
        if value not in (0, 1):
            raise ValueError("correctness must be 0 or 1")
        return value

    @field_validator("brier", "log_loss")
    @classmethod
    def _finite_scores(cls, value: float) -> float:
        if not math.isfinite(value) or value < 0.0:
            raise ValueError("proper scores must be finite and non-negative")
        return float(value)

    @model_validator(mode="after")
    def _winner_in_orientation(self) -> Self:
        if self.player_a_id == self.player_b_id:
            raise ValueError("settlement player identities must differ")
        if self.winner_player_id not in (self.player_a_id, self.player_b_id):
            raise ValueError("settlement winner must match the prediction orientation")
        return self


class ChallengerLeagueRow(WorkbenchRecord):
    challenger_id: str
    n: int
    accuracy: float
    mean_brier: float
    mean_log_loss: float


class FailureAtlasRecord(WorkbenchRecord):
    """Immutable post-settlement row used only to generate future hypotheses."""

    shadow_prediction_id: str
    shadow_prediction_sha256: str
    settlement_sha256: str
    challenger_id: str
    snapshot_sha256: str
    match_id: str
    provider_event_id: str
    p_player_a: float
    outcome_player_a_won: bool
    correctness: int
    brier: float
    log_loss: float
    pre_match_component_probabilities: dict[str, float] = Field(default_factory=dict)
    pre_match_diagnostics: dict[str, float | int | bool | None] = Field(default_factory=dict)
    post_result_diagnostics: dict[str, Any] = Field(default_factory=dict)
    deterministic_tags: tuple[str, ...] = ()
    evidence_role: Literal["POST_RESULT_DIAGNOSTIC_ONLY"] = "POST_RESULT_DIAGNOSTIC_ONLY"

    @field_validator("shadow_prediction_sha256", "settlement_sha256", "snapshot_sha256")
    @classmethod
    def _atlas_sha256(cls, value: str, info: Any) -> str:
        return _require_sha256(value, field_name=info.field_name)

    @field_validator("deterministic_tags")
    @classmethod
    def _unique_tags(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("deterministic_tags must be unique")
        return tuple(sorted(value))


def build_shadow_prediction(
    *,
    registration: ChallengerRegistration,
    snapshot: CommonPreMatchSnapshot,
    output: ShadowModelOutput,
    shadow_prediction_id: str,
    created_at: datetime,
) -> ShadowPredictionRecord:
    """Bind one challenger output to exactly one common pre-match snapshot."""

    if output.challenger_id != registration.challenger_id:
        raise ValueError("challenger output does not match the registration")
    if registration.feature_schema_sha256 != snapshot.feature_schema_sha256:
        raise ValueError("challenger feature schema does not match the common snapshot")
    return ShadowPredictionRecord(
        shadow_prediction_id=shadow_prediction_id,
        registration_sha256=registration.semantic_sha256,
        snapshot_sha256=snapshot.semantic_sha256,
        snapshot_id=snapshot.snapshot_id,
        match_id=snapshot.match_id,
        provider_event_id=snapshot.provider_event_id,
        tour=snapshot.tour,
        player_a_id=snapshot.player_a_id,
        player_b_id=snapshot.player_b_id,
        prediction_cutoff_at=snapshot.prediction_cutoff_at,
        scheduled_start=snapshot.scheduled_start,
        created_at=created_at,
        output=output,
        source_manifest_hashes=snapshot.source_manifest_hashes,
    )


def verify_shadow_anchor(
    *, prediction: ShadowPredictionRecord, anchor: ShadowPredictionAnchor
) -> None:
    if anchor.shadow_prediction_id != prediction.shadow_prediction_id:
        raise ValueError("shadow anchor prediction ID mismatch")
    if anchor.shadow_prediction_sha256 != prediction.semantic_sha256:
        raise ValueError("shadow anchor prediction hash mismatch")
    if anchor.created_at >= prediction.scheduled_start:
        raise ValueError("shadow anchor must exist before scheduled start")
    if anchor.created_at < prediction.created_at:
        raise ValueError("shadow anchor cannot predate the prediction")


def validate_shadow_prediction_set(records: tuple[ShadowPredictionRecord, ...]) -> None:
    """Fail closed on duplicate IDs or mixed snapshots for one side-by-side run."""

    prediction_ids = [record.shadow_prediction_id for record in records]
    if len(prediction_ids) != len(set(prediction_ids)):
        raise ValueError("duplicate shadow prediction IDs are forbidden")
    challenger_ids = [record.output.challenger_id for record in records]
    if len(challenger_ids) != len(set(challenger_ids)):
        raise ValueError("a challenger may appear only once per common snapshot")
    if not records:
        return
    expected = (
        records[0].snapshot_sha256,
        records[0].match_id,
        records[0].provider_event_id,
        records[0].player_a_id,
        records[0].player_b_id,
    )
    for record in records[1:]:
        observed = (
            record.snapshot_sha256,
            record.match_id,
            record.provider_event_id,
            record.player_a_id,
            record.player_b_id,
        )
        if observed != expected:
            raise ValueError("side-by-side shadow predictions must share one snapshot identity")


def settle_shadow_prediction(
    *,
    prediction: ShadowPredictionRecord,
    winner_player_id: str,
    settled_at: datetime,
    settlement_evidence_sha256: str,
) -> ShadowSettlementRecord:
    """Score a shadow prediction without mutating the pre-match record."""

    if winner_player_id not in (prediction.player_a_id, prediction.player_b_id):
        raise ValueError("settlement winner must match the prediction orientation")
    outcome_a = winner_player_id == prediction.player_a_id
    predicted_a = prediction.output.p_player_a >= 0.5
    correctness = int(predicted_a == outcome_a)
    y = 1.0 if outcome_a else 0.0
    probability = min(max(prediction.output.p_player_a, 1e-15), 1.0 - 1e-15)
    brier = (probability - y) ** 2
    log_loss = -(y * math.log(probability) + (1.0 - y) * math.log1p(-probability))
    return ShadowSettlementRecord(
        shadow_prediction_id=prediction.shadow_prediction_id,
        shadow_prediction_sha256=prediction.semantic_sha256,
        snapshot_sha256=prediction.snapshot_sha256,
        match_id=prediction.match_id,
        provider_event_id=prediction.provider_event_id,
        player_a_id=prediction.player_a_id,
        player_b_id=prediction.player_b_id,
        winner_player_id=winner_player_id,
        settled_at=settled_at,
        settlement_evidence_sha256=settlement_evidence_sha256,
        correctness=correctness,
        brier=brier,
        log_loss=log_loss,
    )


def build_league_table(
    *,
    predictions: tuple[ShadowPredictionRecord, ...],
    settlements: tuple[ShadowSettlementRecord, ...],
) -> tuple[ChallengerLeagueRow, ...]:
    """Aggregate only exactly-linked settled shadow records."""

    by_prediction_id = {record.shadow_prediction_id: record for record in predictions}
    if len(by_prediction_id) != len(predictions):
        raise ValueError("duplicate shadow prediction IDs are forbidden")
    settlement_ids = [record.shadow_prediction_id for record in settlements]
    if len(settlement_ids) != len(set(settlement_ids)):
        raise ValueError("duplicate settlements are forbidden")

    grouped: dict[str, list[ShadowSettlementRecord]] = {}
    for settlement in settlements:
        prediction = by_prediction_id.get(settlement.shadow_prediction_id)
        if prediction is None:
            raise ValueError("settlement references an unknown shadow prediction")
        if settlement.shadow_prediction_sha256 != prediction.semantic_sha256:
            raise ValueError("settlement shadow prediction hash mismatch")
        if settlement.snapshot_sha256 != prediction.snapshot_sha256:
            raise ValueError("settlement snapshot hash mismatch")
        grouped.setdefault(prediction.output.challenger_id, []).append(settlement)

    rows = []
    for challenger_id, records in grouped.items():
        n = len(records)
        rows.append(
            ChallengerLeagueRow(
                challenger_id=challenger_id,
                n=n,
                accuracy=sum(item.correctness for item in records) / n,
                mean_brier=sum(item.brier for item in records) / n,
                mean_log_loss=sum(item.log_loss for item in records) / n,
            )
        )
    return tuple(sorted(rows, key=lambda row: row.challenger_id))


def build_failure_atlas_record(
    *,
    prediction: ShadowPredictionRecord,
    settlement: ShadowSettlementRecord,
    post_result_diagnostics: dict[str, Any] | None = None,
) -> FailureAtlasRecord:
    """Create a diagnostic row with a strict pre/post information boundary."""

    if settlement.shadow_prediction_sha256 != prediction.semantic_sha256:
        raise ValueError("settlement does not bind the supplied prediction")
    if settlement.snapshot_sha256 != prediction.snapshot_sha256:
        raise ValueError("settlement does not bind the supplied snapshot")
    if settlement.shadow_prediction_id != prediction.shadow_prediction_id:
        raise ValueError("settlement prediction ID mismatch")

    outcome_a = settlement.winner_player_id == prediction.player_a_id
    tags: set[str] = set()
    if settlement.correctness == 0:
        tags.add("WINNER_MISS")
    if (
        max(prediction.output.p_player_a, prediction.output.p_player_b) >= 0.65
        and settlement.correctness == 0
    ):
        tags.add("HIGH_CONFIDENCE_MISS")
    disagreement_values = tuple(prediction.output.component_probabilities.values())
    if (
        len(disagreement_values) >= 2
        and max(disagreement_values) - min(disagreement_values) >= 0.10
    ):
        tags.add("HIGH_COMPONENT_DISAGREEMENT")
    if bool(prediction.output.diagnostics.get("low_history", False)):
        tags.add("LOW_HISTORY")
    if bool(prediction.output.diagnostics.get("high_missingness", False)):
        tags.add("HIGH_MISSINGNESS")

    return FailureAtlasRecord(
        shadow_prediction_id=prediction.shadow_prediction_id,
        shadow_prediction_sha256=prediction.semantic_sha256,
        settlement_sha256=settlement.semantic_sha256,
        challenger_id=prediction.output.challenger_id,
        snapshot_sha256=prediction.snapshot_sha256,
        match_id=prediction.match_id,
        provider_event_id=prediction.provider_event_id,
        p_player_a=prediction.output.p_player_a,
        outcome_player_a_won=outcome_a,
        correctness=settlement.correctness,
        brier=settlement.brier,
        log_loss=settlement.log_loss,
        pre_match_component_probabilities=prediction.output.component_probabilities,
        pre_match_diagnostics=prediction.output.diagnostics,
        post_result_diagnostics=post_result_diagnostics or {},
        deterministic_tags=tuple(tags),
    )
