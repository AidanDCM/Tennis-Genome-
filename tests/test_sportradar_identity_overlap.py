from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from tennis_genome.research_workbench.sportradar_identity_overlap import (
    corroborate_overlap_identities,
)


def _fixture(tmp_path: Path, *, provider_winner: str = "sr:a") -> tuple[Path, Path]:
    csv = tmp_path / "matches.csv"
    pd.DataFrame(
        [
            {
                "tourney_name": "Test Open",
                "winner_name": "Alice One",
                "winner_id": "101",
                "loser_name": "Bob Two",
                "loser_id": "202",
            },
            {
                "tourney_name": "Test Open",
                "winner_name": "Alice One",
                "winner_id": "101",
                "loser_name": "Cara Three",
                "loser_id": "303",
            },
        ]
    ).to_csv(csv, index=False)
    capture = tmp_path / "seasons" / "sr_season_1"
    capture.mkdir(parents=True)
    summaries = []
    for opponent_id, opponent_name in (("sr:b", "Two, Bob"), ("sr:c", "Three, Cara")):
        summaries.append(
            {
            "sport_event": {
                "id": f"event:{opponent_id}",
                "sport_event_context": {
                    "category": {"id": "sr:category:3"},
                    "season": {"id": "sr:season:1"},
                    "competition": {"type": "singles"},
                },
                "competitors": [
                        {"id": "sr:a", "name": "One, Alice"},
                        {"id": opponent_id, "name": opponent_name},
                    ],
                },
                "sport_event_status": {"status": "closed", "winner_id": provider_winner},
            }
        )
    (capture / "page-000-offset-000000.json").write_text(
        json.dumps({"summaries": summaries}), encoding="utf-8"
    )
    return tmp_path / "seasons", csv


def test_overlap_corroborates_repeated_identity_without_sealing(tmp_path: Path) -> None:
    capture, csv = _fixture(tmp_path)
    report = corroborate_overlap_identities(
        capture_root=capture, canonical_csv=csv, season_tournaments={"sr:season:1": "Test Open"}
    )
    assert report["authoritative_crosswalk"] is False
    assert report["matched_events"] == 2
    assert report["corroborated_players"] == 3
    alice = next(row for row in report["rows"] if row["provider_id"] == "sr:a")
    assert alice["canonical_id"] == "101"
    assert len(alice["matches"]) == 2


def test_overlap_rejects_winner_conflict(tmp_path: Path) -> None:
    capture, csv = _fixture(tmp_path, provider_winner="sr:b")
    with pytest.raises(ValueError, match="winner conflict"):
        corroborate_overlap_identities(
            capture_root=capture, canonical_csv=csv, season_tournaments={"sr:season:1": "Test Open"}
        )
