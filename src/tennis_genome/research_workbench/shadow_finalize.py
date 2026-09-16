from __future__ import annotations

import math
import re
from datetime import datetime
from typing import Any, Self

from pydantic import field_validator, model_validator

from .challenger import (
    ChallengerLeagueRow,
    CommonPreMatchSnapshot,
    FailureAtlasRecord,
    ShadowPredictionRecord,
    ShadowSettlementRecord,
    build_league_table,
    settle_shadow_prediction,
    validate_shadow_prediction_set,
)
from .contracts import WorkbenchRecord

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class VerifiedSettlementBinding(WorkbenchRecord):
    """Minimal trusted champion-settlement facts admitted to the shadow lane."""

    verified_settlement_artifact_id: int
    verified_settlement_dossier_sha256: str
    prediction_artifact_id: int
    prediction_record_sha256: str
    match_id: str
    player_a_id: str
    player_b_id: str
    winner_player_id: str
    actual_start: datetime
    provider_status: str
    finish_status: str
    timing_status: str
    anchor_status: str
    primary_evaluation_eligible: bool
    period_scores: tuple[dict[str, Any], ...] = ()

    @field_validator("verified_settlement_artifact_id", "prediction_artifact_id")
    @classmethod
    def _positive_ids(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("artifact IDs must be positive")
        return value

    @field_validator("verified_settlement_dossier_sha256", "prediction_record_sha256")
    @classmethod
    def _sha256(cls, value: str) -> str:
        if _SHA256_RE.fullmatch(value) is None:
            raise ValueError("settlement binding hashes must be lowercase SHA-256")
        return value

    @field_validator("actual_start")
    @classmethod
    def _aware_start(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("actual_start must be timezone-aware")
        return value

    @model_validator(mode="after")
    def _trusted_terminal_state(self) -> Self:
        if not self.primary_evaluation_eligible:
            raise ValueError("champion settlement is not primary-evaluation eligible")
        if self.provider_status != "closed":
            raise ValueError("champion provider settlement must be closed")
        if self.finish_status != "COMPLETED":
            raise ValueError("champion finish status must be COMPLETED")
        if self.timing_status != "PRE_START_VERIFIED":
            raise ValueError("champion timing status must be PRE_START_VERIFIED")
        if self.anchor_status != "PRE_START_ANCHORED":
            raise ValueError("champion anchor status must be PRE_START_ANCHORED")
        if self.player_a_id == self.player_b_id:
            raise ValueError("champion player identities must differ")
        if self.winner_player_id not in (self.player_a_id, self.player_b_id):
            raise ValueError("champion winner does not match player orientation")
        return self


class ShadowFinalizationBundle(WorkbenchRecord):
    schema_version: str = "tennis-genome-shadow-finalization-bundle-v1"
    source_shadow_artifact_id: int
    snapshot_sha256: str
    settlement_binding: VerifiedSettlementBinding
    settlements: tuple[ShadowSettlementRecord, ...]
    failure_atlas: tuple[FailureAtlasRecord, ...]
    league_table: tuple[ChallengerLeagueRow, ...]

    @field_validator("source_shadow_artifact_id")
    @classmethod
    def _positive_shadow_id(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("source_shadow_artifact_id must be positive")
        return value

    @field_validator("snapshot_sha256")
    @classmethod
    def _snapshot_sha(cls, value: str) -> str:
        if _SHA256_RE.fullmatch(value) is None:
            raise ValueError("snapshot_sha256 must be lowercase SHA-256")
        return value

    @model_validator(mode="after")
    def _parallel_lengths(self) -> Self:
        if not self.settlements:
            raise ValueError("shadow finalization requires at least one settlement")
        if len(self.settlements) != len(self.failure_atlas):
            raise ValueError("every shadow settlement requires one Failure Atlas row")
        if len(self.league_table) != len(self.settlements):
            raise ValueError("one-match finalization expects one league row per challenger")
        return self


def binding_from_verified_dossier(
    *,
    dossier: dict[str, Any],
    verified_settlement_artifact_id: int,
    verified_settlement_dossier_sha256: str,
) -> VerifiedSettlementBinding:
    if dossier.get("schema_version") != "full-stack-forward-verified-settlement-dossier-v1":
        raise ValueError("unexpected verified champion settlement dossier schema")
    period_scores = dossier.get("period_scores", [])
    if not isinstance(period_scores, list):
        raise ValueError("period_scores must be a list")
    return VerifiedSettlementBinding(
        verified_settlement_artifact_id=verified_settlement_artifact_id,
        verified_settlement_dossier_sha256=verified_settlement_dossier_sha256,
        prediction_artifact_id=int(dossier["prediction_artifact_id"]),
        prediction_record_sha256=str(dossier["prediction_record_sha256"]),
        match_id=str(dossier["match_id"]),
        player_a_id=str(dossier["player_a_id"]),
        player_b_id=str(dossier["player_b_id"]),
        winner_player_id=str(dossier["winner_player_id"]),
        actual_start=datetime.fromisoformat(str(dossier["actual_start"])),
        provider_status=str(dossier["provider_status"]),
        finish_status=str(dossier["finish_status"]),
        timing_status=str(dossier["timing_status"]),
        anchor_status=str(dossier["anchor_status"]),
        primary_evaluation_eligible=bool(dossier["primary_evaluation_eligible"]),
        period_scores=tuple(dict(item) for item in period_scores),
    )


def _atlas_record(
    *,
    prediction: ShadowPredictionRecord,
    settlement: ShadowSettlementRecord,
    snapshot: CommonPreMatchSnapshot,
    binding: VerifiedSettlementBinding,
) -> FailureAtlasRecord:
    if prediction.snapshot_sha256 != snapshot.semantic_sha256:
        raise ValueError("shadow prediction does not bind the supplied common snapshot")
    components = snapshot.feature_payload.get("component_probabilities", {})
    diagnostics = snapshot.feature_payload.get("champion_diagnostics", {})
    if not isinstance(components, dict) or not isinstance(diagnostics, dict):
        raise ValueError("common snapshot lacks champion components/diagnostics")
    numeric_components: dict[str, float] = {}
    for key, value in components.items():
        probability = float(value)
        if not math.isfinite(probability) or not 0.0 <= probability <= 1.0:
            raise ValueError("snapshot component probabilities must be finite in [0, 1]")
        numeric_components[str(key)] = probability
    safe_diagnostics: dict[str, float | int | bool | None] = {}
    for key, value in diagnostics.items():
        if value is None or isinstance(value, (float, int, bool)):
            safe_diagnostics[str(key)] = value

    tags: set[str] = set()
    if settlement.correctness == 0:
        tags.add("WINNER_MISS")
    if (
        max(prediction.output.p_player_a, prediction.output.p_player_b) >= 0.65
        and settlement.correctness == 0
    ):
        tags.add("HIGH_CONFIDENCE_MISS")
    if numeric_components:
        disagreement = max(numeric_components.values()) - min(numeric_components.values())
        if disagreement >= 0.10:
            tags.add("HIGH_COMPONENT_DISAGREEMENT")
    model_disagreement = safe_diagnostics.get("model_disagreement")
    if isinstance(model_disagreement, (int, float)) and float(model_disagreement) >= 0.10:
        tags.add("HIGH_MODEL_DISAGREEMENT")
    missing_fraction = safe_diagnostics.get("alignment_missing_fraction")
    if isinstance(missing_fraction, (int, float)) and float(missing_fraction) >= 0.25:
        tags.add("HIGH_MISSINGNESS")
    point_history = safe_diagnostics.get("pointsim_min_prior_point_history")
    if isinstance(point_history, (int, float)) and float(point_history) < 500:
        tags.add("LOW_POINT_HISTORY")

    outcome_a = binding.winner_player_id == prediction.player_a_id
    return FailureAtlasRecord(
        shadow_prediction_id=prediction.shadow_prediction_id,
        shadow_prediction_sha256=prediction.semantic_sha256,
        settlement_sha256=settlement.semantic_sha256,
        challenger_id=prediction.output.challenger_id,
        snapshot_sha256=snapshot.semantic_sha256,
        match_id=prediction.match_id,
        provider_event_id=prediction.provider_event_id,
        p_player_a=prediction.output.p_player_a,
        outcome_player_a_won=outcome_a,
        correctness=settlement.correctness,
        brier=settlement.brier,
        log_loss=settlement.log_loss,
        pre_match_component_probabilities=numeric_components,
        pre_match_diagnostics=safe_diagnostics,
        post_result_diagnostics={
            "actual_start": binding.actual_start.isoformat(),
            "finish_status": binding.finish_status,
            "period_scores": list(binding.period_scores),
            "winner_player_id": binding.winner_player_id,
        },
        deterministic_tags=tuple(tags),
    )


def finalize_shadow_match(
    *,
    predictions: tuple[ShadowPredictionRecord, ...],
    snapshot: CommonPreMatchSnapshot,
    binding: VerifiedSettlementBinding,
    source_shadow_artifact_id: int,
    settled_at: datetime,
) -> ShadowFinalizationBundle:
    if settled_at.tzinfo is None or settled_at.utcoffset() is None:
        raise ValueError("settled_at must be timezone-aware")
    validate_shadow_prediction_set(predictions)
    if not predictions:
        raise ValueError("at least one shadow prediction is required")
    if snapshot.semantic_sha256 != predictions[0].snapshot_sha256:
        raise ValueError("common snapshot hash differs from shadow prediction set")
    if binding.match_id != snapshot.match_id or binding.match_id != snapshot.provider_event_id:
        raise ValueError("verified champion settlement match identity differs from shadow snapshot")
    if binding.player_a_id != snapshot.player_a_id or binding.player_b_id != snapshot.player_b_id:
        raise ValueError("verified champion settlement orientation differs from shadow snapshot")

    identity = [p for p in predictions if p.output.challenger_id == "TGE-SHADOW-IDENTITY-V1"]
    if len(identity) != 1:
        raise ValueError("exactly one identity shadow control is required")

    settlements = tuple(
        settle_shadow_prediction(
            prediction=prediction,
            winner_player_id=binding.winner_player_id,
            settled_at=settled_at,
            settlement_evidence_sha256=binding.verified_settlement_dossier_sha256,
        )
        for prediction in predictions
    )
    atlas = tuple(
        _atlas_record(
            prediction=prediction,
            settlement=settlement,
            snapshot=snapshot,
            binding=binding,
        )
        for prediction, settlement in zip(predictions, settlements, strict=True)
    )
    league = build_league_table(predictions=predictions, settlements=settlements)
    return ShadowFinalizationBundle(
        source_shadow_artifact_id=source_shadow_artifact_id,
        snapshot_sha256=snapshot.semantic_sha256,
        settlement_binding=binding,
        settlements=settlements,
        failure_atlas=atlas,
        league_table=league,
    )
