from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

from tennis_genome.experiments.market_edge import MarketSignalRow, SignalName, Tour
from tennis_genome.experiments.market_edge_inputs import SettledOutcome, SignalValue


@dataclass(frozen=True)
class BookmakerClosingMarketRow:
    match_id: str
    tour: Tour
    source_family: str
    market_probability_a: float
    market_probability_b: float
    decimal_odds_a: float
    decimal_odds_b: float
    record_hash: str
    join_hash: str
    match_date: str


def _sha256_hex(value: object, *, name: str) -> str:
    text = str(value).lower()
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise ValueError(f"{name} must be a SHA-256 hex digest")
    return text


def load_bookmaker_closing_rows(path: str | Path) -> dict[str, BookmakerClosingMarketRow]:
    """Load only selected MARKET-BOOK-001 BOOKMAKER_CLOSE_V1 rows."""

    result: dict[str, BookmakerClosingMarketRow] = {}
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"line {line_number}: bookmaker market record must be an object")
            if value.get("selected_primary") is not True:
                continue
            if value.get("selected_policy") != "BOOKMAKER_CLOSE_V1":
                raise ValueError("selected bookmaker row has unexpected market policy")
            if value.get("join_status") != "MATCHED" or value.get("quote_valid") is not True:
                raise ValueError("selected bookmaker row is not a valid matched quote")
            if value.get("source_conflict") is True:
                raise ValueError("selected bookmaker row is source-conflicted")
            join = value.get("join")
            if not isinstance(join, dict):
                raise ValueError("selected bookmaker row lacks join object")
            match_id = str(join["match_id"])
            if match_id in result:
                raise ValueError(f"multiple selected bookmaker closes for {match_id}")
            tour = str(join["tour"])
            if tour not in {"ATP", "WTA"}:
                raise ValueError("selected bookmaker row has invalid tour")
            p_a = float(value["market_probability_a"])
            p_b = float(value["market_probability_b"])
            odds_a = float(value["decimal_odds_a"])
            odds_b = float(value["decimal_odds_b"])
            if not all(math.isfinite(item) for item in (p_a, p_b, odds_a, odds_b)):
                raise ValueError("selected bookmaker row contains non-finite market values")
            if not 0.0 < p_a < 1.0 or not 0.0 < p_b < 1.0:
                raise ValueError("selected bookmaker probability must be in (0, 1)")
            if not math.isclose(p_a + p_b, 1.0, rel_tol=0.0, abs_tol=1e-12):
                raise ValueError("selected bookmaker probabilities must sum to one")
            if odds_a <= 1.0 or odds_b <= 1.0:
                raise ValueError("selected bookmaker decimal odds must exceed 1.0")
            result[match_id] = BookmakerClosingMarketRow(
                match_id=match_id,
                tour=tour,  # type: ignore[arg-type]
                source_family=str(value["source_family"]),
                market_probability_a=p_a,
                market_probability_b=p_b,
                decimal_odds_a=odds_a,
                decimal_odds_b=odds_b,
                record_hash=_sha256_hex(value.get("record_hash"), name="record_hash"),
                join_hash=_sha256_hex(join.get("join_hash"), name="join_hash"),
                match_date=str(value["match_date"]),
            )
    return result


def build_bookmaker_market_signal_rows(
    *,
    close_rows: dict[str, BookmakerClosingMarketRow],
    outcomes: dict[str, SettledOutcome],
    signals: dict[str, SignalValue],
    years_by_match: dict[str, int],
    tour: Tour,
    signal_name: SignalName,
) -> list[MarketSignalRow]:
    rows: list[MarketSignalRow] = []
    shared = sorted(set(close_rows).intersection(outcomes, signals, years_by_match))
    for match_id in shared:
        market = close_rows[match_id]
        if market.tour != tour:
            continue
        rows.append(
            MarketSignalRow(
                match_id=match_id,
                tour=tour,
                year=int(years_by_match[match_id]),
                outcome_a=outcomes[match_id].outcome_a,
                market_probability_a=market.market_probability_a,
                signal=signals[match_id].signal,
            )
        )
    return sorted(rows, key=lambda row: (row.year, row.match_id))
