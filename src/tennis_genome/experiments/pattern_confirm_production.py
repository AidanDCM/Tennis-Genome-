from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from scipy.special import expit

from tennis_genome.data.canonical import HistoricalMatch
from tennis_genome.data.manifest import verify_canonical_manifest
from tennis_genome.data.parquet import load_canonical_parquet
from tennis_genome.features.foundational import (
    FoundationalSnapshot,
    walk_forward_foundational_features,
)
from tennis_genome.models.core_v1_spec import strict_a_features
from tennis_genome.models.feature_probability import FeatureProbabilityModel
from tennis_genome.models.profile_strength import (
    ProfileStrengthModel,
    elo_strength_coordinate,
)
from tennis_genome.profiles.features import profile_strength_feature_values
from tennis_genome.profiles.state import MatchProfilePair, walk_forward_player_profiles
from tennis_genome.ratings.elo import EloConfig

_PROFILE_EXPERIMENT_ID = "PROFILE-PRODUCTION-001"
_CORE_EXPERIMENT_ID = "CORE-PRODUCTION-001"
_VERSION = "pattern-confirm-production-v1"
_TRAINING_END_YEAR = 2025
_STATE_SEMANTICS = "strictly-earlier-date-state-v1"


@dataclass(frozen=True)
class ProfileProductionArtifact:
    experiment_id: str
    version: str
    tour: str
    representation: str
    training_end_year: int
    training_n: int
    training_rows_sha256: str
    canonical_manifest_sha256: str
    state_semantics: str
    feature_names: tuple[str, ...]
    imputer_statistics: tuple[float, ...]
    scaler_mean: tuple[float, ...]
    scaler_scale: tuple[float, ...]
    logistic_coefficients: tuple[float, ...]
    elo_initial_rating: float
    elo_k_factor: float
    elo_scale: float
    artifact_sha256: str


@dataclass(frozen=True)
class CoreProductionArtifact:
    experiment_id: str
    version: str
    tour: str
    representation: str
    training_end_year: int
    training_n: int
    training_rows_sha256: str
    canonical_manifest_sha256: str
    state_semantics: str
    feature_names: tuple[str, ...]
    imputer_statistics: tuple[float, ...]
    imputer_indicator_features: tuple[int, ...]
    scaler_mean: tuple[float, ...]
    scaler_scale: tuple[float, ...]
    logistic_coefficients: tuple[float, ...]
    logistic_intercept: float
    artifact_sha256: str


def _canonical_json(payload: object) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _self_hash(payload: dict[str, object]) -> str:
    unsigned = dict(payload)
    unsigned.pop("artifact_sha256", None)
    return _sha256_bytes(_canonical_json(unsigned))


def _eligible(matches: list[HistoricalMatch]) -> list[HistoricalMatch]:
    atp = [match for match in matches if match.pre_match.tour == "ATP"]
    if any(match.pre_match.event_date.year > _TRAINING_END_YEAR for match in atp):
        raise ValueError("production freeze forbids post-2025 ATP training rows")
    return [match for match in atp if not match.outcome.walkover and not match.outcome.retirement]


def _training_row_hash(matches: list[HistoricalMatch]) -> str:
    rows = [
        {
            "match_id": match.match_id,
            "event_date": match.pre_match.event_date.isoformat(),
            "outcome_a": match.outcome.a_won,
        }
        for match in matches
    ]
    rows.sort(key=lambda row: (str(row["event_date"]), str(row["match_id"])))
    return _sha256_bytes(_canonical_json(rows))


def _aligned_training_state(
    matches: list[HistoricalMatch],
) -> tuple[list[MatchProfilePair], dict[str, FoundationalSnapshot], list[bool]]:
    pairs = walk_forward_player_profiles(matches, exclude_retirements=False)
    foundational = {
        snapshot.match_id: snapshot
        for snapshot in walk_forward_foundational_features(
            matches,
            exclude_retirements=False,
        )
    }
    outcomes = {match.match_id: match.outcome.a_won for match in matches}
    pairs = [pair for pair in pairs if pair.match_id in foundational]
    if len(pairs) != len(matches):
        raise ValueError("production state builders did not cover every eligible match")
    return pairs, foundational, [outcomes[pair.match_id] for pair in pairs]


