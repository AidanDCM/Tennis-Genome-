"""Provider-neutral, market-blind matchup calculator."""

from .contract import load_validated_matchup_calculator, validate_frozen_bundle_contract
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
    "load_validated_matchup_calculator",
    "validate_frozen_bundle_contract",
]
