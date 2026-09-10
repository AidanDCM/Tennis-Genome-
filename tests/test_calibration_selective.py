from __future__ import annotations

from tennis_genome.experiments.calibration_selective import (
    CALIBRATOR_NAMES,
    COVERAGE_LEVELS,
    OOFPrediction,
    _CalibratedRow,
    calibrate_oof_predictions,
    disagreement_report,
    run_calibration_selective_lab,
    selective_curve,
)
from tests.test_family_lab import _match


def _oof_row(index: int, year: int) -> OOFPrediction:
    outcome = index % 3 != 0
    strict = 0.56 + 0.012 * (index % 10)
    if not outcome:
        strict = 1.0 - strict
    elo = 0.5 + (strict - 0.5) * 0.72
    diagnostic = min(max(strict + (0.01 if index % 2 else -0.015), 0.02), 0.98)
    return OOFPrediction(
        match_id=f"oof-{year}-{index}",
        year=year,
        outcome_a=outcome,
        elo_probability=elo,
        strict_probability=strict,
        a_plus_b_probability=diagnostic,
    )


def _calibrated_row(index: int, probability: float) -> _CalibratedRow:
    oof = OOFPrediction(
        match_id=f"m-{index}",
        year=2025,
        outcome_a=(probability >= 0.5),
        elo_probability=0.5 + (probability - 0.5) * 0.7,
        strict_probability=probability,
        a_plus_b_probability=min(max(probability + (index % 5) * 0.005, 0.01), 0.99),
    )
    return _CalibratedRow(
        oof=oof,
        probabilities={name: probability for name in CALIBRATOR_NAMES},
    )


def test_nested_calibration_uses_only_prior_oof_years() -> None:
    oof = [
        _oof_row(index, year)
        for year in (2022, 2023, 2024)
        for index in range(12)
    ]

    rows, yearly = calibrate_oof_predictions(
        oof,
        min_calibration_predictions=10,
    )

    assert {row.oof.year for row in rows} == {2023, 2024}
    assert [item.year for item in yearly["platt"]] == [2023, 2024]
    assert [item.calibration_train_n for item in yearly["platt"]] == [12, 24]
    assert all(item.n == 12 for item in yearly["platt"])


def test_selective_curve_uses_registered_coverages_and_descending_confidence() -> None:
    probabilities = [
        0.51,
        0.49,
        0.53,
        0.47,
        0.56,
        0.44,
        0.60,
        0.40,
        0.65,
        0.35,
        0.70,
        0.30,
        0.75,
        0.25,
        0.80,
        0.20,
        0.85,
        0.15,
        0.90,
        0.10,
    ]
    rows = [_calibrated_row(index, value) for index, value in enumerate(probabilities)]

    result = selective_curve(rows, calibrator="identity")

    assert tuple(item.requested_coverage for item in result.coverage) == COVERAGE_LEVELS
    assert [item.n for item in result.coverage] == [20, 15, 10, 5, 2, 1]
    assert result.coverage[-1].minimum_confidence >= result.coverage[0].minimum_confidence


def test_disagreement_report_builds_equal_count_quintiles_and_joint_cells() -> None:
    rows: list[_CalibratedRow] = []
    for index in range(25):
        strict = 0.55 + 0.01 * (index % 10)
        elo = strict - 0.002 * index
        diagnostic = strict + 0.0025 * index
        oof = OOFPrediction(
            match_id=f"d-{index}",
            year=2025,
            outcome_a=index % 3 != 0,
            elo_probability=max(0.01, elo),
            strict_probability=strict,
            a_plus_b_probability=min(0.99, diagnostic),
        )
        rows.append(
            _CalibratedRow(
                oof=oof,
                probabilities={name: strict for name in CALIBRATOR_NAMES},
            )
        )

    report = disagreement_report(rows)

    assert len(report.by_disagreement_quintile) == 5
    assert sum(item.n for item in report.by_disagreement_quintile) == 25
    assert sum(item.n for item in report.confidence_x_disagreement) == 25
    assert (
        report.by_disagreement_quintile[-1].mean_disagreement
        > report.by_disagreement_quintile[0].mean_disagreement
    )


def test_full_lab_produces_all_calibrators_and_never_uses_2026() -> None:
    matches = []
    for year in range(2019, 2026):
        for index in range(12):
            matches.append(_match(index, year, a_won=(index + year) % 3 != 0))

    report = run_calibration_selective_lab(
        matches,
        tour="ATP",
        min_train_matches=10,
        min_calibration_predictions=10,
    )

    assert {item.name for item in report.calibrators} == set(CALIBRATOR_NAMES)
    assert {item.calibrator for item in report.selective_prediction} == set(
        CALIBRATOR_NAMES
    )
    assert all(
        len(item.coverage) == len(COVERAGE_LEVELS)
        for item in report.selective_prediction
    )
    assert max(report.base_oof_years) == 2025
    assert max(report.calibration_years) == 2025
    assert 2026 not in report.base_oof_years
    assert report.calibration_population_n > 0
