from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from scipy.special import expit
from sklearn.linear_model import LinearRegression

from tennis_genome.data.canonical import HistoricalMatch, Tour
from tennis_genome.data.manifest import verify_canonical_manifest
from tennis_genome.data.parquet import load_canonical_parquet
from tennis_genome.experiments.calibration_selective import ELO_FEATURES
from tennis_genome.experiments.genome_adversarial_controls import (
    _build_control_evidence,
    _core_genome,
    _fit_meta_model,
    _full_genome,
)
from tennis_genome.experiments.genome_neighborhood import _build_core_ledger
from tennis_genome.experiments.pointsim_adversarial import (
    _build_matched_rows,
    _challenger_features,
)
from tennis_genome.experiments.pointsim_adversarial import (
    _fit_logistic as _fit_pointsim_logistic,
)
from tennis_genome.experiments.uncertainty_ood import (
    _aligned_base_rows,
    _build_distance_rows,
    _conditioning_x,
)
from tennis_genome.features.foundational import (
    FoundationalSnapshot,
    walk_forward_foundational_features,
)
from tennis_genome.independent.spec import MODEL_VERSION, architecture_hash
from tennis_genome.models.core_v1_spec import a_plus_b_features, strict_a_features
from tennis_genome.models.feature_probability import FeatureProbabilityModel
from tennis_genome.neighbors.historical import ResidualRecord

PRODUCTION_VERSION = "TGE-Independent-v1-production-1"
DEVELOPMENT_END_YEAR = 2025
PRIMARY_K = 100
CANDIDATE_LIMIT = 1000
MIN_CORE_TRAIN_MATCHES = 1000
MIN_NEIGHBOR_POOL = 1000
MIN_META_TRAIN_ROWS = 1000
MIN_POINTSIM_TRAIN_ROWS = 1000
MIN_POINTSIM_META_ROWS = 1000
PINNED_SOURCE_REPO = "Aneeshers/tennis-sackmann-archive"
PINNED_SOURCE_COMMIT = "83733587353df8a41f2fd4f516147d5aa83f5a8d"

# Accepted GENOME-ADV-001 canonical-v3 payload hashes. The manifest wrapper itself
# is intentionally not used because it includes a volatile built_at_utc field.
ACCEPTED_CANONICAL_CONTENT = {
    "ATP": {
        "pre_match_sha256": "d1003f47322a58ff92ec1dc98d68168c136a7423a58cfd8e9f43530a6b252442",
        "outcome_sha256": "9ab4a2f850554081bc74eb381479a9529157ab8eb5f24d99cc13be57ee200fa0",
        "stats_sha256": "56b542915523a5e78bf7eedf91b6fbfea5a83f0a10498496bd4689747e08c0d9",
        "row_count": 77850,
    },
    "WTA": {
        "pre_match_sha256": "16c1b6ff231c10169142a6e038d035d56c082f843fe509084eda5436d4b39262",
        "outcome_sha256": "1b3da999ca7d8921d039766854386a1038962d564fc65e348dcec1e4c461a8a8",
        "stats_sha256": "db75fe1b22ab48c64e024a5acadc44ec1b18f536516ef7fb02f806c672bf1df1",
        "row_count": 71419,
    },
}


@dataclass(frozen=True)
class CoreMappingArtifact:
    feature_names: tuple[str, ...]
    training_n: int
    imputer_statistics: tuple[float, ...]
    imputer_indicator_features: tuple[int, ...]
    scaler_mean: tuple[float, ...]
    scaler_scale: tuple[float, ...]
    coefficients: tuple[float, ...]
    intercept: float


@dataclass(frozen=True)
class StandardizedLogisticArtifact:
    input_names: tuple[str, ...]
    training_n: int
    scaler_mean: tuple[float, ...]
    scaler_scale: tuple[float, ...]
    coefficients: tuple[float, ...]
    intercept: float


@dataclass(frozen=True)
class ConditionedUnfamiliarityArtifact:
    input_names: tuple[str, ...]
    training_n: int
    coefficients: tuple[float, ...]
    intercept: float
    residual_sd: float


@dataclass(frozen=True)
class NeighborBankArtifact:
    filename: str
    sha256: str
    row_count: int
    representation: str
    feature_names: tuple[str, ...]
    k: int
    candidate_limit: int


