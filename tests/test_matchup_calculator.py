from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import pytest

from tennis_genome.calculator.engine import MatchupCalculator, fair_decimal_odds
from tennis_genome.calculator.types import MatchupInput
from tennis_genome.features.foundational import FoundationalSnapshot
from tennis_genome.features.genome import GenomeVector, build_genome_vector
from tennis_genome.independent.production import (
    ConditionedUnfamiliarityArtifact,
    CoreMappingArtifact,
    IndependentProductionBundle,
    NeighborBankArtifact,
    StandardizedLogisticArtifact,
    TourProductionArtifact,
    standardized_logistic_probability,
)
from tennis_genome.independent.spec import MODEL_VERSION, architecture_hash
from tennis_genome.models.core_v1_spec import a_plus_b_features, strict_a_features
from tennis_genome.neighbors.historical import ResidualRecord
from tennis_genome.profiles.state import (
    MatchProfilePair,
    PlayerProfileSnapshot,
)
from tennis_genome.ratings.serve_return import ServeReturnSnapshot
from tennis_genome.simulation.tennis import point_sim_match_probability


def _foundational(
    *, match_id: str, event_date: date, elo_logit: float = 0.4
) -> FoundationalSnapshot:
    return FoundationalSnapshot(
        match_id=match_id,
        event_date=event_date,
        elo_logit=elo_logit,
        serve_return_edge=0.03,
        serve_rating_diff=0.02,
        return_rating_diff=-0.01,
        min_prior_points=1500,
        form_result_30_diff=0.04,
        form_result_90_diff=0.02,
        form_point_30_diff=0.01,
        form_point_90_diff=0.01,
        event_gap_days_diff=2.0,
        minutes_7_diff=30.0,
        minutes_14_diff=45.0,
        minutes_28_diff=60.0,
        matches_14_diff=1.0,
        matches_28_diff=1.0,
        previous_event_minutes_diff=10.0,
        age_diff=-1.0,
        age_curve_diff=0.2,
        young_diff=0.0,
        veteran_diff=0.0,
        height_diff=3.0,
        age_x_minutes_14_diff=-20.0,
        age_x_short_gap_diff=0.0,
        h2h_edge=0.1,
        h2h_weighted_edge=0.05,
        h2h_count=3,
        left_hand_diff=0.0,
        opposite_hand_serve_edge=0.0,
        surface_hard_elo=0.1,
        surface_clay_elo=0.0,
        surface_grass_elo=0.0,
        surface_carpet_elo=0.0,
        surface_hard_serve=0.02,
        surface_clay_serve=0.0,
        surface_grass_serve=0.0,
        surface_carpet_serve=0.0,
        slam_elo=0.0,
        masters_elo=0.1,
        finals_elo=0.0,
        lower_tier_elo=0.0,
        late_round_elo=0.0,
        round_robin_elo=0.0,
        best_of_five_elo=0.0,
        qualifier_diff=0.0,
        wildcard_diff=0.0,
        lucky_loser_diff=0.0,
        protected_ranking_diff=0.0,
        seeded_diff=1.0,
        seed_strength_diff=0.1,
    )


def _profile(
    *, player_id: str, player_name: str, tour: str, event_date: date
) -> PlayerProfileSnapshot:
    return PlayerProfileSnapshot(
        player_id=player_id,
        player_name=player_name,
        tour=tour,
        valid_from=event_date,
        valid_until=None,
        profile_version="player-profile-v1",
        ranking=20,
        ranking_points=2000,
        age_years=26.0,
        height_cm=185,
        hand="R",
        ioc="USA",
        elo_rating=1550.0,
        prior_matches=80,
        serve_rating=0.05,
        return_rating=0.02,
        prior_serve_points=5000,
        prior_return_points=4800,
        form_result_30=0.03,
        form_result_90=0.02,
        form_point_30=0.01,
        form_point_90=0.01,
        event_gap_days=7.0,
        minutes_7=100.0,
        minutes_14=200.0,
        minutes_28=350.0,
        matches_14=2,
        matches_28=4,
        previous_event_minutes=90,
        has_point_history=True,
        has_complete_14d_duration=True,
    )


