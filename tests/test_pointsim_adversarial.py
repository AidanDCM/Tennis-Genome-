from __future__ import annotations

from dataclasses import replace

import pytest

from tennis_genome.experiments.pointsim_adversarial import (
    MatchedRow,
    _comparison,
    _gate,
    _walk_forward,
)


def _rows() -> list[MatchedRow]:
    rows: list[MatchedRow] = []
    for year in range(2000, 2006):
        for index in range(8):
            alignment = 0.65 if index % 2 == 0 else 0.35
            pointsim = 0.72 if index % 4 < 2 else 0.28
            outcome = bool((index + year) % 3)
            rows.append(
                MatchedRow(
                    match_id=f"{year}-{index}",
                    year=year,
                    outcome_a=outcome,
                    alignment_probability_a=alignment,
                    pointsim_probability_a=pointsim,
                )
            )
    return rows


def test_walk_forward_predictions_are_future_outcome_invariant() -> None:
    rows = _rows()
    original, _ = _walk_forward(rows, min_adversary_train_rows=8)

    changed = [
        replace(row, outcome_a=not row.outcome_a) if row.year == 2005 else row for row in rows
    ]
    mutated, _ = _walk_forward(changed, min_adversary_train_rows=8)

    original_2005 = {
        row.match_id: (
            row.alignment_recalibration_probability_a,
            row.alignment_plus_pointsim_probability_a,
        )
        for row in original
        if row.year == 2005
    }
    mutated_2005 = {
        row.match_id: (
            row.alignment_recalibration_probability_a,
            row.alignment_plus_pointsim_probability_a,
        )
        for row in mutated
        if row.year == 2005
    }
    assert original_2005 == mutated_2005


def test_walk_forward_rejects_nonpositive_training_gate() -> None:
    with pytest.raises(ValueError, match="positive"):
        _walk_forward(_rows(), min_adversary_train_rows=0)


def test_gate_requires_all_registered_conditions() -> None:
    predictions, yearly = _walk_forward(_rows(), min_adversary_train_rows=8)
    comparison = _comparison(predictions)
    gate = _gate(comparison, comparison, yearly)
    expected = (
        gate.aggregate_brier_better
        and gate.aggregate_log_loss_better
        and gate.at_least_60_percent_joint_year_wins
        and gate.recent_brier_not_worse is True
        and gate.recent_log_loss_not_worse is True
    )
    assert gate.passed is expected
