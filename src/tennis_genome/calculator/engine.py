from __future__ import annotations

import gzip
import json
import math
from datetime import date
from pathlib import Path

from tennis_genome.features.genome import (
    GENOME_VERSION,
    GenomeVector,
    build_genome_vector,
    canonical_orientation_sign,
    canonical_probability,
    original_probability,
)
from tennis_genome.independent.prediction import IndependentPrediction
from tennis_genome.independent.production import (
    PRODUCTION_VERSION,
    ConditionedUnfamiliarityArtifact,
    IndependentProductionBundle,
    NeighborBankArtifact,
    TourProductionArtifact,
    core_probability_from_artifact,
    load_bundle,
    standardized_logistic_probability,
)
from tennis_genome.independent.spec import MODEL_VERSION, architecture_hash
from tennis_genome.models.core_v1_spec import strict_a_features
from tennis_genome.neighbors.historical import (
    HistoricalGenomeIndex,
    NeighborSummary,
    ResidualRecord,
)
from tennis_genome.simulation.tennis import point_sim_match_probability

from .types import FairDecimalOdds, MatchupCalculation, MatchupInput

_VERIFIED_PRODUCTION_BANKS = object()


def _clip_probability(value: float) -> float:
    return min(max(float(value), 1e-9), 1.0 - 1e-9)


def _logit_probability(value: float) -> float:
    probability = _clip_probability(value)
    return math.log(probability / (1.0 - probability))


def _fair_price(probability: float) -> float | None:
    probability = float(probability)
    if probability <= 0.0:
        return None
    return 1.0 / probability


def fair_decimal_odds(p_player_a: float, p_player_b: float) -> FairDecimalOdds:
    if not 0.0 <= p_player_a <= 1.0 or not 0.0 <= p_player_b <= 1.0:
        raise ValueError("fair-odds probabilities must be in [0, 1]")
    if abs((p_player_a + p_player_b) - 1.0) > 1e-9:
        raise ValueError("fair-odds probabilities must sum to one")
    return FairDecimalOdds(
        player_a=_fair_price(p_player_a),
        player_b=_fair_price(p_player_b),
    )


def _record_from_payload(payload: dict[str, object]) -> ResidualRecord:
    genome = GenomeVector(
        match_id=str(payload["match_id"]),
        event_date=date.fromisoformat(str(payload["event_date"])),
        tour=str(payload["tour"]),
        player_a_id=str(payload["player_a_id"]),
        player_b_id=str(payload["player_b_id"]),
        orientation_sign=int(payload["orientation_sign"]),
        feature_names=tuple(str(value) for value in payload["feature_names"]),
        values=tuple(None if value is None else float(value) for value in payload["values"]),
        feature_version=str(payload["feature_version"]),
    )
    return ResidualRecord(
        genome=genome,
        residual_favorite=float(payload["residual_favorite"]),
    )


def load_neighbor_bank(
    bundle_path: Path,
    artifact: NeighborBankArtifact,
) -> tuple[ResidualRecord, ...]:
    path = bundle_path.parent / artifact.filename
    records: list[ResidualRecord] = []
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(_record_from_payload(json.loads(line)))
    if len(records) != artifact.row_count:
        raise ValueError(f"neighbor bank row count mismatch: {artifact.filename}")
    if not records:
        raise ValueError(f"neighbor bank is empty: {artifact.filename}")
    if any(record.genome.feature_names != artifact.feature_names for record in records):
        raise ValueError(f"neighbor bank feature schema mismatch: {artifact.filename}")
    return tuple(records)


def _strict_core_vector(matchup: MatchupInput) -> GenomeVector:
    sign = canonical_orientation_sign(
        elo_logit=matchup.foundational.elo_logit,
        player_a_id=matchup.player_a_id,
        player_b_id=matchup.player_b_id,
    )
    names = strict_a_features(matchup.tour)
    values: list[float | None] = []
    for name in names:
        value = getattr(matchup.foundational, name)
        values.append(None if value is None else sign * float(value))
    return GenomeVector(
        match_id=matchup.match_id,
        event_date=matchup.foundational.event_date,
        tour=matchup.tour,
        player_a_id=matchup.player_a_id,
        player_b_id=matchup.player_b_id,
        orientation_sign=sign,
        feature_names=tuple(f"core::{name}" for name in names),
        values=tuple(values),
        feature_version=f"{GENOME_VERSION}:core",
    )


