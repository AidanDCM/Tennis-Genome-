from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from typing import Literal, Self

from pydantic import field_validator, model_validator

from .api_tennis_conservative_wta_shadow import (
    CHALLENGER_ID,
    build_conservative_wta_shadow_output,
)
from .api_tennis_dynamic_shadow import ApiTennisDynamicShadowRecord
from .challenger import (
    ChallengerRegistration,
    CommonPreMatchSnapshot,
    ShadowModelOutput,
    ShadowPredictionRecord,
)
from .contracts import ForecastingProcedureSpec, WorkbenchRecord

STATE_SCHEMA_VERSION = "tennis-genome-api-tennis-prospective-state-v1"
CROSSWALK_SCHEMA_VERSION = "tennis-genome-api-tennis-champion-crosswalk-v1"
BUNDLE_SCHEMA_VERSION = "tennis-genome-api-tennis-prospective-shadow-bundle-v1"

DEVELOPMENT_POPULATION_SHA256 = (
    "afb24b2547503049e8f155cba86e60144c99657b85eb206f32c4b7a31f598d3c"
)
DEVELOPMENT_EXPOSURE_ID = "API-TENNIS-FILTERED-SHADOW-REPLAY-001"


def _canonical_sha256(value: object) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _require_sha256(value: str, *, field_name: str) -> str:
    if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise ValueError(f"{field_name} must be lowercase SHA-256")
    return value


