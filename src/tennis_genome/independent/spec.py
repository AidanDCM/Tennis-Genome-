from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Literal

from tennis_genome.data.canonical import Tour

MODEL_VERSION = "TGE-Independent-v1"
SPEC_VERSION = "1.0.0"


@dataclass(frozen=True)
class TourArchitecture:
    tour: Tour
    probability_path: tuple[str, ...]
    calibration: str
    diagnostics: tuple[str, ...]
    excluded_components: tuple[str, ...]
    notes: tuple[str, ...]


@dataclass(frozen=True)
class IndependentModelSpec:
    model_version: str
    spec_version: str
    development_data_end_year: int
    market_blind: Literal[True]
    hard_pass_policy_promoted: Literal[False]
    atp: TourArchitecture
    wta: TourArchitecture


TGE_INDEPENDENT_V1 = IndependentModelSpec(
    model_version=MODEL_VERSION,
    spec_version=SPEC_VERSION,
    development_data_end_year=2025,
    market_blind=True,
    hard_pass_policy_promoted=False,
    atp=TourArchitecture(
        tour="ATP",
        probability_path=(
            "strict_core_v1",
            "full_genome_historical_alignment_k100",
        ),
        calibration="identity",
        diagnostics=(
            "core_confidence",
            "conditioned_genome_unfamiliarity",
            "historical_neighbor_support",
            "data_quality",
        ),
        excluded_components=(
            "raw_pointsim_probability",
            "pointsim_incremental_component",
            "pure_surface_elo_replacement",
            "universal_uncertainty_composite",
        ),
        notes=(
            "Full Profile-aware Genome geometry passed GENOME-ADV-001 on ATP.",
            "Conditioned unfamiliarity is diagnostic only; no hard PASS threshold is frozen.",
        ),
    ),
    wta=TourArchitecture(
        tour="WTA",
        probability_path=(
            "strict_core_v1",
            "strict_core_geometry_historical_alignment_k100",
            "pointsim_conditional_meta_component",
        ),
        calibration="identity_after_pointsim_meta_mapping",
        diagnostics=(
            "core_confidence",
            "model_disagreement",
            "historical_neighbor_support",
            "data_quality",
        ),
        excluded_components=(
            "profile_aware_genome_geometry",
            "raw_pointsim_probability",
            "pure_surface_elo_replacement",
            "universal_uncertainty_composite",
        ),
        notes=(
            "Profile-aware Genome geometry failed the WTA adversarial gate.",
            "POINTSIM is a B/conditional residual input and not a standalone probability.",
            "Model disagreement is diagnostic only; no hard PASS threshold is frozen.",
        ),
    ),
)


def canonical_spec_json(spec: IndependentModelSpec = TGE_INDEPENDENT_V1) -> str:
    """Return stable JSON used to identify the frozen architecture."""

    return json.dumps(asdict(spec), sort_keys=True, separators=(",", ":"))


def architecture_hash(spec: IndependentModelSpec = TGE_INDEPENDENT_V1) -> str:
    return hashlib.sha256(canonical_spec_json(spec).encode("utf-8")).hexdigest()


def tour_spec(tour: Tour) -> TourArchitecture:
    if tour == "ATP":
        return TGE_INDEPENDENT_V1.atp
    if tour == "WTA":
        return TGE_INDEPENDENT_V1.wta
    raise ValueError(f"unsupported tour: {tour!r}")
