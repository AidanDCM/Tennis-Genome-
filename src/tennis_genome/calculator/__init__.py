"""Provider-neutral, market-blind matchup calculator."""

from .engine import MatchupCalculator, fair_decimal_odds, load_neighbor_bank
from .types import FairDecimalOdds, MatchupCalculation, MatchupInput

__all__ = [
    "FairDecimalOdds",
    "MatchupCalculation",
    "MatchupCalculator",
    "MatchupInput",
    "fair_decimal_odds",
    "load_neighbor_bank",
]