def _historical_summary(
    *,
    target: GenomeVector,
    records: tuple[ResidualRecord, ...],
    artifact: NeighborBankArtifact,
) -> tuple[NeighborSummary, int]:
    historical = [record for record in records if record.genome.event_date < target.event_date]
    if len(historical) < artifact.k:
        raise ValueError(
            f"insufficient strictly earlier neighbor history: {len(historical)} < {artifact.k}"
        )
    index = HistoricalGenomeIndex(historical)
    candidate_set = index.query_candidates(
        [target],
        candidate_limit=artifact.candidate_limit,
    )[0]
    summary = index.summarize(target, candidate_set, k=artifact.k)
    if summary is None:
        raise RuntimeError("frozen k-neighbor summary is unavailable")
    return summary, len(historical)


def _alignment_probability_a(
    *,
    core_probability_a: float,
    target: GenomeVector,
    summary: NeighborSummary,
    artifact: TourProductionArtifact,
) -> float:
    core_favorite = canonical_probability(
        core_probability_a,
        orientation_sign=target.orientation_sign,
    )
    favorite_probability = standardized_logistic_probability(
        (
            _logit_probability(core_favorite),
            float(summary.mean_residual),
        ),
        artifact.alignment_meta,
    )
    return original_probability(
        favorite_probability,
        orientation_sign=target.orientation_sign,
    )


def _conditioned_unfamiliarity(
    *,
    core_probability_a: float,
    mean_distance: float,
    historical_pool_size: int,
    artifact: ConditionedUnfamiliarityArtifact,
) -> float:
    confidence = abs(float(core_probability_a) - 0.5)
    values = (
        confidence,
        confidence * confidence,
        math.log(max(historical_pool_size, 1)),
    )
    if len(values) != len(artifact.coefficients):
        raise ValueError("conditioned-unfamiliarity artifact dimension mismatch")
    expected = artifact.intercept + sum(
        coefficient * value
        for coefficient, value in zip(artifact.coefficients, values, strict=True)
    )
    observed = math.log(max(float(mean_distance), 1e-12))
    return (observed - expected) / artifact.residual_sd


