from __future__ import annotations

import math
from dataclasses import dataclass

_EPSILON = 1e-12


@dataclass(frozen=True)
class ExchangeFairProbability:
    method: str
    probability_a: float
    probability_b: float
    raw_mid_implied_a: float
    raw_mid_implied_b: float

    def __post_init__(self) -> None:
        if self.method != "exchange_mid_implied_proportional_v1":
            raise ValueError("unsupported exchange probability method")
        for name, value in (
            ("probability_a", self.probability_a),
            ("probability_b", self.probability_b),
            ("raw_mid_implied_a", self.raw_mid_implied_a),
            ("raw_mid_implied_b", self.raw_mid_implied_b),
        ):
            if not math.isfinite(value) or not 0.0 < value < 1.0:
                raise ValueError(f"{name} must be finite and in (0, 1)")
        if not math.isclose(
            self.probability_a + self.probability_b,
            1.0,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise ValueError("fair probabilities must sum to one")


@dataclass(frozen=True)
class ExchangeCLV:
    probability_clv: float
    logit_probability_clv: float
    executable_back_price_clv: float | None


def _validate_price(value: float, *, name: str) -> float:
    price = float(value)
    if not math.isfinite(price) or price <= 1.0:
        raise ValueError(f"{name} must be finite and greater than 1.0")
    return price


def _validate_probability(value: float, *, name: str) -> float:
    probability = float(value)
    if not math.isfinite(probability) or not 0.0 <= probability <= 1.0:
        raise ValueError(f"{name} must be finite and in [0, 1]")
    return probability


def _validate_commission(value: float) -> float:
    commission = float(value)
    if not math.isfinite(commission) or not 0.0 <= commission < 1.0:
        raise ValueError("commission_fraction must be finite and in [0, 1)")
    return commission


def exchange_mid_implied_proportional_v1(
    *,
    back_a: float,
    lay_a: float,
    back_b: float,
    lay_b: float,
) -> ExchangeFairProbability:
    """Convert executable two-way Exchange quotes to a symmetric fair benchmark.

    The transform is preregistered for MARKET-EDGE-001. It averages implied
    back/lay probabilities within each runner, then proportionally normalizes
    the two mid-implied values to sum to one.
    """

    back_a = _validate_price(back_a, name="back_a")
    lay_a = _validate_price(lay_a, name="lay_a")
    back_b = _validate_price(back_b, name="back_b")
    lay_b = _validate_price(lay_b, name="lay_b")
    if back_a > lay_a:
        raise ValueError("back_a cannot exceed lay_a")
    if back_b > lay_b:
        raise ValueError("back_b cannot exceed lay_b")

    q_a = 0.5 * ((1.0 / back_a) + (1.0 / lay_a))
    q_b = 0.5 * ((1.0 / back_b) + (1.0 / lay_b))
    total = q_a + q_b
    if not math.isfinite(total) or total <= 0.0:
        raise ValueError("invalid implied-probability normalization")
    return ExchangeFairProbability(
        method="exchange_mid_implied_proportional_v1",
        probability_a=q_a / total,
        probability_b=q_b / total,
        raw_mid_implied_a=q_a,
        raw_mid_implied_b=q_b,
    )


def isolated_back_expected_value(
    *,
    win_probability: float,
    decimal_odds: float,
    commission_fraction: float,
) -> float:
    """Unit-stake EV for one isolated Exchange back position.

    Commission is applied only to positive winnings from the isolated
    position. Multi-position market settlement requires a separate net-market
    accounting layer.
    """

    probability = _validate_probability(win_probability, name="win_probability")
    odds = _validate_price(decimal_odds, name="decimal_odds")
    commission = _validate_commission(commission_fraction)
    return probability * (odds - 1.0) * (1.0 - commission) - (1.0 - probability)


def commission_adjusted_breakeven_probability(
    *,
    decimal_odds: float,
    commission_fraction: float,
) -> float:
    """Minimum model probability for zero isolated-position Exchange EV."""

    odds = _validate_price(decimal_odds, name="decimal_odds")
    commission = _validate_commission(commission_fraction)
    net_win = (odds - 1.0) * (1.0 - commission)
    return 1.0 / (1.0 + net_win)


def _logit(value: float) -> float:
    probability = _validate_probability(value, name="probability")
    clipped = min(max(probability, _EPSILON), 1.0 - _EPSILON)
    return math.log(clipped / (1.0 - clipped))


def exchange_clv(
    *,
    decision_market_probability: float,
    close_market_probability: float,
    decision_back_price: float | None = None,
    close_back_price: float | None = None,
) -> ExchangeCLV:
    """Compute the preregistered probability and optional executable-price CLV."""

    decision = _validate_probability(
        decision_market_probability,
        name="decision_market_probability",
    )
    close = _validate_probability(close_market_probability, name="close_market_probability")

    price_clv: float | None = None
    if (decision_back_price is None) != (close_back_price is None):
        raise ValueError("decision_back_price and close_back_price must be supplied together")
    if decision_back_price is not None and close_back_price is not None:
        decision_price = _validate_price(decision_back_price, name="decision_back_price")
        close_price = _validate_price(close_back_price, name="close_back_price")
        price_clv = math.log(decision_price / close_price)

    return ExchangeCLV(
        probability_clv=close - decision,
        logit_probability_clv=_logit(close) - _logit(decision),
        executable_back_price_clv=price_clv,
    )
