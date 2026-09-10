from __future__ import annotations

import math
import random

import pytest

import tennis_genome.experiments.market_edge as market_edge
from tennis_genome.evaluation.multiple_testing import holm_adjust
from tennis_genome.experiments.market_edge import (
    MarketSignalRow,
    generate_market_edge_predictions,
    run_market_edge_claim,
)


def _synthetic_rows(
    *,
    years: range = range(2018, 2026),
    rows_per_year: int = 120,
    seed: int = 7,
) -> list[MarketSignalRow]:
    rng = random.Random(seed)
    rows: list[MarketSignalRow] = []
    for year in years:
        for index in range(rows_per_year):
            market_probability = 0.25 + 0.50 * rng.random()
            signal = rng.gauss(0.0, 1.0)
            true_logit = math.log(market_probability / (1.0 - market_probability))
            true_probability = 1.0 / (1.0 + math.exp(-(true_logit + 0.28 * signal)))
            outcome = rng.random() < true_probability
            rows.append(
                MarketSignalRow(
                    match_id=f"{year}-{index:04d}",
                    tour="ATP",
                    year=year,
                    outcome_a=outcome,
                    market_probability_a=market_probability,
                    signal=signal,
                )
            )
    return rows


def test_market_edge_predictions_use_only_earlier_years() -> None:
    rows = _synthetic_rows()
    predictions = generate_market_edge_predictions(
        rows,
        signal_name="profile_gap",
        min_prior_rows=200,
    )
    assert predictions
    assert all(row.train_n >= 200 for row in predictions)
    for prediction in predictions:
        expected_train_n = sum(row.year < prediction.year for row in rows)
        assert prediction.train_n == expected_train_n


def test_current_year_outcome_mutation_cannot_change_current_year_predictions() -> None:
    rows = _synthetic_rows()
    baseline = generate_market_edge_predictions(
        rows,
        signal_name="profile_gap",
        min_prior_rows=200,
    )
    target_year = 2023
    mutated = [
        MarketSignalRow(
            match_id=row.match_id,
            tour=row.tour,
            year=row.year,
            outcome_a=(not row.outcome_a) if row.year == target_year else row.outcome_a,
            market_probability_a=row.market_probability_a,
            signal=row.signal,
        )
        for row in rows
    ]
    changed = generate_market_edge_predictions(
        mutated,
        signal_name="profile_gap",
        min_prior_rows=200,
    )
    base_year = {row.match_id: row for row in baseline if row.year == target_year}
    changed_year = {row.match_id: row for row in changed if row.year == target_year}
    assert base_year.keys() == changed_year.keys()
    for match_id in base_year:
        assert changed_year[match_id].control_probability_a == pytest.approx(
            base_year[match_id].control_probability_a
        )
        assert changed_year[match_id].challenger_probability_a == pytest.approx(
            base_year[match_id].challenger_probability_a
        )
        assert changed_year[match_id].fit_beta == pytest.approx(base_year[match_id].fit_beta)


def test_appending_future_year_cannot_change_earlier_predictions() -> None:
    rows = _synthetic_rows(years=range(2018, 2025))
    initial = generate_market_edge_predictions(
        rows,
        signal_name="genome",
        min_prior_rows=200,
    )
    extended_rows = rows + _synthetic_rows(
        years=range(2025, 2026),
        seed=99,
    )
    extended = generate_market_edge_predictions(
        extended_rows,
        signal_name="genome",
        min_prior_rows=200,
    )
    before = {row.match_id: row for row in initial}
    after = {row.match_id: row for row in extended if row.match_id in before}
    assert before.keys() == after.keys()
    for match_id in before:
        assert after[match_id].control_probability_a == pytest.approx(
            before[match_id].control_probability_a
        )
        assert after[match_id].challenger_probability_a == pytest.approx(
            before[match_id].challenger_probability_a
        )


def test_a_b_reversal_complements_market_edge_predictions() -> None:
    rows = _synthetic_rows()
    direct = generate_market_edge_predictions(
        rows,
        signal_name="profile_gap",
        min_prior_rows=200,
    )
    reversed_rows = [
        MarketSignalRow(
            match_id=row.match_id,
            tour=row.tour,
            year=row.year,
            outcome_a=not row.outcome_a,
            market_probability_a=1.0 - row.market_probability_a,
            signal=-row.signal,
        )
        for row in rows
    ]
    reversed_predictions = generate_market_edge_predictions(
        reversed_rows,
        signal_name="profile_gap",
        min_prior_rows=200,
    )
    direct_by_id = {row.match_id: row for row in direct}
    reverse_by_id = {row.match_id: row for row in reversed_predictions}
    for match_id in direct_by_id:
        assert reverse_by_id[match_id].control_probability_a == pytest.approx(
            1.0 - direct_by_id[match_id].control_probability_a,
            abs=1e-9,
        )
        assert reverse_by_id[match_id].challenger_probability_a == pytest.approx(
            1.0 - direct_by_id[match_id].challenger_probability_a,
            abs=1e-9,
        )


def test_synthetic_signal_can_beat_market_recalibration_control(monkeypatch) -> None:
    monkeypatch.setattr(market_edge, "_BOOTSTRAP_RESAMPLES", 250)
    monkeypatch.setattr(market_edge, "_PERMUTATION_RESAMPLES", 500)
    report = run_market_edge_claim(
        _synthetic_rows(rows_per_year=160),
        signal_name="profile_gap",
        min_prior_rows=250,
    )
    assert report.comparison.brier_improvement_vs_control > 0.0
    assert report.comparison.log_loss_improvement_vs_control > 0.0
    assert report.prediction_n > 0
    assert report.mcnemar.discordant_pairs >= 0


def test_holm_adjustment_is_step_down_and_order_independent() -> None:
    first = holm_adjust({"a": 0.01, "b": 0.04, "c": 0.03, "d": 0.20})
    second = holm_adjust({"d": 0.20, "c": 0.03, "a": 0.01, "b": 0.04})
    assert {key: value.adjusted_p_value for key, value in first.items()} == {
        key: value.adjusted_p_value for key, value in second.items()
    }
    assert first["a"].adjusted_p_value == pytest.approx(0.04)
    assert first["c"].adjusted_p_value == pytest.approx(0.09)
    assert first["b"].adjusted_p_value == pytest.approx(0.09)
    assert first["d"].adjusted_p_value == pytest.approx(0.20)


def test_market_edge_rejects_duplicate_match_ids() -> None:
    row = _synthetic_rows(years=range(2018, 2019), rows_per_year=1)[0]
    with pytest.raises(ValueError, match="duplicate match_id"):
        generate_market_edge_predictions(
            [row, row],
            signal_name="profile_gap",
            min_prior_rows=1,
        )
