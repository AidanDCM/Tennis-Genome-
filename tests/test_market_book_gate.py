from __future__ import annotations

import json
from pathlib import Path

import pytest

from tennis_genome.experiments.market_book_gate import load_confirmatory_market_book_qa


def _gates() -> dict[str, bool]:
    return {
        "overall_close_coverage_at_least_60pct": True,
        "every_recent_year_close_coverage_at_least_50pct": True,
        "every_recent_year_at_least_100_rows": True,
        "at_least_1000_prior_rows_before_first_evaluation_year": True,
        "all_2021_2025_years_in_evaluation_population": True,
        "passed": True,
    }


def _payload(*, missing_year: int | None = None) -> dict[str, object]:
    tours = []
    for tour in ("ATP", "WTA"):
        annual = [
            {"year": year, "eligible_canonical": 200, "usable_close": 150}
            for year in range(2021, 2026)
            if year != missing_year
        ]
        tours.append(
            {
                "tour": tour,
                "status": "ELIGIBLE_CONFIRMATORY",
                "annual": annual,
                "gates": _gates(),
            }
        )
    return {
        "experiment_id": "MARKET-BOOK-QA-001",
        "structural_pass": True,
        "overall_status": "ELIGIBLE_CONFIRMATORY",
        "tours": tours,
    }


def _write(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_confirmatory_gate_accepts_literal_five_year_evidence(tmp_path: Path) -> None:
    path = tmp_path / "qa.json"
    _write(path, _payload())
    assert load_confirmatory_market_book_qa(path) == {
        "ATP": "ELIGIBLE_CONFIRMATORY",
        "WTA": "ELIGIBLE_CONFIRMATORY",
    }


def test_confirmatory_gate_rejects_missing_evaluation_year(tmp_path: Path) -> None:
    path = tmp_path / "qa.json"
    _write(path, _payload(missing_year=2024))
    with pytest.raises(ValueError, match="missing=.*2024"):
        load_confirmatory_market_book_qa(path)


def test_confirmatory_gate_rejects_extra_or_missing_gate_names(tmp_path: Path) -> None:
    payload = _payload()
    tours = payload["tours"]
    assert isinstance(tours, list)
    row = tours[0]
    assert isinstance(row, dict)
    gates = row["gates"]
    assert isinstance(gates, dict)
    gates["unexpected"] = True
    path = tmp_path / "qa.json"
    _write(path, payload)
    with pytest.raises(ValueError, match="gate set differs"):
        load_confirmatory_market_book_qa(path)