def _profile_pair(*, match_id: str, event_date: date, tour: str = "ATP") -> MatchProfilePair:
    return MatchProfilePair(
        match_id=match_id,
        event_date=event_date,
        player_a=_profile(
            player_id="player-a",
            player_name="Player A",
            tour=tour,
            event_date=event_date,
        ),
        player_b=_profile(
            player_id="player-b",
            player_name="Player B",
            tour=tour,
            event_date=event_date,
        ),
    )


def _serve_return(*, match_id: str, event_date: date) -> ServeReturnSnapshot:
    return ServeReturnSnapshot(
        match_id=match_id,
        event_date=event_date,
        probability_a_serve_point=0.66,
        probability_b_serve_point=0.62,
        matchup_edge_a=0.04,
        prior_serve_points_a=5000,
        prior_serve_points_b=4500,
        prior_return_points_a=4800,
        prior_return_points_b=4400,
        serve_rating_a=0.05,
        serve_rating_b=0.01,
        return_rating_a=0.03,
        return_rating_b=0.00,
        serve_rating_diff_a=0.04,
        return_rating_diff_a=0.03,
    )


def _core_artifact(
    feature_names: tuple[str, ...], *, elo_weight: float = 1.0
) -> CoreMappingArtifact:
    coefficients = tuple(
        elo_weight if name == "elo_logit" else 0.0 for name in feature_names
    )
    return CoreMappingArtifact(
        feature_names=feature_names,
        training_n=5000,
        imputer_statistics=tuple(0.0 for _ in feature_names),
        imputer_indicator_features=(),
        scaler_mean=tuple(0.0 for _ in feature_names),
        scaler_scale=tuple(1.0 for _ in feature_names),
        coefficients=coefficients,
        intercept=0.0,
    )


def _logistic_artifact(
    input_names: tuple[str, ...],
    coefficients: tuple[float, ...],
) -> StandardizedLogisticArtifact:
    return StandardizedLogisticArtifact(
        input_names=input_names,
        training_n=4000,
        scaler_mean=tuple(0.0 for _ in input_names),
        scaler_scale=tuple(1.0 for _ in input_names),
        coefficients=coefficients,
        intercept=0.0,
    )


def _bank_artifact(
    *, tour: str, feature_names: tuple[str, ...], row_count: int
) -> NeighborBankArtifact:
    return NeighborBankArtifact(
        filename=f"{tour.lower()}_neighbor_bank.jsonl.gz",
        sha256="0" * 64,
        row_count=row_count,
        representation="full_genome" if tour == "ATP" else "strict_core_geometry",
        feature_names=feature_names,
        k=100,
        candidate_limit=1000,
    )


def _historical_bank(
    target: GenomeVector,
    *,
    include_future: bool = False,
) -> tuple[ResidualRecord, ...]:
    records: list[ResidualRecord] = []
    base_date = date(2024, 1, 1)
    adjustable_index = next(
        (index for index, value in enumerate(target.values) if value is not None),
        0,
    )
    for index in range(100):
        values = list(target.values)
        base_value = values[adjustable_index]
        values[adjustable_index] = (
            (0.0 if base_value is None else float(base_value)) + index * 0.001
        )
        records.append(
            ResidualRecord(
                genome=replace(
                    target,
                    match_id=f"history-{target.tour.lower()}-{index}",
                    event_date=base_date + timedelta(days=index),
                    player_a_id=f"ha-{index}",
                    player_b_id=f"hb-{index}",
                    values=tuple(values),
                ),
                residual_favorite=(index - 50) / 1000.0,
            )
        )
    if include_future:
        records.append(
            ResidualRecord(
                genome=replace(
                    target,
                    match_id=f"future-{target.tour.lower()}",
                    event_date=date(2027, 1, 1),
                    player_a_id="future-a",
                    player_b_id="future-b",
                ),
                residual_favorite=0.9,
            )
        )
    return tuple(records)


