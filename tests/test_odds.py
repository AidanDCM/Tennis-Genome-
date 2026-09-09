import pytest

from tennis_genome.market.odds import (
    american_to_decimal,
    edge_percentage_points,
    expected_value_per_unit,
    proportional_novig_two_way,
)


def test_american_odds_conversion():
    assert american_to_decimal(+100) == pytest.approx(2.0)
    assert american_to_decimal(-200) == pytest.approx(1.5)


def test_proportional_novig_sums_to_one():
    p_a, p_b = proportional_novig_two_way(1.80, 2.10)
    assert p_a + p_b == pytest.approx(1.0)


def test_ev_at_fair_even_money_is_zero():
    assert expected_value_per_unit(p_win=0.5, decimal_odds=2.0) == pytest.approx(0.0)


def test_edge_is_percentage_points():
    assert edge_percentage_points(p_model=0.68, p_market_novig=0.60) == pytest.approx(8.0)