def _require_aware(value: datetime, *, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value


class ApiTennisProspectiveStateEvidence(WorkbenchRecord):
    """Outcome-free API-Tennis dynamic state frozen before one target match."""

    schema_version: Literal[
        "tennis-genome-api-tennis-prospective-state-v1"
    ] = STATE_SCHEMA_VERSION
    source_artifact_id: int
    state_source_sha256: str
    target_fixture_sha256: str
    captured_at: datetime
    history_through_date: date
    event_key: int
    event_date: date
    tour: Literal["WTA"]
    player_a_key: int
    player_b_key: int
    player_a_name: str
    player_b_name: str
    probability_a_serve_point: float
    probability_b_serve_point: float
    probability_a_match: float
    prior_serve_points_a: int
    prior_serve_points_b: int
    prior_return_points_a: int
    prior_return_points_b: int
    historical_actual_start_admissible: Literal[False] = False

    @field_validator("source_artifact_id", "event_key", "player_a_key", "player_b_key")
    @classmethod
    def _positive_ids(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("provider and artifact IDs must be positive")
        return value

    @field_validator("state_source_sha256", "target_fixture_sha256")
    @classmethod
    def _hashes(cls, value: str, info: object) -> str:
        field_name = getattr(info, "field_name", "sha256")
        return _require_sha256(value, field_name=field_name)

    @field_validator("captured_at")
    @classmethod
    def _captured_at(cls, value: datetime) -> datetime:
        return _require_aware(value, field_name="captured_at")

    @field_validator(
        "probability_a_serve_point",
        "probability_b_serve_point",
        "probability_a_match",
    )
    @classmethod
    def _probability(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            raise ValueError("probabilities must be in [0, 1]")
        return float(value)

    @field_validator(
        "prior_serve_points_a",
        "prior_serve_points_b",
        "prior_return_points_a",
        "prior_return_points_b",
    )
    @classmethod
    def _history_counts(cls, value: int) -> int:
        if value < 0:
            raise ValueError("prior point counts must be non-negative")
        return value

    @field_validator("player_a_name", "player_b_name")
    @classmethod
    def _names(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("player names must be nonblank")
        return value

    @model_validator(mode="after")
    def _chronology_and_identity(self) -> Self:
        if self.player_a_key == self.player_b_key:
            raise ValueError("API-Tennis player keys must differ")
        if self.history_through_date >= self.event_date:
            raise ValueError("prospective state may use only strictly prior-date history")
        return self


class ApiTennisChampionCrosswalk(WorkbenchRecord):
    """Explicit pre-match identity bridge between Champion and API-Tennis."""

    schema_version: Literal[
        "tennis-genome-api-tennis-champion-crosswalk-v1"
    ] = CROSSWALK_SCHEMA_VERSION
    champion_match_id: str
    champion_provider_event_id: str
    champion_player_a_id: str
    champion_player_b_id: str
    api_tennis_event_key: int
    api_tennis_player_a_key: int
    api_tennis_player_b_key: int
    orientation: Literal["DIRECT", "REVERSED"]
    mapping_basis: Literal[
        "EXPLICIT_PROVIDER_ID",
        "DOCUMENTED_MANUAL_PREMATCH",
        "EXACT_NORMALIZED_NAME_PREMATCH",
    ]
    mapping_evidence_sha256: str
    created_at: datetime

    @field_validator(
        "champion_match_id",
        "champion_provider_event_id",
        "champion_player_a_id",
        "champion_player_b_id",
    )
    @classmethod
    def _nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("crosswalk identity fields must be nonblank")
        return value

    @field_validator(
        "api_tennis_event_key",
        "api_tennis_player_a_key",
        "api_tennis_player_b_key",
    )
    @classmethod
    def _positive_provider_ids(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("API-Tennis crosswalk IDs must be positive")
        return value

    @field_validator("mapping_evidence_sha256")
    @classmethod
    def _mapping_hash(cls, value: str) -> str:
        return _require_sha256(value, field_name="mapping_evidence_sha256")

    @field_validator("created_at")
    @classmethod
    def _created_at(cls, value: datetime) -> datetime:
        return _require_aware(value, field_name="created_at")

    @model_validator(mode="after")
    def _distinct_players(self) -> Self:
        if self.champion_player_a_id == self.champion_player_b_id:
            raise ValueError("Champion player IDs must differ")
        if self.api_tennis_player_a_key == self.api_tennis_player_b_key:
            raise ValueError("API-Tennis player keys must differ")
        return self


class ApiTennisProspectiveShadowBundle(WorkbenchRecord):
    schema_version: Literal[
        "tennis-genome-api-tennis-prospective-shadow-bundle-v1"
    ] = BUNDLE_SCHEMA_VERSION
    snapshot_sha256: str
    evidence: ApiTennisProspectiveStateEvidence
    crosswalk: ApiTennisChampionCrosswalk
    registration: ChallengerRegistration
    prediction: ShadowPredictionRecord | None

    @field_validator("snapshot_sha256")
    @classmethod
    def _snapshot_hash(cls, value: str) -> str:
        return _require_sha256(value, field_name="snapshot_sha256")

    @model_validator(mode="after")
    def _bind_challenger(self) -> Self:
        if self.registration.challenger_id != CHALLENGER_ID:
            raise ValueError("prospective bundle registration has wrong challenger ID")
        if self.prediction is not None and self.prediction.output.challenger_id != CHALLENGER_ID:
            raise ValueError("prospective bundle prediction has wrong challenger ID")
        return self


def _feature_schema_sha256(snapshot: CommonPreMatchSnapshot) -> str:
    return _canonical_sha256(
        {
            "common_snapshot_feature_schema_sha256": snapshot.feature_schema_sha256,
            "supplemental_state_schema_version": STATE_SCHEMA_VERSION,
            "crosswalk_schema_version": CROSSWALK_SCHEMA_VERSION,
            "orientation_policy": "explicit_direct_or_reversed",
            "eligibility": {
                "tour": "WTA",
                "min_combined_prior_points_per_player": 200,
                "shrinkage_to_neutral": 0.80,
            },
        }
    )


def _validate_binding(
    *,
    snapshot: CommonPreMatchSnapshot,
    evidence: ApiTennisProspectiveStateEvidence,
    crosswalk: ApiTennisChampionCrosswalk,
    created_at: datetime,
    registered_at: datetime,
) -> None:
    _require_aware(created_at, field_name="created_at")
    _require_aware(registered_at, field_name="registered_at")
    if snapshot.tour != "WTA" or evidence.tour != "WTA":
        raise ValueError("conservative API-Tennis prospective shadow is WTA-only")
    if crosswalk.champion_match_id != snapshot.match_id:
        raise ValueError("crosswalk Champion match ID mismatch")
    if crosswalk.champion_provider_event_id != snapshot.provider_event_id:
        raise ValueError("crosswalk Champion provider event mismatch")
    if crosswalk.champion_player_a_id != snapshot.player_a_id:
        raise ValueError("crosswalk Champion player A mismatch")
    if crosswalk.champion_player_b_id != snapshot.player_b_id:
        raise ValueError("crosswalk Champion player B mismatch")
    if crosswalk.api_tennis_event_key != evidence.event_key:
        raise ValueError("crosswalk API-Tennis event mismatch")
    if crosswalk.api_tennis_player_a_key != evidence.player_a_key:
        raise ValueError("crosswalk API-Tennis player A mismatch")
    if crosswalk.api_tennis_player_b_key != evidence.player_b_key:
        raise ValueError("crosswalk API-Tennis player B mismatch")
    if evidence.captured_at >= snapshot.scheduled_start:
        raise ValueError("API-Tennis state evidence must be captured before scheduled start")
    if crosswalk.created_at >= snapshot.scheduled_start:
        raise ValueError("API-Tennis crosswalk must be frozen before scheduled start")
    if created_at >= snapshot.scheduled_start:
        raise ValueError("prospective shadow prediction must be created before scheduled start")
    if created_at < snapshot.captured_at:
        raise ValueError("prospective shadow cannot predate the common snapshot")
    if created_at < evidence.captured_at:
        raise ValueError("prospective shadow cannot predate API-Tennis state evidence")
    if created_at < crosswalk.created_at:
        raise ValueError("prospective shadow cannot predate the crosswalk")
    if registered_at > created_at:
        raise ValueError("challenger registration cannot postdate its prediction")


def _oriented_dynamic_record(
    *,
    evidence: ApiTennisProspectiveStateEvidence,
    crosswalk: ApiTennisChampionCrosswalk,
) -> ApiTennisDynamicShadowRecord:
    if crosswalk.orientation == "DIRECT":
        return ApiTennisDynamicShadowRecord(
            match_id=f"api-tennis:{evidence.event_key}",
            event_key=evidence.event_key,
            event_date=evidence.event_date.isoformat(),
            tour="WTA",
            player_a_key=evidence.player_a_key,
            player_b_key=evidence.player_b_key,
            player_a_name=evidence.player_a_name,
            player_b_name=evidence.player_b_name,
            probability_a_serve_point=evidence.probability_a_serve_point,
            probability_b_serve_point=evidence.probability_b_serve_point,
            probability_a_match=evidence.probability_a_match,
            prior_serve_points_a=evidence.prior_serve_points_a,
            prior_serve_points_b=evidence.prior_serve_points_b,
            prior_return_points_a=evidence.prior_return_points_a,
            prior_return_points_b=evidence.prior_return_points_b,
            source_raw_match_sha256=evidence.target_fixture_sha256,
        )

    return ApiTennisDynamicShadowRecord(
        match_id=f"api-tennis:{evidence.event_key}",
        event_key=evidence.event_key,
        event_date=evidence.event_date.isoformat(),
        tour="WTA",
        player_a_key=evidence.player_b_key,
        player_b_key=evidence.player_a_key,
        player_a_name=evidence.player_b_name,
        player_b_name=evidence.player_a_name,
        probability_a_serve_point=evidence.probability_b_serve_point,
        probability_b_serve_point=evidence.probability_a_serve_point,
        probability_a_match=1.0 - evidence.probability_a_match,
        prior_serve_points_a=evidence.prior_serve_points_b,
        prior_serve_points_b=evidence.prior_serve_points_a,
        prior_return_points_a=evidence.prior_return_points_b,
        prior_return_points_b=evidence.prior_return_points_a,
        source_raw_match_sha256=evidence.target_fixture_sha256,
    )


def _registration(
    *,
    snapshot: CommonPreMatchSnapshot,
    implementation_sha256: str,
    registered_at: datetime,
) -> ChallengerRegistration:
    _require_sha256(implementation_sha256, field_name="implementation_sha256")
    procedure = ForecastingProcedureSpec(
        procedure_id=CHALLENGER_ID,
        name="Conservative WTA dynamic serve-return shadow",
        version="1",
        input_contract=(
            "common-pre-match-snapshot-v1+"
            "api-tennis-prospective-state-v1+explicit-crosswalk-v1"
        ),
        feature_set=(
            "api_tennis_dynamic_match_probability",
            "api_tennis_prior_serve_points",
            "api_tennis_prior_return_points",
            "explicit_provider_crosswalk",
        ),
        training_method="frozen_development_rule_no_refit",
        hyperparameters_json=json.dumps(
            {
                "min_combined_prior_points_per_player": 200,
                "shrinkage_to_neutral": 0.80,
                "tour": "WTA",
            }
        ),
        calibration="linear_shrinkage_80_percent_to_neutral",
        prediction_method="history_gate_then_shrink_dynamic_match_probability",
        required_data=(
            "strictly_prior_date_api_tennis_state",
            "pre_match_target_fixture_identity",
            "explicit_champion_api_tennis_crosswalk",
        ),
        development_exposure_ids=(DEVELOPMENT_EXPOSURE_ID,),
        parent_procedure_ids=("TGE-SHADOW-API-TENNIS-DYNAMIC-SR-V1",),
        source_code_sha=implementation_sha256,
        runtime_id="python-3.11-pinned",
        random_seed=None,
    )
    return ChallengerRegistration(
        challenger_id=CHALLENGER_ID,
        challenger_version="1.0.0",
        procedure=procedure,
        parent_champion_model_version="TGE-Independent-v1",
        feature_schema_sha256=_feature_schema_sha256(snapshot),
        code_sha256=implementation_sha256,
        training_population_sha256=DEVELOPMENT_POPULATION_SHA256,
        training_window="API-Tennis filtered 2026-08-17 through 2026-09-16 development replay",
        eligibility_contract=(
            "WTA only; explicit crosswalk; both players >=200 combined strictly-prior "
            "serve+return points; otherwise abstain"
        ),
        promotion_contract=(
            "shadow only; prospective Brier/log-loss evaluation required; no retuning "
            "prospective outcomes into confirmatory evidence"
        ),
        registered_at=registered_at,
    )


def build_api_tennis_prospective_shadow_bundle(
    *,
    snapshot: CommonPreMatchSnapshot,
    evidence: ApiTennisProspectiveStateEvidence,
    crosswalk: ApiTennisChampionCrosswalk,
    created_at: datetime,
    implementation_sha256: str,
    registered_at: datetime,
) -> ApiTennisProspectiveShadowBundle:
    """Bind frozen supplemental API-Tennis state to the existing common shadow snapshot."""

    _validate_binding(
        snapshot=snapshot,
        evidence=evidence,
        crosswalk=crosswalk,
        created_at=created_at,
        registered_at=registered_at,
    )
    registration = _registration(
        snapshot=snapshot,
        implementation_sha256=implementation_sha256,
        registered_at=registered_at,
    )
    oriented = _oriented_dynamic_record(evidence=evidence, crosswalk=crosswalk)
    base_output = build_conservative_wta_shadow_output(oriented)
    if base_output is None:
        prediction = None
    else:
        output = ShadowModelOutput(
            challenger_id=base_output.challenger_id,
            p_player_a=base_output.p_player_a,
            p_player_b=base_output.p_player_b,
            component_probabilities=base_output.component_probabilities,
            diagnostics={
                **base_output.diagnostics,
                "supplemental_evidence_bound": True,
                "orientation_reversed": crosswalk.orientation == "REVERSED",
            },
        )
        cutoff = max(
            snapshot.prediction_cutoff_at,
            evidence.captured_at,
            crosswalk.created_at,
        )
        source_hashes = tuple(
            dict.fromkeys(
                (
                    *snapshot.source_manifest_hashes,
                    evidence.state_source_sha256,
                    evidence.target_fixture_sha256,
                    evidence.semantic_sha256,
                    crosswalk.semantic_sha256,
                )
            )
        )
        prediction = ShadowPredictionRecord(
            shadow_prediction_id=f"{CHALLENGER_ID}-{snapshot.snapshot_id}",
            registration_sha256=registration.semantic_sha256,
            snapshot_sha256=snapshot.semantic_sha256,
            snapshot_id=snapshot.snapshot_id,
            match_id=snapshot.match_id,
            provider_event_id=snapshot.provider_event_id,
            tour=snapshot.tour,
            player_a_id=snapshot.player_a_id,
            player_b_id=snapshot.player_b_id,
            prediction_cutoff_at=cutoff,
            scheduled_start=snapshot.scheduled_start,
            created_at=created_at,
            output=output,
            source_manifest_hashes=source_hashes,
        )

    return ApiTennisProspectiveShadowBundle(
        snapshot_sha256=snapshot.semantic_sha256,
        evidence=evidence,
        crosswalk=crosswalk,
        registration=registration,
        prediction=prediction,
    )
