from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from pydantic import field_validator

from .challenger import (
    ChallengerRegistration,
    CommonPreMatchSnapshot,
    ShadowModelOutput,
    ShadowPredictionRecord,
    build_shadow_prediction,
    validate_shadow_prediction_set,
)
from .contracts import ForecastingProcedureSpec, WorkbenchRecord

_COMPONENT_VIEWS = (
    (
        "TGE-SHADOW-IDENTITY-V1",
        "Identity parity control",
        "champion_probability_a",
    ),
    (
        "TGE-SHADOW-GEOMETRY-V1",
        "Historical geometry component",
        "strict_core_geometry_historical_alignment_k100",
    ),
    (
        "TGE-SHADOW-POINTSIM-V1",
        "PointSim component",
        "pointsim_conditional_meta_input",
    ),
)


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _sha256_json(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _schema_shape(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): _schema_shape(item) for key, item in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        if not value:
            return ["empty"]
        shapes = {_canonical_json(_schema_shape(item)) for item in value}
        return [json.loads(shape) for shape in sorted(shapes)]
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    return "str"


class ComponentShadowBundle(WorkbenchRecord):
    schema_version: str = "tennis-genome-component-shadow-bundle-v1"
    snapshot: CommonPreMatchSnapshot
    registrations: tuple[ChallengerRegistration, ...]
    predictions: tuple[ShadowPredictionRecord, ...]

    @field_validator("registrations", "predictions")
    @classmethod
    def _nonempty(cls, value: tuple[Any, ...]) -> tuple[Any, ...]:
        if not value:
            raise ValueError("component shadow bundle collections must be nonempty")
        return value


def build_component_shadow_bundle(
    *,
    prediction_dossier: dict[str, Any],
    matchup_input: dict[str, Any],
    target_resolution: dict[str, Any],
    created_at: datetime,
    implementation_sha256: str,
    registered_at: datetime,
) -> ComponentShadowBundle:
    """Build market-blind component challengers from one frozen champion calculation."""

    calculation = prediction_dossier.get("calculation")
    if not isinstance(calculation, dict):
        raise ValueError("prediction dossier lacks calculation")
    prediction = calculation.get("prediction")
    if not isinstance(prediction, dict):
        raise ValueError("prediction dossier lacks champion prediction")
    components = prediction.get("component_probabilities")
    diagnostics = prediction.get("diagnostics")
    if not isinstance(components, dict) or not isinstance(diagnostics, dict):
        raise ValueError("champion component probabilities/diagnostics are unavailable")

    match_id = str(prediction["match_id"])
    event_id = str(target_resolution["event_id"])
    if match_id != event_id or str(matchup_input["match_id"]) != match_id:
        raise ValueError("champion dossier, matchup input, and provider target disagree")
    if str(matchup_input["player_a_id"]) != str(calculation["player_a_id"]):
        raise ValueError("player A orientation differs between champion inputs")
    if str(matchup_input["player_b_id"]) != str(calculation["player_b_id"]):
        raise ValueError("player B orientation differs between champion inputs")

    champion_probability_a = float(prediction["p_player_a"])
    champion_probability_b = float(prediction["p_player_b"])
    if abs(champion_probability_a + champion_probability_b - 1.0) > 1e-9:
        raise ValueError("champion probabilities do not sum to one")

    safe_payload = {
        "matchup_input": matchup_input,
        "champion_model_version": str(prediction["model_version"]),
        "champion_probability_a": champion_probability_a,
        "champion_probability_b": champion_probability_b,
        "component_probabilities": components,
        "champion_diagnostics": diagnostics,
        "production_bundle_sha256": str(calculation["production_bundle_sha256"]),
    }
    feature_payload_sha256 = _sha256_json(safe_payload)
    feature_schema_sha256 = _sha256_json(_schema_shape(safe_payload))
    prediction_cutoff_at = datetime.fromisoformat(str(prediction["prediction_cutoff_at"]))
    scheduled_start = datetime.fromisoformat(str(target_resolution["scheduled_start"]))
    source_manifest_hashes = tuple(str(v) for v in prediction["source_manifest_hashes"])

    snapshot = CommonPreMatchSnapshot(
        snapshot_id=f"COMMON-SNAPSHOT-V1-{prediction['prediction_id']}",
        match_id=match_id,
        provider_event_id=event_id,
        tour=str(prediction["tour"]),
        player_a_id=str(calculation["player_a_id"]),
        player_b_id=str(calculation["player_b_id"]),
        scheduled_start=scheduled_start,
        prediction_cutoff_at=prediction_cutoff_at,
        captured_at=created_at,
        source_manifest_hashes=source_manifest_hashes,
        feature_payload_sha256=feature_payload_sha256,
        feature_schema_sha256=feature_schema_sha256,
        feature_payload=safe_payload,
    )

    probabilities = {
        "champion_probability_a": champion_probability_a,
        "strict_core_geometry_historical_alignment_k100": float(
            components["strict_core_geometry_historical_alignment_k100"]
        ),
        "pointsim_conditional_meta_input": float(
            components["pointsim_conditional_meta_input"]
        ),
    }

    registrations: list[ChallengerRegistration] = []
    predictions: list[ShadowPredictionRecord] = []
    for challenger_id, name, source_key in _COMPONENT_VIEWS:
        procedure = ForecastingProcedureSpec(
            procedure_id=challenger_id,
            name=name,
            version="1",
            input_contract="common-pre-match-snapshot-v1",
            feature_set=(source_key,),
            training_method="frozen_component_view_no_refit",
            hyperparameters_json="{}",
            calibration="identity",
            prediction_method="copy_frozen_pre_match_probability",
            required_data=(source_key,),
            development_exposure_ids=(),
            parent_procedure_ids=("TGE-Independent-v1",),
            source_code_sha=implementation_sha256,
            runtime_id="python-3.11-pinned",
            random_seed=None,
        )
        registration = ChallengerRegistration(
            challenger_id=challenger_id,
            challenger_version="1.0.0",
            procedure=procedure,
            parent_champion_model_version="TGE-Independent-v1",
            feature_schema_sha256=feature_schema_sha256,
            code_sha256=implementation_sha256,
            training_population_sha256=str(calculation["production_bundle_sha256"]),
            training_window="inherits-frozen-TGE-Independent-v1-2000-2025",
            eligibility_contract=(
                "WTA shadow only; same common pre-match snapshot and orientation as champion"
            ),
            promotion_contract=(
                "diagnostic shadow only; cannot promote without separately preregistered gate"
            ),
            registered_at=registered_at,
        )
        probability_a = probabilities[source_key]
        output = ShadowModelOutput(
            challenger_id=challenger_id,
            p_player_a=probability_a,
            p_player_b=1.0 - probability_a,
            component_probabilities={"source_probability_a": probability_a},
            diagnostics={
                "champion_model_disagreement": diagnostics.get("model_disagreement"),
                "champion_alignment_missing_fraction": diagnostics.get(
                    "alignment_missing_fraction"
                ),
                "champion_points_history": diagnostics.get(
                    "pointsim_min_prior_point_history"
                ),
            },
        )
        shadow_prediction = build_shadow_prediction(
            registration=registration,
            snapshot=snapshot,
            output=output,
            shadow_prediction_id=f"{challenger_id}-{prediction['prediction_id']}",
            created_at=created_at,
        )
        registrations.append(registration)
        predictions.append(shadow_prediction)

    prediction_tuple = tuple(predictions)
    validate_shadow_prediction_set(prediction_tuple)
    return ComponentShadowBundle(
        snapshot=snapshot,
        registrations=tuple(registrations),
        predictions=prediction_tuple,
    )


def canonical_record_json(record: WorkbenchRecord) -> str:
    """Canonical bytes used by semantic SHA-256 and trusted anchor transport."""

    return _canonical_json(record.canonical_payload())
