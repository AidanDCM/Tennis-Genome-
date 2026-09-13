from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from tennis_genome.independent.production import (
    ACCEPTED_CANONICAL_CONTENT,
    CANDIDATE_LIMIT,
    DEVELOPMENT_END_YEAR,
    PINNED_SOURCE_COMMIT,
    PINNED_SOURCE_REPO,
    PRIMARY_K,
    PRODUCTION_VERSION,
    IndependentProductionBundle,
    TourProductionArtifact,
    canonical_content_sha256,
)
from tennis_genome.independent.spec import MODEL_VERSION, architecture_hash
from tennis_genome.models.core_v1_spec import (
    ELO_FEATURES,
    a_plus_b_features,
    strict_a_features,
)

FROZEN_PRODUCTION_BUNDLE_SHA256 = "7a5874325d57d4fa670e5515607a2ec6a02ecedc9fdfb87338367e8e4556a2f1"
_ALIGNMENT_INPUTS = (
    "core_probability_favorite_logit",
    "neighbor_residual_k100",
)
_WTA_POINTSIM_INPUTS = (
    "alignment_probability_a_logit",
    "pointsim_probability_a_logit",
)
_ATP_UNFAMILIARITY_INPUTS = (
    "core_confidence",
    "core_confidence_squared",
    "log_pool_size",
)


def _validate_tour_contract(artifact: TourProductionArtifact, *, tour: str) -> None:
    if artifact.tour != tour:
        raise ValueError(f"production bundle {tour} slot contains {artifact.tour!r}")

    expected_content = canonical_content_sha256(ACCEPTED_CANONICAL_CONTENT[tour])
    if artifact.canonical_content_sha256 != expected_content:
        raise ValueError(f"{tour} canonical content hash is not the frozen source")

    expected_core = strict_a_features(tour)
    if artifact.core.feature_names != expected_core:
        raise ValueError(f"{tour} Core feature schema is not frozen strict Core v1")
    if artifact.core.training_n <= 0:
        raise ValueError(f"{tour} Core artifact has no training rows")
    if artifact.eligible_training_n <= 0:
        raise ValueError(f"{tour} production artifact has no eligible training rows")
    if artifact.eligible_training_n > ACCEPTED_CANONICAL_CONTENT[tour]["row_count"]:
        raise ValueError(f"{tour} eligible training count exceeds frozen canonical source")

    bank = artifact.neighbor_bank
    expected_representation = "full_genome" if tour == "ATP" else "strict_core_geometry"
    if bank.filename != f"{tour.lower()}_neighbor_bank.jsonl.gz":
        raise ValueError(f"{tour} neighbor-bank filename is not frozen")
    if bank.representation != expected_representation:
        raise ValueError(f"{tour} neighbor-bank representation is not frozen")
    if bank.k != PRIMARY_K:
        raise ValueError(f"{tour} neighbor-bank k is not frozen at {PRIMARY_K}")
    if bank.candidate_limit != CANDIDATE_LIMIT:
        raise ValueError(f"{tour} neighbor candidate limit is not frozen at {CANDIDATE_LIMIT}")
    if bank.row_count <= 0 or bank.row_count > artifact.eligible_training_n:
        raise ValueError(f"{tour} neighbor-bank row count is invalid")
    if artifact.alignment_meta.input_names != _ALIGNMENT_INPUTS:
        raise ValueError(f"{tour} historical-alignment meta schema is not frozen")
    if artifact.alignment_meta.training_n <= 0:
        raise ValueError(f"{tour} historical-alignment meta has no training rows")

    prefixed_core = tuple(f"core::{name}" for name in expected_core)
    if tour == "ATP":
        if bank.feature_names[: len(prefixed_core)] != prefixed_core:
            raise ValueError("ATP full-Genome bank does not begin with frozen Core geometry")
        if len(bank.feature_names) <= len(prefixed_core):
            raise ValueError("ATP full-Genome bank is missing Profile-aware dimensions")
        if artifact.wta_pointsim_meta is not None:
            raise ValueError("ATP artifact must not contain WTA PointSim meta")
        if artifact.wta_elo_diagnostic is not None:
            raise ValueError("ATP artifact must not contain WTA Elo diagnostic")
        if artifact.wta_a_plus_b_diagnostic is not None:
            raise ValueError("ATP artifact must not contain WTA A+B diagnostic")
        unfamiliarity = artifact.atp_conditioned_unfamiliarity
        if unfamiliarity is None:
            raise ValueError("ATP artifact lacks frozen conditioned unfamiliarity")
        if unfamiliarity.input_names != _ATP_UNFAMILIARITY_INPUTS:
            raise ValueError("ATP conditioned-unfamiliarity schema is not frozen")
        if unfamiliarity.training_n <= 0 or unfamiliarity.residual_sd <= 0.0:
            raise ValueError("ATP conditioned-unfamiliarity artifact is invalid")
        return

    if bank.feature_names != prefixed_core:
        raise ValueError("WTA neighbor bank is not frozen strict-Core geometry")
    if artifact.atp_conditioned_unfamiliarity is not None:
        raise ValueError("WTA artifact must not contain ATP conditioned unfamiliarity")
    if artifact.wta_pointsim_meta is None:
        raise ValueError("WTA artifact lacks frozen PointSim conditional meta")
    if artifact.wta_pointsim_meta.input_names != _WTA_POINTSIM_INPUTS:
        raise ValueError("WTA PointSim conditional meta schema is not frozen")
    if artifact.wta_pointsim_meta.training_n <= 0:
        raise ValueError("WTA PointSim conditional meta has no training rows")
    if artifact.wta_elo_diagnostic is None:
        raise ValueError("WTA artifact lacks frozen Elo disagreement diagnostic")
    if artifact.wta_elo_diagnostic.feature_names != tuple(ELO_FEATURES):
        raise ValueError("WTA Elo diagnostic schema is not frozen")
    if artifact.wta_a_plus_b_diagnostic is None:
        raise ValueError("WTA artifact lacks frozen A+B disagreement diagnostic")
    if artifact.wta_a_plus_b_diagnostic.feature_names != a_plus_b_features("WTA"):
        raise ValueError("WTA A+B diagnostic schema is not frozen")