@dataclass(frozen=True)
class TourProductionArtifact:
    tour: Tour
    canonical_content_sha256: str
    eligible_training_n: int
    core: CoreMappingArtifact
    alignment_meta: StandardizedLogisticArtifact
    neighbor_bank: NeighborBankArtifact
    wta_pointsim_meta: StandardizedLogisticArtifact | None
    wta_elo_diagnostic: CoreMappingArtifact | None
    wta_a_plus_b_diagnostic: CoreMappingArtifact | None
    atp_conditioned_unfamiliarity: ConditionedUnfamiliarityArtifact | None


@dataclass(frozen=True)
class IndependentProductionBundle:
    model_version: str
    architecture_hash: str
    production_version: str
    development_end_year: int
    source_repo: str
    source_commit: str
    atp: TourProductionArtifact
    wta: TourProductionArtifact
    artifact_sha256: str


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _self_hash(payload: dict[str, Any]) -> str:
    unsigned = dict(payload)
    unsigned.pop("artifact_sha256", None)
    return _sha256_bytes(_canonical_json(unsigned))


def canonical_content_sha256(content: dict[str, object]) -> str:
    payload = {
        "pre_match_sha256": str(content["pre_match_sha256"]),
        "outcome_sha256": str(content["outcome_sha256"]),
        "stats_sha256": str(content["stats_sha256"]),
        "row_count": int(content["row_count"]),
    }
    return _sha256_bytes(_canonical_json(payload))


def verify_accepted_canonical_content(tour: Tour, manifest: dict[str, object]) -> str:
    accepted = ACCEPTED_CANONICAL_CONTENT[tour]
    observed = {
        "pre_match_sha256": str(manifest.get("pre_match_sha256", "")),
        "outcome_sha256": str(manifest.get("outcome_sha256", "")),
        "stats_sha256": str(manifest.get("stats_sha256", "")),
        "row_count": int(manifest.get("row_count", -1)),
    }
    if observed != accepted:
        raise ValueError(f"{tour} canonical content does not match accepted GENOME-ADV-001 source")
    return canonical_content_sha256(observed)


def _eligible(matches: list[HistoricalMatch], *, tour: Tour) -> list[HistoricalMatch]:
    selected = [match for match in matches if match.pre_match.tour == tour]
    if any(match.pre_match.event_date.year > DEVELOPMENT_END_YEAR for match in selected):
        raise ValueError(f"post-{DEVELOPMENT_END_YEAR} {tour} rows are forbidden")
    return [
        match for match in selected if not match.outcome.walkover and not match.outcome.retirement
    ]


def _core_artifact_from_model(
    model: FeatureProbabilityModel,
) -> CoreMappingArtifact:
    if model._pipeline is None:
        raise RuntimeError("feature model is not fitted")
    imputer = model._pipeline.named_steps["simpleimputer"]
    scaler = model._pipeline.named_steps["standardscaler"]
    logistic = model._pipeline.named_steps["logisticregression"]
    indicator = (
        ()
        if imputer.indicator_ is None
        else tuple(int(v) for v in imputer.indicator_.features_.tolist())
    )
    return CoreMappingArtifact(
        feature_names=tuple(model.feature_names),
        training_n=model.metadata.training_rows,
        imputer_statistics=tuple(float(v) for v in imputer.statistics_.tolist()),
        imputer_indicator_features=indicator,
        scaler_mean=tuple(float(v) for v in scaler.mean_.tolist()),
        scaler_scale=tuple(float(v) for v in scaler.scale_.tolist()),
        coefficients=tuple(float(v) for v in logistic.coef_[0].tolist()),
        intercept=float(logistic.intercept_[0]),
    )


def _fit_feature_artifact(
    snapshots: list[FoundationalSnapshot],
    outcomes: list[bool],
    feature_names: tuple[str, ...],
) -> CoreMappingArtifact:
    model = FeatureProbabilityModel(feature_names).fit(snapshots, outcomes)
    return _core_artifact_from_model(model)


def _standardized_logistic_artifact(
    model: object,
    *,
    input_names: tuple[str, ...],
    training_n: int,
) -> StandardizedLogisticArtifact:
    scaler = model.named_steps["standardscaler"]
    logistic = model.named_steps["logisticregression"]
    coefficients = tuple(float(v) for v in logistic.coef_[0].tolist())
    if len(coefficients) != len(input_names):
        raise RuntimeError("standardized logistic coefficient dimension mismatch")
    return StandardizedLogisticArtifact(
        input_names=input_names,
        training_n=training_n,
        scaler_mean=tuple(float(v) for v in scaler.mean_.tolist()),
        scaler_scale=tuple(float(v) for v in scaler.scale_.tolist()),
        coefficients=coefficients,
        intercept=float(logistic.intercept_[0]),
    )


