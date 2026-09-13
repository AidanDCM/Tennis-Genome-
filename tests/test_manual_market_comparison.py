from __future__ import annotations

from datetime import UTC, datetime

import pytest

from tennis_genome.calculator.market import compare_manual_decimal_odds
from tests.test_matchup_calculator import _calculator_and_inputs


def _compare(*, calculation):
    return compare_manual_decimal_odds(
        comparison_id="comparison-1",
        market_snapshot_id="manual-market-1",
        created_at=datetime(2026, 9, 19, 18, 2, tzinfo=UTC),
        observed_at=datetime(2026, 9, 19, 18, 1, tzinfo=UTC),
        calculation=calculation,
        decimal_odds_a=1.85,
        decimal_odds_b=2.05,
        selection_a_name="Player A",
        selection_b_name="Player B",
        bookmaker="MANUAL_TEST",
        commence_at=datetime(2026, 9, 20, 12, 0, tzinfo=UTC),
    )


def test_manual_odds_comparison_is_downstream_of_independent_prediction() -> None:
    calculator, atp_input, _ = _calculator_and_inputs()
    calculation = calculator.calculate(atp_input)
    independent_before = calculation.prediction.to_dict()

    comparison = _compare(calculation=calculation)

    assert calculation.prediction.to_dict() == independent_before
    assert calculation.player_a_id == atp_input.player_a_id
    assert calculation.player_b_id == atp_input.player_b_id
    assert comparison.prediction_id == calculation.prediction.prediction_id
    assert comparison.model_p_a == pytest.approx(calculation.prediction.p_player_a)
    assert comparison.novig_p_a + comparison.novig_p_b == pytest.approx(1.0)
    assert comparison.decision_eligible is True
    assert comparison.reason_codes == ()
