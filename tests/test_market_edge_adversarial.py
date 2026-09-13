from __future__ import annotations

import json
import math
import random
from dataclasses import replace
from pathlib import Path

import pytest

import tennis_genome.experiments.market_edge_adversarial as adversarial
from tennis_genome.experiments.market_edge_adv_family import (
    run_market_edge_adversarial_family,
)
from tennis_genome.experiments.market_edge_adv_inputs import (
    load_genome_core_signal,
    load_profile_gap_core_signal,
)
from tennis_genome.experiments.market_edge_adversarial import (
    MarketCoreSignalRow,
    generate_adversarial_predictions,
    run_market_edge_adversarial_claim,
)


def _sigmoid(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-value))


def _rows(*, tour: str = "ATP", signal_effect: float = 0.35) -> list[MarketCoreSignalRow]:
    rng = random.Random(6401 if tour == "ATP" else 6402)
    rows: list[MarketCoreSignalRow] = []
    for year in range(2018, 2026):
        for index in range(50):
            market_latent = -1.4 + 2.8 * ((index + 0.3 * (year - 2018)) % 50) / 49.0
            core_extra = 0.55 * math.sin(index * 0.41 + year)
            core_latent = 0.70 * market_latent + core_extra
            signal = math.cos(index * 0.29 + year * 0.17) + rng.gauss(0.0, 0.25)
            true_latent = 0.75 * market_latent + 0.45 * core_latent + signal_effect * signal
            outcome = rng.random() < _sigmoid(true_latent)
            rows.append(
                MarketCoreSignalRow(
                    match_id=f"{tour.lower()}-{year}-{index:03d}",
                    tour=tour,  # type: ignore[arg-type]
                    year=year,
                    outcome_a=outcome,
                    market_probability_a=_sigmoid(market_latent),
                    core_probability_a=_sigmoid(core_latent),
                    signal=signal,
                )
            )
    return rows


def test_same_year_outcomes_do_not_change_same_year_predictions() -> None:
    original = _rows()
    mutated = [
        replace(row, outcome_a=not row.outcome_a) if row.year == 2025 else row for row in original
    ]
    first = generate_adversarial_predictions(
        original,
        signal_name="profile_gap",
        min_prior_rows=100,
    )
    second = generate_adversarial_predictions(
        mutated,
        signal_name="profile_gap",
        min_prior_rows=100,
    )
    first_2025 = {row.match_id: row for row in first if row.year == 2025}
    second_2025 = {row.match_id: row for row in second if row.year == 2025}
    assert first_2025.keys() == second_2025.keys()
    for match_id in first_2025:
        left = first_2025[match_id]
        right = second_2025[match_id]
        assert left.market_only_probability_a == pytest.approx(right.market_only_probability_a)
        assert left.market_core_probability_a == pytest.approx(right.market_core_probability_a)
        assert left.challenger_probability_a == pytest.approx(right.challenger_probability_a)
        assert left.challenger_fit == right.challenger_fit


def test_trailing_three_year_window_uses_only_prior_three_calendar_years() -> None:
    predictions = generate_adversarial_predictions(
        _rows(),
        signal_name="genome",
        training_window="trailing_3y",
        min_prior_rows=100,
    )
    rows_2025 = [row for row in predictions if row.year == 2025]
    assert rows_2025
    fit = rows_2025[0].challenger_fit
    assert fit.train_start_year == 2022
    assert fit.train_end_year == 2024
    assert fit.train_n == 150


def test_rank_deficient_market_core_design_fails_closed() -> None:
    rows = []
    for year in range(2020, 2023):
        for index in range(50):
            probability = 0.25 + 0.5 * (index / 49.0)
            rows.append(
                MarketCoreSignalRow(
                    match_id=f"m-{year}-{index}",
                    tour="ATP",
                    year=year,
                    outcome_a=index % 2 == 0,
                    market_probability_a=probability,
                    core_probability_a=probability,
                    signal=float(index),
                )
            )
    with pytest.raises(ValueError, match="rank deficient"):
        generate_adversarial_predictions(
            rows,
            signal_name="profile_gap",
            min_prior_rows=50,
        )


