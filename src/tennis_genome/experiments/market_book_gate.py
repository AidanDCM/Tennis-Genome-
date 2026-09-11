from __future__ import annotations

import json
from pathlib import Path
from typing import Literal, cast

Tour = Literal["ATP", "WTA"]
_CONFIRMATORY_STATUS = "ELIGIBLE_CONFIRMATORY"
_REQUIRED_GATES = {
    "overall_close_coverage_at_least_60pct",
    "every_recent_year_close_coverage_at_least_50pct",
    "every_recent_year_at_least_100_rows",
    "at_least_1000_prior_rows_before_first_evaluation_year",
    "all_2021_2025_years_in_evaluation_population",
    "passed",
}


def load_confirmatory_market_book_qa(path: str | Path) -> dict[Tour, str]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("MARKET-BOOK-QA artifact must be a JSON object")
    if payload.get("experiment_id") != "MARKET-BOOK-QA-001":
        raise ValueError("unexpected MARKET-BOOK-QA experiment ID")
    if payload.get("structural_pass") is not True:
        raise ValueError("MARKET-BOOK-QA is structurally blocked")
    if payload.get("overall_status") != _CONFIRMATORY_STATUS:
        raise ValueError("MARKET-BOOK-QA overall status is not confirmatory")
    tours = payload.get("tours")
    if not isinstance(tours, list):
        raise ValueError("MARKET-BOOK-QA tours must be a list")

    result: dict[Tour, str] = {}
    for row in tours:
        if not isinstance(row, dict):
            raise ValueError("MARKET-BOOK-QA contains an invalid tour row")
        tour_text = str(row.get("tour", ""))
        if tour_text not in {"ATP", "WTA"}:
            raise ValueError(f"invalid MARKET-BOOK-QA tour: {tour_text!r}")
        tour = cast(Tour, tour_text)
        if tour in result:
            raise ValueError(f"duplicate MARKET-BOOK-QA tour row for {tour}")
        status = str(row.get("status", ""))
        if status != _CONFIRMATORY_STATUS:
            raise ValueError(
                "bookmaker confirmatory evaluation requires QA-eligible ATP and WTA; "
                f"blocked={[tour]}"
            )
        gates = row.get("gates")
        if not isinstance(gates, dict):
            raise ValueError(f"MARKET-BOOK-QA {tour} row lacks coverage gates")
        if set(gates) != _REQUIRED_GATES:
            raise ValueError(f"MARKET-BOOK-QA {tour} gate set differs from frozen design")
        if any(gates[name] is not True for name in _REQUIRED_GATES):
            raise ValueError(f"MARKET-BOOK-QA {tour} has a failed frozen coverage gate")
        result[tour] = status

    if set(result) != {"ATP", "WTA"}:
        raise ValueError("MARKET-BOOK-QA must report ATP and WTA")
    return dict(sorted(result.items()))