def _bank_payload(record: ResidualRecord) -> dict[str, object]:
    genome = record.genome
    return {
        "match_id": genome.match_id,
        "event_date": genome.event_date.isoformat(),
        "tour": genome.tour,
        "player_a_id": genome.player_a_id,
        "player_b_id": genome.player_b_id,
        "orientation_sign": genome.orientation_sign,
        "feature_names": list(genome.feature_names),
        "values": list(genome.values),
        "feature_version": genome.feature_version,
        "residual_favorite": float(record.residual_favorite),
    }


def write_neighbor_bank(path: Path, records: list[ResidualRecord]) -> str:
    if not records:
        raise ValueError("neighbor bank cannot be empty")
    ordered = sorted(
        records,
        key=lambda item: (item.genome.event_date, item.genome.match_id),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0) as compressed:
            for record in ordered:
                compressed.write(_canonical_json(_bank_payload(record)) + b"\n")
    return _sha256_file(path)


def _production_state(
    eligible: list[HistoricalMatch], *, tour: Tour
) -> tuple[list[FoundationalSnapshot], list[bool]]:
    snapshots = walk_forward_foundational_features(eligible, exclude_retirements=False)
    outcome_by_id = {match.match_id: match.outcome.a_won for match in eligible}
    if len(snapshots) != len(eligible):
        raise RuntimeError("production foundational state did not cover every row")
    outcomes = [outcome_by_id[snapshot.match_id] for snapshot in snapshots]
    return snapshots, outcomes


def _alignment_freeze(
    eligible: list[HistoricalMatch],
    *,
    tour: Tour,
    output_dir: Path,
) -> tuple[StandardizedLogisticArtifact, NeighborBankArtifact]:
    ledger = _build_core_ledger(
        eligible,
        tour=tour,
        min_core_train_matches=MIN_CORE_TRAIN_MATCHES,
    )
    if len(ledger) < MIN_NEIGHBOR_POOL:
        raise ValueError("insufficient OOS Core ledger for production alignment bank")

    evidence = _build_control_evidence(ledger, min_neighbor_pool=MIN_NEIGHBOR_POOL)
    if len(evidence) < MIN_META_TRAIN_ROWS:
        raise ValueError("insufficient chronological alignment evidence")
    signal_field = "full_neighbor_residual" if tour == "ATP" else "core_neighbor_residual"
    model = _fit_meta_model(evidence, signal_field=signal_field)
    meta = _standardized_logistic_artifact(
        model,
        input_names=("core_probability_favorite_logit", "neighbor_residual_k100"),
        training_n=len(evidence),
    )

    records: list[ResidualRecord] = []
    for row in ledger:
        genome = _full_genome(row) if tour == "ATP" else _core_genome(row)
        records.append(
            ResidualRecord(
                genome=genome,
                residual_favorite=float(row.core_residual_favorite),
            )
        )
    feature_names = records[0].genome.feature_names
    if any(record.genome.feature_names != feature_names for record in records):
        raise RuntimeError("production neighbor bank feature schemas differ")
    filename = f"{tour.lower()}_neighbor_bank.jsonl.gz"
    bank_path = output_dir / filename
    bank_sha = write_neighbor_bank(bank_path, records)
    bank = NeighborBankArtifact(
        filename=filename,
        sha256=bank_sha,
        row_count=len(records),
        representation="full_genome" if tour == "ATP" else "strict_core_geometry",
        feature_names=feature_names,
        k=PRIMARY_K,
        candidate_limit=CANDIDATE_LIMIT,
    )
    return meta, bank


def _fit_atp_unfamiliarity(
    matches: list[HistoricalMatch],
) -> ConditionedUnfamiliarityArtifact:
    base_rows = _aligned_base_rows(
        matches,
        tour="ATP",
        min_core_train_matches=MIN_CORE_TRAIN_MATCHES,
    )
    distance_rows = _build_distance_rows(base_rows, min_neighbor_pool=MIN_NEIGHBOR_POOL)
    if len(distance_rows) < MIN_META_TRAIN_ROWS:
        raise ValueError("insufficient ATP distance evidence")
    matrix = [_conditioning_x(row) for row in distance_rows]
    observed = [math.log(max(row.raw_mean_distance_100, 1e-12)) for row in distance_rows]
    model = LinearRegression().fit(matrix, observed)
    predicted = model.predict(matrix).tolist()
    residuals = [a - b for a, b in zip(observed, predicted, strict=True)]
    mean_residual = sum(residuals) / len(residuals)
    variance = sum((value - mean_residual) ** 2 for value in residuals) / len(residuals)
    residual_sd = math.sqrt(variance)
    if not math.isfinite(residual_sd) or residual_sd <= 0.0:
        raise RuntimeError("ATP conditioned-unfamiliarity residual SD is invalid")
    return ConditionedUnfamiliarityArtifact(
        input_names=("core_confidence", "core_confidence_squared", "log_pool_size"),
        training_n=len(distance_rows),
        coefficients=tuple(float(v) for v in model.coef_.tolist()),
        intercept=float(model.intercept_),
        residual_sd=float(residual_sd),
    )