def freeze_production_artifacts(
    matches: list[HistoricalMatch],
    *,
    canonical_manifest_sha256: str,
) -> tuple[ProfileProductionArtifact, CoreProductionArtifact]:
    eligible = _eligible(matches)
    if not eligible:
        raise ValueError("production training population is empty")
    pairs, foundational, outcomes = _aligned_training_state(eligible)
    training_rows_sha = _training_row_hash(eligible)

    profile_model = ProfileStrengthModel("ATP", include_conditional=False).fit(
        pairs,
        outcomes,
    )
    if (
        profile_model._imputer is None
        or profile_model._scaler is None
        or profile_model._model is None
    ):
        raise RuntimeError("Profile production model did not fit")
    profile_unsigned: dict[str, object] = {
        "experiment_id": _PROFILE_EXPERIMENT_ID,
        "version": _VERSION,
        "tour": "ATP",
        "representation": "strict",
        "training_end_year": _TRAINING_END_YEAR,
        "training_n": len(pairs),
        "training_rows_sha256": training_rows_sha,
        "canonical_manifest_sha256": canonical_manifest_sha256,
        "state_semantics": _STATE_SEMANTICS,
        "feature_names": list(profile_model.feature_names),
        "imputer_statistics": profile_model._imputer.statistics_.astype(float).tolist(),
        "scaler_mean": profile_model._scaler.mean_.astype(float).tolist(),
        "scaler_scale": profile_model._scaler.scale_.astype(float).tolist(),
        "logistic_coefficients": profile_model._model.coef_[0].astype(float).tolist(),
        "elo_initial_rating": profile_model.elo_config.initial_rating,
        "elo_k_factor": profile_model.elo_config.k_factor,
        "elo_scale": profile_model.elo_config.scale,
    }
    profile_digest = _self_hash(profile_unsigned)
    profile_artifact = ProfileProductionArtifact(
        **{
            **profile_unsigned,
            "feature_names": tuple(profile_unsigned["feature_names"]),
            "imputer_statistics": tuple(profile_unsigned["imputer_statistics"]),
            "scaler_mean": tuple(profile_unsigned["scaler_mean"]),
            "scaler_scale": tuple(profile_unsigned["scaler_scale"]),
            "logistic_coefficients": tuple(profile_unsigned["logistic_coefficients"]),
        },
        artifact_sha256=profile_digest,
    )

    core_feature_names = strict_a_features("ATP")
    core_model = FeatureProbabilityModel(core_feature_names).fit(
        [foundational[pair.match_id] for pair in pairs],
        outcomes,
    )
    if core_model._pipeline is None:
        raise RuntimeError("Core production model did not fit")
    imputer = core_model._pipeline.named_steps["simpleimputer"]
    scaler = core_model._pipeline.named_steps["standardscaler"]
    logistic = core_model._pipeline.named_steps["logisticregression"]
    indicator_features = (
        [] if imputer.indicator_ is None else imputer.indicator_.features_.astype(int).tolist()
    )
    core_unsigned: dict[str, object] = {
        "experiment_id": _CORE_EXPERIMENT_ID,
        "version": _VERSION,
        "tour": "ATP",
        "representation": "strict_a",
        "training_end_year": _TRAINING_END_YEAR,
        "training_n": len(pairs),
        "training_rows_sha256": training_rows_sha,
        "canonical_manifest_sha256": canonical_manifest_sha256,
        "state_semantics": _STATE_SEMANTICS,
        "feature_names": list(core_feature_names),
        "imputer_statistics": imputer.statistics_.astype(float).tolist(),
        "imputer_indicator_features": indicator_features,
        "scaler_mean": scaler.mean_.astype(float).tolist(),
        "scaler_scale": scaler.scale_.astype(float).tolist(),
        "logistic_coefficients": logistic.coef_[0].astype(float).tolist(),
        "logistic_intercept": float(logistic.intercept_[0]),
    }
    core_digest = _self_hash(core_unsigned)
    core_artifact = CoreProductionArtifact(
        **{
            **core_unsigned,
            "feature_names": tuple(core_unsigned["feature_names"]),
            "imputer_statistics": tuple(core_unsigned["imputer_statistics"]),
            "imputer_indicator_features": tuple(core_unsigned["imputer_indicator_features"]),
            "scaler_mean": tuple(core_unsigned["scaler_mean"]),
            "scaler_scale": tuple(core_unsigned["scaler_scale"]),
            "logistic_coefficients": tuple(core_unsigned["logistic_coefficients"]),
        },
        artifact_sha256=core_digest,
    )
    return profile_artifact, core_artifact


def verify_profile_artifact(payload: dict[str, object]) -> ProfileProductionArtifact:
    if payload.get("experiment_id") != _PROFILE_EXPERIMENT_ID:
        raise ValueError("unexpected Profile production experiment ID")
    stored = str(payload.get("artifact_sha256", ""))
    if not stored or _self_hash(payload) != stored:
        raise ValueError("Profile production artifact digest mismatch")
    normalized = dict(payload)
    for name in (
        "feature_names",
        "imputer_statistics",
        "scaler_mean",
        "scaler_scale",
        "logistic_coefficients",
    ):
        normalized[name] = tuple(payload.get(name, ()))
    artifact = ProfileProductionArtifact(**normalized)
    size = len(artifact.feature_names)
    if not all(
        len(values) == size
        for values in (
            artifact.imputer_statistics,
            artifact.scaler_mean,
            artifact.scaler_scale,
            artifact.logistic_coefficients,
        )
    ):
        raise ValueError("Profile production artifact dimensions do not agree")
    return artifact


