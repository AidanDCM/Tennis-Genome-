from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest

from tennis_genome.experiments.fusion_calibration import (
    BaseProbabilityRow,
    FusionPredictionRow,
    _alignment_probability,
    _calibration_rows_for_candidate,
    _fixed_equal_logit_blend,
    _fusion_oof_from_base_rows,
    run_fusion_calibration,
)
from tennis_genome.experiments.genome_adversarial_controls import PredictionRow
from tests.factories import make_match


def _adversarial_prediction() -> PredictionRow:
    return PredictionRow(
        match_id="m",
        year=2025,
        outcome_a=True,
        core_probability_a=0.61,
        calibration_control_probability_a=0.60,
        probability_neighborhood_probability_a=0.62,
        core_neighborhood_probability_a=0.63,
        full_genome_probability_a=0.67,
        probability_neighbor_residual=0.01,
        core_neighbor_residual=0.02,
        full_neighbor_residual=0.03,
    )


def test_alignment_selection_is_tour_specific() -> None:
    row = _adversarial_prediction()
    assert _alignment_probability(row, tour="ATP") == pytest.approx(0.67)
    assert _alignment_probability(row, tour="WTA") == pytest.approx(0.63)


def _base_rows() -> list[BaseProbabilityRow]:
    rows: list[BaseProbabilityRow] = []
    for year in range(2010, 2016):
        for index in range(180):
            latent = ((index % 31) - 15) / 40.0
            core = min(max(0.5 + 0.28 * latent, 0.08), 0.92)
            correction = 0.025 if index % 4 in (0, 1) else -0.012
            alignment = min(max(core + correction, 0.05), 0.95)
            threshold = int(round(alignment * 20))
            outcome = ((index * 7 + year * 3) % 20) < threshold
            rows.append(
                BaseProbabilityRow(
                    match_id=f"m-{year}-{index:03d}",
                    year=year,
                    outcome_a=outcome,
                    core_control_probability_a=core,
                    alignment_probability_a=alignment,
                )
            )
    return rows


def test_fusion_never_uses_target_year_outcomes_to_predict_target_year() -> None:
    original = _base_rows()
    altered = [
        replace(row, outcome_a=not row.outcome_a) if row.year == 2015 else row
        for row in original
    ]

    first, _ = _fusion_oof_from_base_rows(original, min_fusion_train_rows=100)
    second, _ = _fusion_oof_from_base_rows(altered, min_fusion_train_rows=100)

    first_2015 = {row.match_id: row for row in first if row.year == 2015}
    second_2015 = {row.match_id: row for row in second if row.year == 2015}
    assert first_2015.keys() == second_2015.keys()
    for match_id in first_2015:
        assert first_2015[match_id].f1_alignment_recalibration == pytest.approx(
            second_2015[match_id].f1_alignment_recalibration
        )
        assert first_2015[match_id].f3_two_view_fusion == pytest.approx(
            second_2015[match_id].f3_two_view_fusion
        )


def _fusion_rows() -> list[FusionPredictionRow]:
    base, _ = _fusion_oof_from_base_rows(_base_rows(), min_fusion_train_rows=100)
    return base


def test_nested_calibrator_never_uses_target_year_outcomes() -> None:
    rows = _fusion_rows()
    target_year = max(row.year for row in rows)
    altered = [
        replace(row, outcome_a=not row.outcome_a) if row.year == target_year else row
        for row in rows
    ]

    first, _ = _calibration_rows_for_candidate(
        rows,
        candidate="f3",
        min_calibration_rows=100,
    )
    second, _ = _calibration_rows_for_candidate(
        altered,
        candidate="f3",
        min_calibration_rows=100,
    )

    for calibrator in first:
        first_target = {
            row.match_id: probability
            for row, probability in first[calibrator]
            if row.year == target_year
        }
        second_target = {
            row.match_id: probability
            for row, probability in second[calibrator]
            if row.year == target_year
        }
        assert first_target.keys() == second_target.keys()
        for match_id in first_target:
            assert first_target[match_id] == pytest.approx(second_target[match_id])


def test_equal_logit_blend_is_player_order_symmetric() -> None:
    forward = _fixed_equal_logit_blend(0.72, 0.64)
    reversed_probability = _fixed_equal_logit_blend(0.28, 0.36)
    assert forward == pytest.approx(1.0 - reversed_probability)


def test_fitted_fusion_is_player_order_symmetric() -> None:
    rows = _base_rows()
    mirrored = [
        BaseProbabilityRow(
            match_id=row.match_id,
            year=row.year,
            outcome_a=not row.outcome_a,
            core_control_probability_a=1.0 - row.core_control_probability_a,
            alignment_probability_a=1.0 - row.alignment_probability_a,
        )
        for row in rows
    ]

    forward, _ = _fusion_oof_from_base_rows(rows, min_fusion_train_rows=100)
    reverse, _ = _fusion_oof_from_base_rows(mirrored, min_fusion_train_rows=100)
    reverse_by_id = {row.match_id: row for row in reverse}
    for row in forward:
        other = reverse_by_id[row.match_id]
        assert row.f1_alignment_recalibration == pytest.approx(
            1.0 - other.f1_alignment_recalibration,
            abs=1e-9,
        )
        assert row.f3_two_view_fusion == pytest.approx(
            1.0 - other.f3_two_view_fusion,
            abs=1e-9,
        )


def test_fusion_calibration_rejects_post_2025_selected_tour_data() -> None:
    match = make_match(
        match_id="future",
        event_date=date(2026, 1, 1),
        player_a_id="a",
        player_b_id="b",
        a_won=True,
    )
    with pytest.raises(ValueError, match="post-2025"):
        run_fusion_calibration(
            [match],
            tour="ATP",
            min_core_train_matches=1,
            min_neighbor_pool=1,
            min_meta_train_rows=1,
            min_fusion_train_rows=1,
            min_calibration_rows=1,
        )