def _fit_wta_pointsim_meta(matches: list[HistoricalMatch]) -> StandardizedLogisticArtifact:
    rows = _build_matched_rows(
        matches,
        min_core_train_matches=MIN_CORE_TRAIN_MATCHES,
        min_neighbor_pool=MIN_NEIGHBOR_POOL,
        min_meta_train_rows=MIN_META_TRAIN_ROWS,
        min_pointsim_train_rows=MIN_POINTSIM_TRAIN_ROWS,
        exclude_retirements=True,
    )
    if len(rows) < MIN_POINTSIM_META_ROWS:
        raise ValueError("insufficient WTA POINTSIM meta rows")
    outcomes = [row.outcome_a for row in rows]
    model = _fit_pointsim_logistic(_challenger_features(rows), outcomes)
    return _standardized_logistic_artifact(
        model,
        input_names=("alignment_probability_a_logit", "pointsim_probability_a_logit"),
        training_n=len(rows),
    )


def _freeze_tour(
    matches: list[HistoricalMatch],
    *,
    tour: Tour,
    canonical_content: dict[str, object],
    output_dir: Path,
) -> TourProductionArtifact:
    eligible = _eligible(matches, tour=tour)
    if not eligible:
        raise ValueError(f"no eligible {tour} development rows")
    snapshots, outcomes = _production_state(eligible, tour=tour)
    core = _fit_feature_artifact(snapshots, outcomes, strict_a_features(tour))
    alignment_meta, neighbor_bank = _alignment_freeze(
        eligible,
        tour=tour,
        output_dir=output_dir,
    )

    wta_pointsim_meta = None
    wta_elo = None
    wta_a_plus_b = None
    atp_unfamiliarity = None
    if tour == "WTA":
        wta_pointsim_meta = _fit_wta_pointsim_meta(matches)
        wta_elo = _fit_feature_artifact(snapshots, outcomes, tuple(ELO_FEATURES))
        wta_a_plus_b = _fit_feature_artifact(
            snapshots,
            outcomes,
            a_plus_b_features("WTA"),
        )
    else:
        atp_unfamiliarity = _fit_atp_unfamiliarity(matches)

    return TourProductionArtifact(
        tour=tour,
        canonical_content_sha256=canonical_content_sha256(canonical_content),
        eligible_training_n=len(eligible),
        core=core,
        alignment_meta=alignment_meta,
        neighbor_bank=neighbor_bank,
        wta_pointsim_meta=wta_pointsim_meta,
        wta_elo_diagnostic=wta_elo,
        wta_a_plus_b_diagnostic=wta_a_plus_b,
        atp_conditioned_unfamiliarity=atp_unfamiliarity,
    )


def freeze_independent_production_bundle(
    *,
    atp_matches: list[HistoricalMatch],
    wta_matches: list[HistoricalMatch],
    atp_canonical_content: dict[str, object],
    wta_canonical_content: dict[str, object],
    output_dir: Path,
) -> IndependentProductionBundle:
    output_dir.mkdir(parents=True, exist_ok=True)
    atp = _freeze_tour(
        atp_matches,
        tour="ATP",
        canonical_content=atp_canonical_content,
        output_dir=output_dir,
    )
    wta = _freeze_tour(
        wta_matches,
        tour="WTA",
        canonical_content=wta_canonical_content,
        output_dir=output_dir,
    )
    unsigned: dict[str, Any] = {
        "model_version": MODEL_VERSION,
        "architecture_hash": architecture_hash(),
        "production_version": PRODUCTION_VERSION,
        "development_end_year": DEVELOPMENT_END_YEAR,
        "source_repo": PINNED_SOURCE_REPO,
        "source_commit": PINNED_SOURCE_COMMIT,
        "atp": asdict(atp),
        "wta": asdict(wta),
    }
    digest = _self_hash(unsigned)
    return IndependentProductionBundle(
        model_version=MODEL_VERSION,
        architecture_hash=architecture_hash(),
        production_version=PRODUCTION_VERSION,
        development_end_year=DEVELOPMENT_END_YEAR,
        source_repo=PINNED_SOURCE_REPO,
        source_commit=PINNED_SOURCE_COMMIT,
        atp=atp,
        wta=wta,
        artifact_sha256=digest,
    )


