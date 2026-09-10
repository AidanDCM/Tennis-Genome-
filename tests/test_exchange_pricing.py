from __future__ import annotations

import math

import pytest

from tennis_genome.market.exchange_pricing import (
    commission_adjusted_breakeven_probability,
    exchange_clv,
    exchange_mid_implied_proportional_v1,
    isolated_back_expected_value,
)


def test_exchange_probability_is_symmetric_and_sums_to_one() -> None:
    direct = exchange_mid_implied_proportional_v1(
        back_a=1.80,
        lay_a=1.82,
        back_b=2.20,
        lay_b=2.24,
    )
    swapped = exchange_mid_implied_proportional_v1(
        back_a=2.20,
        lay_a=2.24,
        back_b=1.80,
        lay_b=1.82,
    )
    assert direct.probability_a + direct.probability_b == pytest.approx(1.0)
    assert swapped.probability_a == pytest.approx(direct.probability_b)
    assert swapped.probability_b == pytest.approx(direct.probability_a)
    assert direct.probability_a > 0.5


def test_exchange_probability_rejects_crossed_or_invalid_quotes() -> None:
    with pytest.raises(ValueError, match="back_a cannot exceed lay_a"):
        exchange_mid_implied_proportional_v1(
            back_a=1.90,
            lay_a=1.80,
            back_b=2.10,
            lay_b=2.20,
        )
    with pytest.raises(ValueError, match="greater than 1.0"):
        exchange_mid_implied_proportional_v1(
            back_a=1.0,
            lay_a=1.80,
            back_b=2.10,
            lay_b=2.20,
        )


def test_commission_lowers_ev_and_raises_breakeven_probability() -> None:
    ev_zero = isolated_back_expected_value(
        win_probability=0.60,
        decimal_odds=1.80,
        commission_fraction=0.0,
    )
    ev_five = isolated_back_expected_value(
        win_probability=0.60,
        decimal_odds=1.80,
        commission_fraction=0.05,
    )
    assert ev_five < ev_zero

    break_even_zero = commission_adjusted_breakeven_probability(
        decimal_odds=1.80,
        commission_fraction=0.0,
    )
    break_even_five = commission_adjusted_breakeven_probability(
        decimal_odds=1.80,
        commission_fraction=0.05,
    )
    assert break_even_zero == pytest.approx(1.0 / 1.80)
    assert break_even_five > break_even_zero
    assert isolated_back_expected_value(
        win_probability=break_even_five,
        decimal_odds=1.80,
        commission_fraction=0.05,
    ) == pytest.approx(0.0)


def test_clv_positive_when_market_moves_toward_selected_runner() -> None:
    result = exchange_clv(
        decision_market_probability=0.55,
        close_market_probability=0.60,
        decision_back_price=1.90,
        close_back_price=1.70,
    )
    assert result.probability_clv == pytest.approx(0.05)
    assert result.logit_probability_clv > 0.0
    assert result.executable_back_price_clv == pytest.approx(math.log(1.90 / 1.70))
    assert result.executable_back_price_clv > 0.0


def test_clv_requires_both_back_prices_or_neither() -> None:
    with pytest.raises(ValueError, match="must be supplied together"):
        exchange_clv(
            decision_market_probability=0.55,
            close_market_probability=0.60,
            decision_back_price=1.90,
        )


def test_extreme_probabilities_produce_finite_logit_clv() -> None:
    result = exchange_clv(
        decision_market_probability=0.0,
        close_market_probability=1.0,
    )
    assert math.isfinite(result.logit_probability_clv)
    assert result.logit_probability_clv > 0.0