def verify_core_artifact(payload: dict[str, object]) -> CoreProductionArtifact:
    if payload.get("experiment_id") != _CORE_EXPERIMENT_ID:
        raise ValueError("unexpected Core production experiment ID")
    stored = str(payload.get("artifact_sha256", ""))
    if not stored or _self_hash(payload) != stored:
        raise ValueError("Core production artifact digest mismatch")
    normalized = dict(payload)
    for name in (
        "feature_names",
        "imputer_statistics",
        "imputer_indicator_features",
        "scaler_mean",
        "scaler_scale",
        "logistic_coefficients",
    ):
        normalized[name] = tuple(payload.get(name, ()))
    artifact = CoreProductionArtifact(**normalized)
    raw_size = len(artifact.feature_names)
    expanded_size = raw_size + len(artifact.imputer_indicator_features)
    if len(artifact.imputer_statistics) != raw_size:
        raise ValueError("Core imputer dimension does not match feature schema")
    if not all(
        len(values) == expanded_size
        for values in (
            artifact.scaler_mean,
            artifact.scaler_scale,
            artifact.logistic_coefficients,
        )
    ):
        raise ValueError("Core production artifact dimensions do not agree")
    if any(index < 0 or index >= raw_size for index in artifact.imputer_indicator_features):
        raise ValueError("Core missing-indicator index is outside feature schema")
    return artifact


def _standardize(
    values: list[float],
    *,
    mean: tuple[float, ...],
    scale: tuple[float, ...],
) -> np.ndarray:
    vector = np.asarray(values, dtype=float)
    denominator = np.asarray(scale, dtype=float)
    if np.any(~np.isfinite(vector)) or np.any(~np.isfinite(denominator)):
        raise ValueError("production transform contains non-finite values")
    if np.any(denominator <= 0.0):
        raise ValueError("production scaler requires positive scales")
    return (vector - np.asarray(mean, dtype=float)) / denominator


def profile_gap_from_artifact(
    pair: MatchProfilePair,
    artifact: ProfileProductionArtifact,
) -> float:
    if pair.player_a.tour != "ATP" or pair.player_b.tour != "ATP":
        raise ValueError("Profile production artifact is ATP only")
    raw_a = profile_strength_feature_values(pair.player_a, include_conditional=False)
    raw_b = profile_strength_feature_values(pair.player_b, include_conditional=False)
    if len(raw_a) != len(artifact.feature_names) or len(raw_b) != len(artifact.feature_names):
        raise ValueError("Profile snapshot does not match frozen feature schema")

    def transform(raw: tuple[float | None, ...]) -> np.ndarray:
        values = [
            artifact.imputer_statistics[index] if value is None else float(value)
            for index, value in enumerate(raw)
        ]
        return _standardize(values, mean=artifact.scaler_mean, scale=artifact.scaler_scale)

    coefficient = np.asarray(artifact.logistic_coefficients, dtype=float)
    score_a = float(np.dot(coefficient, transform(raw_a)))
    score_b = float(np.dot(coefficient, transform(raw_b)))
    elo_config = EloConfig(
        initial_rating=artifact.elo_initial_rating,
        k_factor=artifact.elo_k_factor,
        scale=artifact.elo_scale,
    )
    elo_a = elo_strength_coordinate(pair.player_a.elo_rating, config=elo_config)
    elo_b = elo_strength_coordinate(pair.player_b.elo_rating, config=elo_config)
    return (score_a - elo_a) - (score_b - elo_b)


def core_probability_from_artifact(
    snapshot: FoundationalSnapshot,
    artifact: CoreProductionArtifact,
) -> float:
    raw: list[float | None] = []
    missing: list[bool] = []
    for name in artifact.feature_names:
        value = getattr(snapshot, name)
        is_missing = value is None or (isinstance(value, float) and math.isnan(value))
        missing.append(is_missing)
        raw.append(None if is_missing else float(value))
    imputed = [
        artifact.imputer_statistics[index] if value is None else value
        for index, value in enumerate(raw)
    ]
    expanded = [float(value) for value in imputed]
    expanded.extend(1.0 if missing[index] else 0.0 for index in artifact.imputer_indicator_features)
    standardized = _standardize(
        expanded,
        mean=artifact.scaler_mean,
        scale=artifact.scaler_scale,
    )
    linear = artifact.logistic_intercept + float(
        np.dot(np.asarray(artifact.logistic_coefficients, dtype=float), standardized)
    )
    return float(expit(linear))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Freeze PATTERN-CONFIRM-001 upstream mappings")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--pre-match", required=True, type=Path)
    parser.add_argument("--outcomes", required=True, type=Path)
    parser.add_argument("--stats", required=True, type=Path)
    parser.add_argument("--profile-output", required=True, type=Path)
    parser.add_argument("--core-output", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    verify_canonical_manifest(
        manifest_path=args.manifest,
        pre_match_path=args.pre_match,
        outcome_path=args.outcomes,
        stats_path=args.stats,
    )
    matches = load_canonical_parquet(
        pre_match_path=args.pre_match,
        outcome_path=args.outcomes,
        stats_path=args.stats,
    )
    profile, core = freeze_production_artifacts(
        matches,
        canonical_manifest_sha256=_sha256_file(args.manifest),
    )
    args.profile_output.write_text(
        json.dumps(asdict(profile), indent=2, sort_keys=True, allow_nan=False) + "\n"
    )
    args.core_output.write_text(
        json.dumps(asdict(core), indent=2, sort_keys=True, allow_nan=False) + "\n"
    )


if __name__ == "__main__":
    main()