def bundle_as_dict(bundle: IndependentProductionBundle) -> dict[str, Any]:
    return asdict(bundle)


def write_bundle(path: Path, bundle: IndependentProductionBundle) -> None:
    path.write_text(json.dumps(bundle_as_dict(bundle), indent=2, sort_keys=True) + "\n")


def _core_from_dict(payload: dict[str, object]) -> CoreMappingArtifact:
    normalized = dict(payload)
    for field in (
        "feature_names",
        "imputer_statistics",
        "imputer_indicator_features",
        "scaler_mean",
        "scaler_scale",
        "coefficients",
    ):
        normalized[field] = tuple(normalized[field])
    return CoreMappingArtifact(**normalized)


def _logistic_from_dict(payload: dict[str, object]) -> StandardizedLogisticArtifact:
    normalized = dict(payload)
    for field in ("input_names", "scaler_mean", "scaler_scale", "coefficients"):
        normalized[field] = tuple(normalized[field])
    return StandardizedLogisticArtifact(**normalized)


def _unfamiliarity_from_dict(payload: dict[str, object]) -> ConditionedUnfamiliarityArtifact:
    normalized = dict(payload)
    normalized["input_names"] = tuple(normalized["input_names"])
    normalized["coefficients"] = tuple(normalized["coefficients"])
    return ConditionedUnfamiliarityArtifact(**normalized)


def _bank_from_dict(payload: dict[str, object]) -> NeighborBankArtifact:
    normalized = dict(payload)
    normalized["feature_names"] = tuple(normalized["feature_names"])
    return NeighborBankArtifact(**normalized)


def _tour_from_dict(payload: dict[str, object]) -> TourProductionArtifact:
    normalized = dict(payload)
    normalized["core"] = _core_from_dict(dict(normalized["core"]))
    normalized["alignment_meta"] = _logistic_from_dict(dict(normalized["alignment_meta"]))
    normalized["neighbor_bank"] = _bank_from_dict(dict(normalized["neighbor_bank"]))
    if normalized.get("wta_pointsim_meta") is not None:
        normalized["wta_pointsim_meta"] = _logistic_from_dict(dict(normalized["wta_pointsim_meta"]))
    if normalized.get("wta_elo_diagnostic") is not None:
        normalized["wta_elo_diagnostic"] = _core_from_dict(dict(normalized["wta_elo_diagnostic"]))
    if normalized.get("wta_a_plus_b_diagnostic") is not None:
        normalized["wta_a_plus_b_diagnostic"] = _core_from_dict(
            dict(normalized["wta_a_plus_b_diagnostic"])
        )
    if normalized.get("atp_conditioned_unfamiliarity") is not None:
        normalized["atp_conditioned_unfamiliarity"] = _unfamiliarity_from_dict(
            dict(normalized["atp_conditioned_unfamiliarity"])
        )
    return TourProductionArtifact(**normalized)


def load_bundle(path: Path, *, verify_banks: bool = True) -> IndependentProductionBundle:
    payload = json.loads(path.read_text())
    if payload.get("model_version") != MODEL_VERSION:
        raise ValueError("unexpected independent production model version")
    if payload.get("architecture_hash") != architecture_hash():
        raise ValueError("independent production architecture hash mismatch")
    if payload.get("production_version") != PRODUCTION_VERSION:
        raise ValueError("unexpected independent production bundle version")
    if _self_hash(payload) != payload.get("artifact_sha256"):
        raise ValueError("independent production bundle digest mismatch")
    bundle = IndependentProductionBundle(
        model_version=str(payload["model_version"]),
        architecture_hash=str(payload["architecture_hash"]),
        production_version=str(payload["production_version"]),
        development_end_year=int(payload["development_end_year"]),
        source_repo=str(payload["source_repo"]),
        source_commit=str(payload["source_commit"]),
        atp=_tour_from_dict(dict(payload["atp"])),
        wta=_tour_from_dict(dict(payload["wta"])),
        artifact_sha256=str(payload["artifact_sha256"]),
    )
    if verify_banks:
        for tour_artifact in (bundle.atp, bundle.wta):
            bank_path = path.parent / tour_artifact.neighbor_bank.filename
            if not bank_path.is_file():
                raise ValueError(f"missing neighbor bank: {bank_path.name}")
            if _sha256_file(bank_path) != tour_artifact.neighbor_bank.sha256:
                raise ValueError(f"neighbor bank digest mismatch: {bank_path.name}")
    return bundle


