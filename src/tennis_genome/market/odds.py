from __future__ import annotations


def american_to_decimal(odds: float) -> float:
    """Convert American odds to decimal odds."""
    odds = float(odds)
    if odds == 0:
        raise ValueError("American odds cannot be zero")
    if odds > 0:
        return 1.0 + odds / 100.0
    return 1.0 + 100.0 / abs(odds)


def implied_probability_from_decimal(decimal_odds: float) -> float:
    decimal_odds = float(decimal_odds)
    if decimal_odds <= 1.0:
        raise ValueError("decimal odds must be greater than 1.0")
    return 1.0 / decimal_odds


def proportional_novig_two_way(decimal_a: float, decimal_b: float) -> tuple[float, float]:
    """Remove two-way vig by proportional normalization of implied probabilities."""
    raw_a = implied_probability_from_decimal(decimal_a)
    raw_b = implied_probability_from_decimal(decimal_b)
    total = raw_a + raw_b
    if total <= 0:
        raise ValueError("invalid implied-probability total")
    return raw_a / total, raw_b / total


def expected_value_per_unit(*, p_win: float, decimal_odds: float) -> float:
    """Expected net profit per unit staked."""
    p_win = float(p_win)
    if not 0.0 <= p_win <= 1.0:
        raise ValueError("p_win must be in [0, 1]")
    decimal_odds = float(decimal_odds)
    if decimal_odds <= 1.0:
        raise ValueError("decimal odds must be greater than 1.0")
    return p_win * (decimal_odds - 1.0) - (1.0 - p_win)


def edge_percentage_points(*, p_model: float, p_market_novig: float) -> float:
    """Return model-minus-market edge in percentage points."""
    for name, p in {"p_model": p_model, "p_market_novig": p_market_novig}.items():
        if not 0.0 <= float(p) <= 1.0:
            raise ValueError(f"{name} must be in [0, 1]")
    return (float(p_model) - float(p_market_novig)) * 100.0