def _wta_target(matchup: MatchupInput) -> GenomeVector:
    names = strict_a_features("WTA")
    values = tuple(
        float(getattr(matchup.foundational, name) or 0.0) for name in names
    )
    return GenomeVector(
        match_id=matchup.match_id,
        event_date=matchup.foundational.event_date,
        tour="WTA",
        player_a_id=matchup.player_a_id,
        player_b_id=matchup.player_b_id,
        orientation_sign=1,
        feature_names=tuple(f"core::{name}" for name in names),
        values=values,
        feature_version="genome-v1-core-plus-profile-means:core",
    )


def _calculator_and_inputs() -> tuple[MatchupCalculator, MatchupInput, MatchupInput]:
    target_date = date(2026, 9, 20)
    created = datetime(2026, 9, 19, 18, 0, tzinfo=UTC)
    cutoff = datetime(2026, 9, 19, 17, 55, tzinfo=UTC)

    atp_foundational = _foundational(match_id="atp-target", event_date=target_date)
    atp_pair = _profile_pair(match_id="atp-target", event_date=target_date)
    atp_input = MatchupInput(
        prediction_id="pred-atp",
        match_id="atp-target",
        tour="ATP",
        player_a_id="player-a",
        player_b_id="player-b",
        created_at=created,
        prediction_cutoff_at=cutoff,
        foundational=atp_foundational,
        profile_pair=atp_pair,
        source_manifest_hashes=("a" * 64,),
    )
    atp_target = build_genome_vector(atp_pair, atp_foundational)
    atp_bank = _historical_bank(atp_target)

    wta_foundational = _foundational(match_id="wta-target", event_date=target_date)
    wta_input = MatchupInput(
        prediction_id="pred-wta",
        match_id="wta-target",
        tour="WTA",
        player_a_id="player-a",
        player_b_id="player-b",
        created_at=created,
        prediction_cutoff_at=cutoff,
        foundational=wta_foundational,
        serve_return=_serve_return(match_id="wta-target", event_date=target_date),
        source_manifest_hashes=("b" * 64,),
        best_of=3,
    )
    wta_target = _wta_target(wta_input)
    wta_bank = _historical_bank(wta_target, include_future=True)

    atp_artifact = TourProductionArtifact(
        tour="ATP",
        canonical_content_sha256="1" * 64,
        eligible_training_n=70000,
        core=_core_artifact(strict_a_features("ATP")),
        alignment_meta=_logistic_artifact(
            ("core_probability_favorite_logit", "neighbor_residual_k100"),
            (1.0, 0.5),
        ),
        neighbor_bank=_bank_artifact(
            tour="ATP",
            feature_names=atp_target.feature_names,
            row_count=len(atp_bank),
        ),
        wta_pointsim_meta=None,
        wta_elo_diagnostic=None,
        wta_a_plus_b_diagnostic=None,
        atp_conditioned_unfamiliarity=ConditionedUnfamiliarityArtifact(
            input_names=("core_confidence", "core_confidence_squared", "log_pool_size"),
            training_n=4000,
            coefficients=(0.0, 0.0, 0.0),
            intercept=0.0,
            residual_sd=1.0,
        ),
    )
    wta_artifact = TourProductionArtifact(
        tour="WTA",
        canonical_content_sha256="2" * 64,
        eligible_training_n=65000,
        core=_core_artifact(strict_a_features("WTA")),
        alignment_meta=_logistic_artifact(
            ("core_probability_favorite_logit", "neighbor_residual_k100"),
            (1.0, 0.5),
        ),
        neighbor_bank=_bank_artifact(
            tour="WTA",
            feature_names=wta_target.feature_names,
            row_count=len(wta_bank),
        ),
        wta_pointsim_meta=_logistic_artifact(
            ("alignment_probability_a_logit", "pointsim_probability_a_logit"),
            (0.8, 0.2),
        ),
        wta_elo_diagnostic=_core_artifact(("elo_logit",), elo_weight=0.5),
        wta_a_plus_b_diagnostic=_core_artifact(
            a_plus_b_features("WTA"),
            elo_weight=1.5,
        ),
        atp_conditioned_unfamiliarity=None,
    )
    bundle = IndependentProductionBundle(
        model_version=MODEL_VERSION,
        architecture_hash=architecture_hash(),
        production_version="TGE-Independent-v1-production-1",
        development_end_year=2025,
        source_repo="test/source",
        source_commit="deadbeef",
        atp=atp_artifact,
        wta=wta_artifact,
        artifact_sha256="f" * 64,
    )
    return (
        MatchupCalculator(
            bundle,
            atp_neighbor_bank=atp_bank,
            wta_neighbor_bank=wta_bank,
        ),
        atp_input,
        wta_input,
    )