def test_post_2025_row_is_rejected() -> None:
    with pytest.raises(ValueError, match="2025"):
        MarketCoreSignalRow(
            match_id="future",
            tour="ATP",
            year=2026,
            outcome_a=True,
            market_probability_a=0.55,
            core_probability_a=0.57,
            signal=0.1,
        )


def test_claim_reports_market_core_as_primary_control(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(adversarial, "_BOOTSTRAP_RESAMPLES", 400)
    monkeypatch.setattr(adversarial, "_PERMUTATION_RESAMPLES", 800)
    report = run_market_edge_adversarial_claim(
        _rows(signal_effect=0.55),
        signal_name="profile_gap",
        min_prior_rows=100,
    )
    assert report.primary.prediction_n > 0
    assert report.primary.comparison.market_core_control.n == report.primary.prediction_n
    assert report.primary.comparison.signal_challenger.n == report.primary.prediction_n
    assert report.primary.training_window == "expanding"
    assert report.trailing_3y_robustness is not None
    assert report.trailing_3y_robustness.training_window == "trailing_3y"
    assert report.promotion_diagnostics.yearly_count == len(report.primary.yearly)


def test_frozen_four_claim_family_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(adversarial, "_BOOTSTRAP_RESAMPLES", 200)
    monkeypatch.setattr(adversarial, "_PERMUTATION_RESAMPLES", 400)
    with pytest.raises(ValueError, match="four-claim family"):
        run_market_edge_adversarial_family(
            {("ATP", "profile_gap"): _rows(tour="ATP")},
            min_prior_rows=100,
        )

    family = run_market_edge_adversarial_family(
        {
            ("ATP", "profile_gap"): _rows(tour="ATP", signal_effect=0.5),
            ("WTA", "profile_gap"): _rows(tour="WTA", signal_effect=0.5),
            ("ATP", "genome"): _rows(tour="ATP", signal_effect=0.5),
            ("WTA", "genome"): _rows(tour="WTA", signal_effect=0.5),
        },
        min_prior_rows=100,
    )
    assert family.experiment_id == "MARKET-EDGE-ADV-001"
    assert len(family.claims) == 4
    assert len(family.decisions) == 4
    assert {decision.label for decision in family.decisions} == {
        "ATP:profile_gap",
        "WTA:profile_gap",
        "ATP:genome",
        "WTA:genome",
    }


def test_profile_loader_uses_frozen_strict_core_probability(tmp_path: Path) -> None:
    path = tmp_path / "profile.json"
    path.write_text(
        json.dumps(
            {
                "experiment_id": "PROFILE-GAP-001",
                "tour": "ATP",
                "predictions": [
                    {
                        "match_id": "m1",
                        "outcome_a": False,
                        "strict_core_probability": 0.63,
                        "profile_gap_match": -0.22,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    values = load_profile_gap_core_signal(path, tour="ATP")
    assert values["m1"].core_probability_a == pytest.approx(0.63)
    assert values["m1"].signal == pytest.approx(-0.22)


def test_genome_loader_uses_tour_approved_signal_field(tmp_path: Path) -> None:
    atp_path = tmp_path / "atp.json"
    atp_path.write_text(
        json.dumps(
            {
                "experiment_id": "GENOME-ADV-001",
                "tour": "ATP",
                "predictions": [
                    {
                        "match_id": "a",
                        "core_probability_a": 0.58,
                        "full_neighbor_residual": 0.12,
                        "core_neighbor_residual": 9.0,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    wta_path = tmp_path / "wta.json"
    wta_path.write_text(
        json.dumps(
            {
                "experiment_id": "GENOME-ADV-001",
                "tour": "WTA",
                "predictions": [
                    {
                        "match_id": "w",
                        "core_probability_a": 0.52,
                        "full_neighbor_residual": 9.0,
                        "core_neighbor_residual": -0.08,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    assert load_genome_core_signal(atp_path, tour="ATP")["a"].signal == pytest.approx(0.12)
    assert load_genome_core_signal(wta_path, tour="WTA")["w"].signal == pytest.approx(-0.08)