def _recomputed_bundle_sha256(bundle: IndependentProductionBundle) -> str:
    payload = asdict(bundle)
    payload.pop("artifact_sha256", None)
    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def validate_frozen_bundle_authenticity(bundle: IndependentProductionBundle) -> None:
    """Authenticate in-memory content before allowing a production identity claim."""

    if _recomputed_bundle_sha256(bundle) != bundle.artifact_sha256:
        raise ValueError("production bundle semantic digest does not match object content")
    validate_frozen_bundle_contract(bundle)


def validate_frozen_bundle_contract(bundle: IndependentProductionBundle) -> None:
    """Fail closed if a bundle does not match the frozen production contract."""

    if bundle.artifact_sha256 != FROZEN_PRODUCTION_BUNDLE_SHA256:
        raise ValueError("production bundle SHA-256 is not the sealed TGE-Independent-v1")
    if bundle.model_version != MODEL_VERSION:
        raise ValueError("unexpected independent model version")
    if bundle.architecture_hash != architecture_hash():
        raise ValueError("independent architecture hash is not frozen")
    if bundle.production_version != PRODUCTION_VERSION:
        raise ValueError("independent production version is not frozen")
    if bundle.development_end_year != DEVELOPMENT_END_YEAR:
        raise ValueError(f"production development cutoff must remain {DEVELOPMENT_END_YEAR}")
    if bundle.source_repo != PINNED_SOURCE_REPO:
        raise ValueError("production source repository is not frozen")
    if bundle.source_commit != PINNED_SOURCE_COMMIT:
        raise ValueError("production source commit is not frozen")

    _validate_tour_contract(bundle.atp, tour="ATP")
    _validate_tour_contract(bundle.wta, tour="WTA")


def load_validated_matchup_calculator(path: Path):
    """Load the sealed bundle and construct the calculator only after contract validation."""

    from .engine import MatchupCalculator

    return MatchupCalculator.from_bundle_path(path)