def core_probability_from_artifact(
    snapshot: FoundationalSnapshot,
    artifact: CoreMappingArtifact,
) -> float:
    raw: list[float] = []
    missing: list[bool] = []
    if len(artifact.imputer_statistics) != len(artifact.feature_names):
        raise ValueError("core artifact imputer dimension mismatch")
    for index, name in enumerate(artifact.feature_names):
        value = getattr(snapshot, name)
        is_missing = value is None
        missing.append(is_missing)
        raw.append(artifact.imputer_statistics[index] if is_missing else float(value))
    expanded = list(raw)
    expanded.extend(1.0 if missing[index] else 0.0 for index in artifact.imputer_indicator_features)
    if not (
        len(expanded)
        == len(artifact.scaler_mean)
        == len(artifact.scaler_scale)
        == len(artifact.coefficients)
    ):
        raise ValueError("core artifact transformed dimension mismatch")
    standardized = [
        (value - mean) / scale
        for value, mean, scale in zip(
            expanded,
            artifact.scaler_mean,
            artifact.scaler_scale,
            strict=True,
        )
    ]
    logit = artifact.intercept + sum(
        coefficient * value
        for coefficient, value in zip(
            artifact.coefficients,
            standardized,
            strict=True,
        )
    )
    return float(expit(logit))


def standardized_logistic_probability(
    values: tuple[float, ...], artifact: StandardizedLogisticArtifact
) -> float:
    if not (
        len(values)
        == len(artifact.input_names)
        == len(artifact.scaler_mean)
        == len(artifact.scaler_scale)
        == len(artifact.coefficients)
    ):
        raise ValueError("standardized logistic input dimension mismatch")
    standardized = [
        (float(value) - mean) / scale
        for value, mean, scale in zip(
            values,
            artifact.scaler_mean,
            artifact.scaler_scale,
            strict=True,
        )
    ]
    logit = artifact.intercept + sum(
        coefficient * value
        for coefficient, value in zip(
            artifact.coefficients,
            standardized,
            strict=True,
        )
    )
    return float(expit(logit))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Freeze TGE-Independent-v1 production artifacts")
    for tour in ("atp", "wta"):
        parser.add_argument(f"--{tour}-manifest", required=True, type=Path)
        parser.add_argument(f"--{tour}-pre-match", required=True, type=Path)
        parser.add_argument(f"--{tour}-outcomes", required=True, type=Path)
        parser.add_argument(f"--{tour}-stats", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args()


def _load_tour(
    args: argparse.Namespace, tour: str
) -> tuple[list[HistoricalMatch], dict[str, object]]:
    prefix = tour.lower()
    manifest_path: Path = getattr(args, f"{prefix}_manifest")
    pre_match_path: Path = getattr(args, f"{prefix}_pre_match")
    outcome_path: Path = getattr(args, f"{prefix}_outcomes")
    stats_path: Path = getattr(args, f"{prefix}_stats")
    manifest = verify_canonical_manifest(
        manifest_path=manifest_path,
        pre_match_path=pre_match_path,
        outcome_path=outcome_path,
        stats_path=stats_path,
        require_research_permission=True,
    )
    verify_accepted_canonical_content(tour, manifest)
    matches = load_canonical_parquet(
        pre_match_path=pre_match_path,
        outcome_path=outcome_path,
        stats_path=stats_path,
    )
    return matches, ACCEPTED_CANONICAL_CONTENT[tour]


def main() -> None:
    args = _parse_args()
    atp_matches, atp_content = _load_tour(args, "ATP")
    wta_matches, wta_content = _load_tour(args, "WTA")
    bundle = freeze_independent_production_bundle(
        atp_matches=atp_matches,
        wta_matches=wta_matches,
        atp_canonical_content=atp_content,
        wta_canonical_content=wta_content,
        output_dir=args.output_dir,
    )
    write_bundle(args.output_dir / "tge_independent_v1_production.json", bundle)
    print(json.dumps(bundle_as_dict(bundle), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
