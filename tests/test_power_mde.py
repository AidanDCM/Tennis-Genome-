from __future__ import annotations

import math

import pytest

from tennis_genome.experiments.power_mde import (
    PowerMdeRow,
    run_power_mde_claim,
)


def _row(
    match_id: str,
    *,
    year: int,
    probability: float,
    signal: float,
    tour: str = "ATP",
) -> PowerMdeRow:
    return PowerMdeRow(
        match_id=match_id,
        tour=tour,  # type: ignore[arg-type]
        year=year,
        market_probability_a=probability,
        signal=signal,
    )


def _balanced_training_rows(*, copies: int = 1, tour: str = "ATP") -> list[PowerMdeRow]:
    base = [
        (0.28, -1.4),
        (0.36, 0.2),
        (0.47, -0.4),
        (0.59, 1.1),
        (0.68, 0.5),
        (0.76, 1.7),
    ]
    rows: list[PowerMdeRow] = []
    for copy_index in range(copies):
        for index, (probability, signal) in enumerate(base):
            rows.append(
                _row(
                    f"train-{copy_index}-{index}",
                    year=2020,
                    probability=probability,
                    signal=signal,
                    tour=tour,
                )
            )
    rows.extend(
        [
            _row(
                f"eval-{index}",
                year=2021,
                probability=probability,
                signal=signal,
                tour=tour,
            )
            for index, (probability, signal) in enumerate(base[:3])
        ]
    )
    return rows


def test_power_mde_reports_positive_finite_resolution() -> None:
    report = run_power_mde_claim(
        _balanced_training_rows(),
        signal_name="profile_gap",
        min_prior_rows=6,
    )
    assert report.first_planned_evaluation_year == 2021
    assert report.last_planned_evaluation_year == 2021
    assert report.identifiable_year_count == 1
    plan = report.year_plans[0]
    assert plan.identifiable is True
    assert plan.training_n == 6
    assert plan.evaluation_n == 3
    assert plan.beta_se_null is not None and plan.beta_se_null > 0.0
    assert plan.mde_beta_80 is not None and plan.mde_beta_80 > 0.0
    assert plan.mde_beta_90 is not None and plan.mde_beta_90 > plan.mde_beta_80
    powers = [point.approximate_two_sided_power for point in plan.power_grid]
    assert powers == sorted(powers)
    assert all(0.0 <= value <= 1.0 for value in powers)
    shifts = {item.market_probability: item for item in plan.probability_shifts}
    assert shifts[0.50].shift_at_mde_80 > shifts[0.80].shift_at_mde_80 > 0.0


def test_doubling_identical_training_information_reduces_mde() -> None:
    small = run_power_mde_claim(
        _balanced_training_rows(copies=1),
        signal_name="profile_gap",
        min_prior_rows=6,
    ).year_plans[0]
    large = run_power_mde_claim(
        _balanced_training_rows(copies=2),
        signal_name="profile_gap",
        min_prior_rows=6,
    ).year_plans[0]
    assert small.mde_beta_80 is not None
    assert large.mde_beta_80 is not None
    assert large.training_n == 2 * small.training_n
    assert large.mde_beta_80 < small.mde_beta_80
    assert large.mde_beta_80 == pytest.approx(small.mde_beta_80 / math.sqrt(2.0))


def test_exact_market_signal_collinearity_is_non_identifiable() -> None:
    probabilities = (0.25, 0.32, 0.41, 0.56, 0.67, 0.78)
    rows = [
        _row(
            f"train-{index}",
            year=2020,
            probability=probability,
            signal=math.log(probability / (1.0 - probability)),
        )
        for index, probability in enumerate(probabilities)
    ]
    rows.append(_row("eval", year=2021, probability=0.52, signal=0.0))
    report = run_power_mde_claim(rows, signal_name="genome", min_prior_rows=6)
    plan = report.year_plans[0]
    assert plan.identifiable is False
    assert plan.beta_se_null is None
    assert plan.non_identifiable_reason is not None


def test_ab_reversal_preserves_beta_resolution() -> None:
    rows = _balanced_training_rows()
    reversed_rows = [
        PowerMdeRow(
            match_id=row.match_id,
            tour=row.tour,
            year=row.year,
            market_probability_a=1.0 - row.market_probability_a,
            signal=-row.signal,
        )
        for row in rows
    ]
    original = run_power_mde_claim(
        rows,
        signal_name="profile_gap",
        min_prior_rows=6,
    ).year_plans[0]
    reversed_plan = run_power_mde_claim(
        reversed_rows,
        signal_name="profile_gap",
        min_prior_rows=6,
    ).year_plans[0]
    assert original.beta_se_null == pytest.approx(reversed_plan.beta_se_null)
    assert original.mde_beta_80 == pytest.approx(reversed_plan.mde_beta_80)
    assert original.mde_beta_90 == pytest.approx(reversed_plan.mde_beta_90)


def test_power_mde_rejects_post_2025_rows() -> None:
    with pytest.raises(ValueError, match="frozen through 2025"):
        _row("future", year=2026, probability=0.55, signal=0.1)


def test_power_mde_rejects_duplicate_match_ids() -> None:
    rows = _balanced_training_rows()
    rows.append(rows[0])
    with pytest.raises(ValueError, match="duplicate match_id"):
        run_power_mde_claim(rows, signal_name="profile_gap", min_prior_rows=6)


def test_power_mde_requires_one_tour_per_claim() -> None:
    rows = _balanced_training_rows()
    rows[-1] = _row("wta-eval", year=2021, probability=0.55, signal=0.2, tour="WTA")
    with pytest.raises(ValueError, match="exactly one tour"):
        run_power_mde_claim(rows, signal_name="profile_gap", min_prior_rows=6)
