from __future__ import annotations

from datetime import date

import pytest

from tennis_genome.data.canonical import HistoricalMatch, MatchOutcome, PreMatchState
from tennis_genome.experiments import uncertainty_ood
from tennis_genome.features.genome import GENOME_VERSION, GenomeVector


def _genome(match_id: str, *, tour: str = "ATP") -> GenomeVector:
    return GenomeVector(
        match_id=match_id,
        event_date=date(2020, 1, 1),
        tour=tour,
        player_a_id="a",
        player_b_id="b",
        orientation_sign=1,
        feature_names=(
            "core::elo_logit",
            "core::form_result_90_diff",
            "profile_mean::elo_rating",
        ),
        values=(0.2, None, 1500.0),
        feature_version=GENOME_VERSION,
    )


def _base(
    match_id: str,
    year: int,
    *,
    confidence_probability: float,
) -> uncertainty_ood._BaseRow:
    genome = _genome(match_id)
    return uncertainty_ood._BaseRow(
        match_id=match_id,
        year=year,
        outcome_a=True,
        core_probability_a=confidence_probability,
        disagreement=0.03,
        alignment_vector=genome,
        min_prior_matches=25,
        min_prior_point_exposure=1000,
    )


def test_wta_alignment_uses_strict_core_only_but_atp_keeps_full_genome() -> None:
    genome = _genome("m")

    atp = uncertainty_ood._alignment_vector(genome, tour="ATP")
    wta = uncertainty_ood._alignment_vector(
        GenomeVector(
            **{
                **genome.__dict__,
                "tour": "WTA",
            }
        ),
        tour="WTA",
    )

    assert atp.feature_names == genome.feature_names
    assert wta.feature_names == (
        "core::elo_logit",
        "core::form_result_90_diff",
    )
    assert wta.values == (0.2, None)
    assert atp.missing_fraction == pytest.approx(1 / 3)
    assert wta.missing_fraction == pytest.approx(1 / 2)


def test_distance_conditioning_never_fits_target_year_distribution() -> None:
    prior = [
        uncertainty_ood._DistanceRow(
            base=_base(f"p-{index}", 2010 + index // 2, confidence_probability=0.6),
            raw_mean_distance_100=1.0 + 0.1 * index,
            historical_pool_size=1000 + 50 * index,
        )
        for index in range(4)
    ]
    target_a = uncertainty_ood._DistanceRow(
        base=_base("target-a", 2012, confidence_probability=0.7),
        raw_mean_distance_100=1.5,
        historical_pool_size=1200,
    )
    target_b = uncertainty_ood._DistanceRow(
        base=_base("target-b", 2012, confidence_probability=0.7),
        raw_mean_distance_100=1.6,
        historical_pool_size=1200,
    )

    first = uncertainty_ood._condition_distances(
        prior + [target_a, target_b],
        min_condition_train_rows=4,
    )
    altered = uncertainty_ood._condition_distances(
        prior
        + [
            target_a,
            uncertainty_ood._DistanceRow(
                base=target_b.base,
                raw_mean_distance_100=1_000_000.0,
                historical_pool_size=1200,
            ),
        ],
        min_condition_train_rows=4,
    )

    first_a = next(row for row in first if row.base.match_id == "target-a")
    altered_a = next(row for row in altered if row.base.match_id == "target-a")
    assert first_a.conditioned_unfamiliarity == pytest.approx(altered_a.conditioned_unfamiliarity)


def _synthetic_match(year: int, index: int, *, tour: str = "ATP") -> HistoricalMatch:
    surface = ("Hard", "Clay", "Grass")[index % 3]
    level = ("A", "G", "M")[index % 3]
    round_name = ("R32", "QF", "SF", "F")[index % 4]
    player_a = f"a-{year}-{index:03d}"
    player_b = f"b-{year}-{index:03d}"
    state = PreMatchState(
        match_id=f"m-{tour}-{year}-{index:03d}",
        tour=tour,
        event_date=date(year, 1 + (index % 12), 1),
        source_order=index,
        tournament_id=f"event-{year}-{index // 32}",
        tournament_name="Synthetic Event",
        tournament_level=level,
        surface=surface,
        round=round_name,
        best_of=5 if tour == "ATP" and index % 11 == 0 else 3,
        player_a_id=player_a,
        player_b_id=player_b,
        player_a_name=player_a,
        player_b_name=player_b,
        rank_a=1 + (index % 100),
        rank_b=1 + ((index * 7) % 100),
        rank_points_a=5000 - (index % 1000),
        rank_points_b=4500 - ((index * 3) % 1000),
        seed_a=(1 + index % 16) if index % 4 == 0 else None,
        seed_b=(1 + (index * 3) % 16) if index % 5 == 0 else None,
        entry_a="Q" if index % 17 == 0 else None,
        entry_b="WC" if index % 19 == 0 else None,
        hand_a="R",
        hand_b="L" if index % 5 == 0 else "R",
        height_cm_a=178 + (index % 15),
        height_cm_b=176 + ((index * 2) % 15),
        age_years_a=20.0 + (index % 15),
        age_years_b=21.0 + ((index * 3) % 15),
        ioc_a="USA",
        ioc_b="ESP",
    )
    return HistoricalMatch(
        pre_match=state,
        outcome=MatchOutcome(
            match_id=state.match_id,
            a_won=(index % 2 == 0),
            score="6-4 6-4",
            retirement=False,
            walkover=False,
        ),
        stats=None,
    )


def _history(*, tour: str = "ATP") -> list[HistoricalMatch]:
    return [
        _synthetic_match(year, index, tour=tour)
        for year in range(2010, 2017)
        for index in range(120)
    ]


def test_uncertainty_lab_produces_nested_oos_risk_predictions() -> None:
    report = uncertainty_ood.run_uncertainty_ood(
        _history(),
        tour="ATP",
        min_core_train_matches=100,
        min_neighbor_pool=100,
        min_condition_train_rows=100,
        min_risk_train_rows=100,
    )

    assert report.primary_k == 100
    assert report.alignment_representation == "full_genome"
    assert report.distance_population_n > report.conditioned_population_n
    assert report.conditioned_population_n > report.risk_population_n
    assert report.predictions
    assert min(row.year for row in report.predictions) >= 2014
    assert len(report.selective.coverage) == 6
    assert report.selective.coverage[0].requested_coverage == 1.0


def test_uncertainty_lab_rejects_spent_post_2025_data() -> None:
    matches = _history()
    matches.append(_synthetic_match(2026, 0))

    with pytest.raises(ValueError, match="post-2025"):
        uncertainty_ood.run_uncertainty_ood(
            matches,
            tour="ATP",
            min_core_train_matches=100,
            min_neighbor_pool=100,
            min_condition_train_rows=100,
            min_risk_train_rows=100,
        )