def test_fair_decimal_odds_are_model_derived_prices() -> None:
    prices = fair_decimal_odds(0.625, 0.375)
    assert prices.player_a == pytest.approx(1.6)
    assert prices.player_b == pytest.approx(2.6666666667)


def test_atp_calculator_uses_frozen_alignment_and_diagnostics() -> None:
    calculator, atp_input, _ = _calculator_and_inputs()
    result = calculator.calculate(atp_input)

    assert result.prediction.p_player_a + result.prediction.p_player_b == pytest.approx(1.0)
    assert result.prediction.component_probabilities["strict_core_v1"] > 0.5
    assert (
        result.prediction.component_probabilities["full_genome_historical_alignment_k100"]
        == pytest.approx(result.prediction.p_player_a)
    )
    assert result.prediction.diagnostics["historical_neighbor_pool_size"] == 100
    assert result.prediction.diagnostics["historical_neighbor_k"] == 100
    assert result.prediction.diagnostics["conditioned_genome_unfamiliarity"] is not None
    assert result.prediction.diagnostics["hard_pass_policy_promoted"] is False
    assert result.prediction.reason_codes == ("NO_HARD_PASS_POLICY",)
    assert result.assessment_status == "DIAGNOSTIC_ONLY_NO_HARD_PASS"
    assert result.fair_decimal_odds.player_a == pytest.approx(
        1.0 / result.prediction.p_player_a
    )


def test_wta_calculator_routes_pointsim_only_through_frozen_meta_mapping() -> None:
    calculator, _, wta_input = _calculator_and_inputs()
    result = calculator.calculate(wta_input)
    components = result.prediction.component_probabilities

    raw_pointsim = point_sim_match_probability(0.66, 0.62, best_of=3)
    assert components["pointsim_conditional_meta_input"] == pytest.approx(raw_pointsim)
    alignment = components["strict_core_geometry_historical_alignment_k100"]
    expected_final = standardized_logistic_probability(
        (
            __import__("math").log(alignment / (1.0 - alignment)),
            __import__("math").log(raw_pointsim / (1.0 - raw_pointsim)),
        ),
        calculator.bundle.wta.wta_pointsim_meta,
    )
    assert result.prediction.p_player_a == pytest.approx(expected_final)
    assert components["pointsim_conditional_meta_final"] == pytest.approx(expected_final)
    assert result.prediction.diagnostics["historical_neighbor_pool_size"] == 100
    assert result.prediction.diagnostics["model_disagreement"] > 0.0
    assert result.prediction.diagnostics["hard_pass_policy_promoted"] is False


def test_terminal_bundle_refuses_in_development_historical_replay() -> None:
    calculator, _, wta_input = _calculator_and_inputs()
    historical_foundational = replace(
        wta_input.foundational,
        event_date=date(2025, 6, 1),
    )
    historical_serve = replace(
        wta_input.serve_return,
        event_date=date(2025, 6, 1),
    )
    historical_input = replace(
        wta_input,
        foundational=historical_foundational,
        serve_return=historical_serve,
    )
    with pytest.raises(ValueError, match="chronological replay engine"):
        calculator.calculate(historical_input)


def test_calculator_output_keeps_market_fields_outside_independent_prediction() -> None:
    calculator, atp_input, _ = _calculator_and_inputs()
    result = calculator.calculate(atp_input)
    independent_payload = result.prediction.to_dict()

    assert "fair_decimal_odds" not in independent_payload
    assert "market" not in independent_payload
    assert "edge" not in independent_payload
    assert result.to_dict()["fair_decimal_odds"]["player_a"] is not None
