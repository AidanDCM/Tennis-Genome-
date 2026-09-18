from __future__ import annotations

from datetime import date

import pytest

from tennis_genome.evaluation.validation import (
    ValidationObservation,
    build_paired_model_comparison,
    build_validation_report,
)


def _rows(model_id: str = "MODEL-A") -> list[ValidationObservation]:
    return [
        ValidationObservation(
            model_id=model_id,
            match_id="m1",
            event_date=date(2026, 8, 1),
            probability_a=0.80,
            outcome_a_won=True,
            component_probabilities={"core": 0.75, "sim": 0.82},
            tags=("DEEP_HISTORY",),
        ),
        ValidationObservation(
            model_id=model_id,
            match_id="m2",
            event_date=date(2026, 8, 2),
            probability_a=0.70,
            outcome_a_won=True,
            component_probabilities={"core": 0.66, "sim": 0.78},
            tags=("DEEP_HISTORY", "HIGH_DISAGREEMENT"),
        ),
        ValidationObservation(
            model_id=model_id,
            match_id="m3",
            event_date=date(2026, 9, 1),
            probability_a=0.65,
            outcome_a_won=False,
            component_probabilities={"core": 0.55, "sim": 0.70},
            tags=("LOW_HISTORY", "HIGH_DISAGREEMENT"),
        ),
        ValidationObservation(
            model_id=model_id,
            match_id="m4",
            event_date=date(2026, 9, 2),
            probability_a=0.40,
            outcome_a_won=False,
            component_probabilities={"core": 0.42, "sim": 0.38},
            tags=("LOW_HISTORY",),
        ),
        ValidationObservation(
            model_id=model_id,
            match_id="m5",
            event_date=date(2026, 9, 3),
            probability_a=0.30,
            outcome_a_won=False,
            component_probabilities={"core": 0.34, "sim": 0.25},
        ),
        ValidationObservation(
            model_id=model_id,
            match_id="m6",
            event_date=date(2026, 9, 4),
            probability_a=0.20,
            outcome_a_won=True,
            component_probabilities={"core": 0.30, "sim": 0.18},
        ),
    ]


def test_validation_report_contains_full_probability_quality_contract() -> None:
    report = build_validation_report(_rows(), population_size=10, n_bins=5)

    assert report["model_id"] == "MODEL-A"
    assert report["population_size"] == 10
    assert report["prediction_count"] == 6
    assert report["abstention_count"] == 4
    assert report["coverage"] == pytest.approx(0.6)

    overall = report["overall"]
    for field in (
        "accuracy",
        "accuracy_wilson_95_low",
        "accuracy_wilson_95_high",
        "brier",
        "brier_skill_vs_50",
        "log_loss",
        "log_loss_skill_vs_50",
        "expected_calibration_error",
        "maximum_calibration_error",
        "calibration_intercept",
        "calibration_slope",
        "mean_confidence",
        "high_confidence_65_miss_rate",
        "high_confidence_75_miss_rate",
    ):
        assert field in overall

    assert len(report["reliability_table"]) > 0
    assert len(report["confidence_buckets"]) > 0
    assert [row["target_coverage"] for row in report["selective_coverage_curve"]] == [
        1.0,
        0.9,
        0.75,
        0.5,
        0.25,
        0.1,
    ]
    assert {row["month"] for row in report["monthly_slices"]} == {
        "2026-08",
        "2026-09",
    }
    assert {row["tag"] for row in report["tag_slices"]} == {
        "DEEP_HISTORY",
        "HIGH_DISAGREEMENT",
        "LOW_HISTORY",
    }
    assert report["component_disagreement"]["n"] == 6


def test_validation_report_rejects_duplicate_match_ids_and_mixed_models() -> None:
    rows = _rows()
    with pytest.raises(ValueError, match="unique match_id"):
        build_validation_report([rows[0], rows[0]])

    mixed = [rows[0], ValidationObservation(**{**rows[1].__dict__, "model_id": "OTHER"})]
    with pytest.raises(ValueError, match="exactly one model_id"):
        build_validation_report(mixed)


def test_paired_comparison_requires_same_matches_and_reports_metric_deltas() -> None:
    baseline = _rows("BASE")
    candidate = [
        ValidationObservation(
            model_id="CAND",
            match_id=row.match_id,
            event_date=row.event_date,
            probability_a=0.5 + (row.probability_a - 0.5) * 0.5,
            outcome_a_won=row.outcome_a_won,
            component_probabilities=row.component_probabilities,
            tags=row.tags,
        )
        for row in baseline
    ]

    comparison = build_paired_model_comparison(baseline, candidate, n_bins=5)

    assert comparison["baseline_model_id"] == "BASE"
    assert comparison["candidate_model_id"] == "CAND"
    assert comparison["n"] == len(baseline)
    assert "delta_brier_candidate_minus_baseline" in comparison
    assert "delta_log_loss_candidate_minus_baseline" in comparison
    assert "delta_ece_candidate_minus_baseline" in comparison
    assert 0.0 <= comparison["fraction_matches_candidate_lower_brier"] <= 1.0

    with pytest.raises(ValueError, match="identical match populations"):
        build_paired_model_comparison(baseline, candidate[:-1])


def test_degenerate_calibration_fit_is_reported_as_unavailable_not_fabricated() -> None:
    rows = [
        ValidationObservation(
            model_id="DEGENERATE",
            match_id=f"m{index}",
            probability_a=0.7,
            outcome_a_won=True,
        )
        for index in range(4)
    ]

    report = build_validation_report(rows)

    assert report["overall"]["calibration_intercept"] is None
    assert report["overall"]["calibration_slope"] is None


def test_observation_validates_probability_and_tag_uniqueness() -> None:
    with pytest.raises(ValueError, match="probability_a"):
        ValidationObservation(
            model_id="M",
            match_id="m",
            probability_a=1.1,
            outcome_a_won=True,
        )

    with pytest.raises(ValueError, match="tags must be unique"):
        ValidationObservation(
            model_id="M",
            match_id="m",
            probability_a=0.5,
            outcome_a_won=True,
            tags=("X", "X"),
        )
