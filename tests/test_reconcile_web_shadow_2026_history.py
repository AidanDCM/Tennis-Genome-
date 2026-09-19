from __future__ import annotations

import csv
from pathlib import Path

import pytest

from scripts import reconcile_web_shadow_2026_history as reconcile

COLUMNS = [
    "tourney_id",
    "tourney_name",
    "surface",
    "draw_size",
    "tourney_level",
    "tourney_date",
    "match_num",
    "winner_id",
    "winner_name",
    "loser_id",
    "loser_name",
    "score",
    "best_of",
    "round",
]


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _row(
    *,
    match_num: int,
    winner_id: int,
    winner_name: str,
    loser_id: int,
    loser_name: str,
    score: str = "6-4 6-2",
) -> dict[str, object]:
    return {
        "tourney_id": "2026-2096",
        "tourney_name": "Canberra 125",
        "surface": "Hard",
        "draw_size": 32,
        "tourney_level": "C",
        "tourney_date": 20260105,
        "match_num": match_num,
        "winner_id": winner_id,
        "winner_name": winner_name,
        "loser_id": loser_id,
        "loser_name": loser_name,
        "score": score,
        "best_of": 3,
        "round": "R32",
    }


def test_reconcile_collapses_exact_secondary_duplicates(tmp_path: Path) -> None:
    primary = tmp_path / "main.csv"
    secondary = tmp_path / "qual.csv"
    output = tmp_path / "qual-reconciled.csv"
    receipt = tmp_path / "receipt.json"

    primary_row = _row(
        match_num=9,
        winner_id=901,
        winner_name="Primary One",
        loser_id=902,
        loser_name="Primary Two",
    )
    duplicate = _row(
        match_num=10,
        winner_id=100,
        winner_name="Alpha One",
        loser_id=200,
        loser_name="Beta Two",
    )
    unique = _row(
        match_num=11,
        winner_id=300,
        winner_name="Gamma Three",
        loser_id=400,
        loser_name="Delta Four",
    )
    _write_csv(primary, [primary_row])
    _write_csv(secondary, [duplicate, duplicate, unique])

    result = reconcile.reconcile_2026_sources(
        primary_path=primary,
        secondary_path=secondary,
        output_path=output,
        receipt_path=receipt,
        expected_exact_duplicate_rows=1,
        expected_cross_source_overlap_rows=0,
    )

    assert result["secondary_original_match_count"] == 3
    assert result["secondary_internal_exact_duplicate_id_count"] == 1
    assert result["secondary_internal_exact_duplicate_rows_removed"] == 1
    assert result["secondary_internal_conflicting_id_count"] == 0
    assert result["cross_source_overlap_rows_removed"] == 0
    assert result["secondary_reconciled_match_count"] == 2
    assert receipt.is_file()

    with output.open(encoding="utf-8", newline="") as handle:
        filtered = list(csv.DictReader(handle))
    assert [int(row["match_num"]) for row in filtered] == [10, 11]


def test_reconcile_removes_cross_source_overlap_after_exact_dedupe(
    tmp_path: Path,
) -> None:
    primary = tmp_path / "main.csv"
    secondary = tmp_path / "qual.csv"

    duplicate = _row(
        match_num=10,
        winner_id=100,
        winner_name="Alpha One",
        loser_id=200,
        loser_name="Beta Two",
    )
    unique = _row(
        match_num=11,
        winner_id=300,
        winner_name="Gamma Three",
        loser_id=400,
        loser_name="Delta Four",
    )
    _write_csv(primary, [duplicate])
    _write_csv(secondary, [duplicate, unique])

    result = reconcile.reconcile_2026_sources(
        primary_path=primary,
        secondary_path=secondary,
        output_path=tmp_path / "out.csv",
        receipt_path=tmp_path / "receipt.json",
        expected_exact_duplicate_rows=0,
        expected_cross_source_overlap_rows=1,
    )

    assert result["cross_source_overlap_rows_removed"] == 1
    assert result["cross_source_overlap_unique_id_count"] == 1
    assert result["secondary_reconciled_match_count"] == 1


def test_reconcile_rejects_conflicting_secondary_duplicate_identity(
    tmp_path: Path,
) -> None:
    primary = tmp_path / "main.csv"
    secondary = tmp_path / "qual.csv"

    _write_csv(
        primary,
        [
            _row(
                match_num=9,
                winner_id=901,
                winner_name="Primary One",
                loser_id=902,
                loser_name="Primary Two",
            )
        ],
    )
    base = _row(
        match_num=10,
        winner_id=100,
        winner_name="Alpha One",
        loser_id=200,
        loser_name="Beta Two",
    )
    conflict = dict(base)
    conflict["score"] = "7-6 6-4"
    _write_csv(secondary, [base, conflict])

    with pytest.raises(ValueError, match="conflicting rows"):
        reconcile.reconcile_2026_sources(
            primary_path=primary,
            secondary_path=secondary,
            output_path=tmp_path / "out.csv",
            receipt_path=tmp_path / "receipt.json",
        )


def test_reconcile_enforces_pinned_duplicate_expectation(tmp_path: Path) -> None:
    primary = tmp_path / "main.csv"
    secondary = tmp_path / "qual.csv"

    _write_csv(
        primary,
        [
            _row(
                match_num=9,
                winner_id=901,
                winner_name="Primary One",
                loser_id=902,
                loser_name="Primary Two",
            )
        ],
    )
    _write_csv(
        secondary,
        [
            _row(
                match_num=10,
                winner_id=100,
                winner_name="Alpha One",
                loser_id=200,
                loser_name="Beta Two",
            )
        ],
    )

    with pytest.raises(RuntimeError, match="exact-duplicate row count"):
        reconcile.reconcile_2026_sources(
            primary_path=primary,
            secondary_path=secondary,
            output_path=tmp_path / "out.csv",
            receipt_path=tmp_path / "receipt.json",
            expected_exact_duplicate_rows=216,
        )
