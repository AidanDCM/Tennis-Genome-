"""Provider-neutral, market-blind matchup calculator."""

from .engine import MatchupCalculator, fair_decimal_odds, load_neighbor_bank
from .market import compare_manual_decimal_odds
from .types import FairDecimalOdds, MatchupCalculation, MatchupInput

__all__ = [
    "FairDecimalOdds",
    "MatchupCalculation",
    "MatchupCalculator",
    "MatchupInput",
    "compare_manual_decimal_odds",
    "fair_decimal_odds",
    "load_neighbor_bank",
]
