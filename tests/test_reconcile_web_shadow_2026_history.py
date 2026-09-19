from __future__ import annotations

import csv
from pathlib import Path

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
        "score": "6-4 6-2",
        "best_of": 3,
        "round": "R32",
    }


def test_reconcile_removes_cross_source_duplicate_ids(tmp_path: Path) -> None:
    primary = tmp_path / "main.csv"
    secondary = tmp_path / "qual.csv"
    output = tmp_path / "qual-reconciled.csv"
    receipt = tmp_path / "receipt.json"

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
        output_path=output,
        receipt_path=receipt,
    )

    assert result["primary_match_count"] == 1
    assert result["secondary_original_match_count"] == 2
    assert result["secondary_reconciled_match_count"] == 1
    assert result["removed_overlap_count"] == 1
    assert len(result["removed_overlap_ids"]) == 1
    assert receipt.is_file()

    with output.open(encoding="utf-8", newline="") as handle:
        filtered = list(csv.DictReader(handle))
    assert [int(row["match_num"]) for row in filtered] == [11]


def test_reconcile_requires_real_overlap(tmp_path: Path) -> None:
    primary = tmp_path / "main.csv"
    secondary = tmp_path / "qual.csv"

    _write_csv(
        primary,
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
    _write_csv(
        secondary,
        [
            _row(
                match_num=11,
                winner_id=300,
                winner_name="Gamma Three",
                loser_id=400,
                loser_name="Delta Four",
            )
        ],
    )

    try:
        reconcile.reconcile_2026_sources(
            primary_path=primary,
            secondary_path=secondary,
            output_path=tmp_path / "out.csv",
            receipt_path=tmp_path / "receipt.json",
        )
    except RuntimeError as exc:
        assert "removed none" in str(exc)
    else:
        raise AssertionError("non-overlapping 2026 sources should fail the overlap contract")