class MatchupCalculator:
    """Inference-only orchestrator for the frozen TGE-Independent-v1 architecture."""

    def __init__(
        self,
        bundle: IndependentProductionBundle,
        *,
        atp_neighbor_bank: tuple[ResidualRecord, ...],
        wta_neighbor_bank: tuple[ResidualRecord, ...],
        _production_bank_token: object | None = None,
    ) -> None:
        from .contract import FROZEN_PRODUCTION_BUNDLE_SHA256, validate_frozen_bundle_authenticity

        if bundle.artifact_sha256 == FROZEN_PRODUCTION_BUNDLE_SHA256:
            validate_frozen_bundle_authenticity(bundle)
            if _production_bank_token is not _VERIFIED_PRODUCTION_BANKS:
                raise ValueError(
                    "sealed production neighbor banks must be loaded through "
                    "MatchupCalculator.from_bundle_path(...)"
                )
        if bundle.model_version != MODEL_VERSION:
            raise ValueError("unexpected independent production model version")
        if bundle.architecture_hash != architecture_hash():
            raise ValueError("independent production architecture hash mismatch")
        if bundle.production_version != PRODUCTION_VERSION:
            raise ValueError("unexpected independent production bundle version")
        self.bundle = bundle
        self._atp_bank = atp_neighbor_bank
        self._wta_bank = wta_neighbor_bank
        self._validate_bank(self.bundle.atp, self._atp_bank)
        self._validate_bank(self.bundle.wta, self._wta_bank)

    @classmethod
    def from_bundle_path(cls, path: Path) -> MatchupCalculator:
        from .contract import validate_frozen_bundle_contract

        bundle = load_bundle(path, verify_banks=True)
        validate_frozen_bundle_contract(bundle)
        return cls(
            bundle,
            atp_neighbor_bank=load_neighbor_bank(path, bundle.atp.neighbor_bank),
            wta_neighbor_bank=load_neighbor_bank(path, bundle.wta.neighbor_bank),
            _production_bank_token=_VERIFIED_PRODUCTION_BANKS,
        )

    @staticmethod
    def _validate_bank(
        artifact: TourProductionArtifact,
        records: tuple[ResidualRecord, ...],
    ) -> None:
        if len(records) != artifact.neighbor_bank.row_count:
            raise ValueError(f"{artifact.tour} neighbor bank row count mismatch")
        if any(record.genome.tour != artifact.tour for record in records):
            raise ValueError(f"{artifact.tour} neighbor bank contains mixed tours")
        if any(
            record.genome.feature_names != artifact.neighbor_bank.feature_names
            for record in records
        ):
            raise ValueError(f"{artifact.tour} neighbor bank feature schema mismatch")

    def calculate(self, matchup: MatchupInput) -> MatchupCalculation:
        if matchup.prediction_cutoff_at.year <= self.bundle.development_end_year:
            raise ValueError(
                "prediction cutoff must occur after the frozen production development period"
            )
        if matchup.foundational.event_date.year <= self.bundle.development_end_year:
            raise ValueError(
                "terminal production bundle cannot be used for in-development historical "
                "replay; use a chronological replay engine instead"
            )
        if matchup.tour == "ATP":
            return self._calculate_atp(matchup)
        if matchup.tour == "WTA":
            return self._calculate_wta(matchup)
        raise ValueError(f"unsupported tour: {matchup.tour!r}")

    def _calculation(
        self,
        *,
        matchup: MatchupInput,
        prediction: IndependentPrediction,
    ) -> MatchupCalculation:
        return MatchupCalculation(
            prediction=prediction,
            player_a_id=matchup.player_a_id,
            player_b_id=matchup.player_b_id,
            fair_decimal_odds=fair_decimal_odds(
                prediction.p_player_a,
                prediction.p_player_b,
            ),
            production_bundle_sha256=self.bundle.artifact_sha256,
        )

    def _calculate_atp(self, matchup: MatchupInput) -> MatchupCalculation:
        if matchup.profile_pair is None:
            raise ValueError("ATP matchup calculation requires profile_pair")
        artifact = self.bundle.atp
        core_probability_a = core_probability_from_artifact(
            matchup.foundational,
            artifact.core,
        )
        target = build_genome_vector(matchup.profile_pair, matchup.foundational)
        if target.player_a_id != matchup.player_a_id or target.player_b_id != matchup.player_b_id:
            raise ValueError("ATP Genome identities differ from matchup input")
        summary, pool_size = _historical_summary(
            target=target,
            records=self._atp_bank,
            artifact=artifact.neighbor_bank,
        )
        alignment_probability_a = _alignment_probability_a(
            core_probability_a=core_probability_a,
            target=target,
            summary=summary,
            artifact=artifact,
        )
        unfamiliarity_artifact = artifact.atp_conditioned_unfamiliarity
        if unfamiliarity_artifact is None:
            raise RuntimeError("ATP production bundle lacks conditioned unfamiliarity")
        conditioned_unfamiliarity = _conditioned_unfamiliarity(
            core_probability_a=core_probability_a,
            mean_distance=summary.mean_distance,
            historical_pool_size=pool_size,
            artifact=unfamiliarity_artifact,
        )
        min_prior_matches = min(
            matchup.profile_pair.player_a.prior_matches,
            matchup.profile_pair.player_b.prior_matches,
        )
        min_prior_points = min(
            matchup.profile_pair.player_a.prior_serve_points,
            matchup.profile_pair.player_a.prior_return_points,
            matchup.profile_pair.player_b.prior_serve_points,
            matchup.profile_pair.player_b.prior_return_points,
        )
        prediction = IndependentPrediction(
            prediction_id=matchup.prediction_id,
            match_id=matchup.match_id,
            tour=matchup.tour,
            created_at=matchup.created_at,
            prediction_cutoff_at=matchup.prediction_cutoff_at,
            p_player_a=alignment_probability_a,
            p_player_b=1.0 - alignment_probability_a,
            component_probabilities={
                "strict_core_v1": core_probability_a,
                "full_genome_historical_alignment_k100": alignment_probability_a,
            },
            diagnostics={
                "core_confidence": abs(core_probability_a - 0.5),
                "conditioned_genome_unfamiliarity": conditioned_unfamiliarity,
                "historical_neighbor_pool_size": pool_size,
                "historical_neighbor_k": summary.k,
                "historical_neighbor_nearest_distance": summary.nearest_distance,
                "historical_neighbor_mean_distance": summary.mean_distance,
                "historical_neighbor_kth_distance": summary.kth_distance,
                "historical_neighbor_shared_player_fraction": summary.shared_player_fraction,
                "alignment_missing_fraction": target.missing_fraction,
                "min_prior_matches": min_prior_matches,
                "min_prior_point_exposure": min_prior_points,
                "hard_pass_policy_promoted": False,
            },
            source_manifest_hashes=matchup.source_manifest_hashes,
            reason_codes=("NO_HARD_PASS_POLICY",),
        )
        return self._calculation(matchup=matchup, prediction=prediction)

    def _calculate_wta(self, matchup: MatchupInput) -> MatchupCalculation:
        if matchup.serve_return is None:
            raise ValueError("WTA matchup calculation requires serve_return state")
        artifact = self.bundle.wta
        if artifact.wta_pointsim_meta is None:
            raise RuntimeError("WTA production bundle lacks PointSim meta mapping")
        if artifact.wta_elo_diagnostic is None or artifact.wta_a_plus_b_diagnostic is None:
            raise RuntimeError("WTA production bundle lacks disagreement diagnostics")

        core_probability_a = core_probability_from_artifact(
            matchup.foundational,
            artifact.core,
        )
        target = _strict_core_vector(matchup)
        summary, pool_size = _historical_summary(
            target=target,
            records=self._wta_bank,
            artifact=artifact.neighbor_bank,
        )
        alignment_probability_a = _alignment_probability_a(
            core_probability_a=core_probability_a,
            target=target,
            summary=summary,
            artifact=artifact,
        )
        pointsim_probability_a = point_sim_match_probability(
            matchup.serve_return.probability_a_serve_point,
            matchup.serve_return.probability_b_serve_point,
            best_of=matchup.best_of,
        )
        final_probability_a = standardized_logistic_probability(
            (
                _logit_probability(alignment_probability_a),
                _logit_probability(pointsim_probability_a),
            ),
            artifact.wta_pointsim_meta,
        )
        elo_probability_a = core_probability_from_artifact(
            matchup.foundational,
            artifact.wta_elo_diagnostic,
        )
        a_plus_b_probability_a = core_probability_from_artifact(
            matchup.foundational,
            artifact.wta_a_plus_b_diagnostic,
        )
        disagreement = max(
            elo_probability_a,
            core_probability_a,
            a_plus_b_probability_a,
        ) - min(
            elo_probability_a,
            core_probability_a,
            a_plus_b_probability_a,
        )
        min_point_history = min(
            matchup.serve_return.prior_serve_points_a,
            matchup.serve_return.prior_serve_points_b,
            matchup.serve_return.prior_return_points_a,
            matchup.serve_return.prior_return_points_b,
        )
        prediction = IndependentPrediction(
            prediction_id=matchup.prediction_id,
            match_id=matchup.match_id,
            tour=matchup.tour,
            created_at=matchup.created_at,
            prediction_cutoff_at=matchup.prediction_cutoff_at,
            p_player_a=final_probability_a,
            p_player_b=1.0 - final_probability_a,
            component_probabilities={
                "strict_core_v1": core_probability_a,
                "strict_core_geometry_historical_alignment_k100": alignment_probability_a,
                "pointsim_conditional_meta_input": pointsim_probability_a,
                "pointsim_conditional_meta_final": final_probability_a,
            },
            diagnostics={
                "core_confidence": abs(core_probability_a - 0.5),
                "model_disagreement": disagreement,
                "historical_neighbor_pool_size": pool_size,
                "historical_neighbor_k": summary.k,
                "historical_neighbor_nearest_distance": summary.nearest_distance,
                "historical_neighbor_mean_distance": summary.mean_distance,
                "historical_neighbor_kth_distance": summary.kth_distance,
                "historical_neighbor_shared_player_fraction": summary.shared_player_fraction,
                "alignment_missing_fraction": target.missing_fraction,
                "pointsim_min_prior_point_history": min_point_history,
                "hard_pass_policy_promoted": False,
            },
            source_manifest_hashes=matchup.source_manifest_hashes,
            reason_codes=("NO_HARD_PASS_POLICY",),
        )
        return self._calculation(matchup=matchup, prediction=prediction)
