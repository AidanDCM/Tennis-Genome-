from __future__ import annotations

from tennis_genome.experiments.market_book_inputs import (
    BookmakerClosingMarketRow,
    build_bookmaker_market_signal_rows,
)
from tennis_genome.experiments.market_edge_inputs import SettledOutcome, SignalValue


def _close(match_id: str, tour: str, probability: float) -> BookmakerClosingMarketRow:
    return BookmakerClosingMarketRow(
        match_id=match_id,
        tour=tour,  # type: ignore[arg-type]
        source_family="VALUEBETENNIS",
        market_probability_a=probability,
        market_probability_b=1.0 - probability,
        decimal_odds_a=1.8,
        decimal_odds_b=2.1,
        record_hash="a" * 64,
        join_hash="b" * 64,
        match_date="2024-06-01",
    )


def test_bookmaker_market_probability_reaches_frozen_claim_row() -> None:
    match_id = "atp-2024-001"
    rows = build_bookmaker_market_signal_rows(
        close_rows={match_id: _close(match_id, "ATP", 0.637)},
        outcomes={match_id: SettledOutcome(match_id=match_id, outcome_a=True)},
        signals={match_id: SignalValue(match_id=match_id, signal=1.25)},
        years_by_match={match_id: 2024},
        tour="ATP",
        signal_name="profile_gap",
    )
    assert len(rows) == 1
    assert rows[0].market_probability_a == 0.637
    assert rows[0].signal == 1.25
    assert rows[0].outcome_a is True


def test_bookmaker_rows_do_not_cross_tours() -> None:
    match_id = "wta-2024-001"
    rows = build_bookmaker_market_signal_rows(
        close_rows={match_id: _close(match_id, "WTA", 0.55)},
        outcomes={match_id: SettledOutcome(match_id=match_id, outcome_a=False)},
        signals={match_id: SignalValue(match_id=match_id, signal=-0.2)},
        years_by_match={match_id: 2024},
        tour="ATP",
        signal_name="genome",
    )
    assert rows == []
