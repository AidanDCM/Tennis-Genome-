from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from tennis_genome.research_workbench.sportradar_identity_candidates import (
    build_candidate_report,
    normalize_name,
)


def test_name_normalization_reorders_and_folds_accents() -> None:
    assert normalize_name("Nadál, Rafael") == normalize_name("Rafael Nadal")


def test_report_preserves_ambiguity_and_country_conflict(tmp_path: Path) -> None:
    history = tmp_path / "history"
    for tour in ("atp", "wta"):
        folder = history / tour
        folder.mkdir(parents=True)
        pd.DataFrame(
            {
                "player_a_id": ["1", "3"],
                "player_b_id": ["2", "4"],
                "player_a_name": ["Rafael Nadal", "Same Name"],
                "player_b_name": ["Other Player", "Same Name"],
                "ioc_a": ["ESP", "USA"],
                "ioc_b": ["GER", "CAN"],
            }
        ).to_parquet(folder / f"{tour}_pre_match.parquet")
    capture = tmp_path / "capture"
    season = capture / "seasons" / "sr_season_1"
    season.mkdir(parents=True)
    summary = {
        "sport_event": {
            "sport_event_context": {"category": {"id": "sr:category:3"}},
            "competitors": [
                {"id": "sr:competitor:1", "name": "Nadal, Rafael", "country_code": "ESP"},
                {"id": "sr:competitor:2", "name": "Name, Same", "country_code": "USA"},
                {"id": "sr:competitor:3", "name": "Player, Other", "country_code": "FRA"},
                {"id": "sr:competitor:4", "name": "Nobody New", "country_code": "USA"},
                {"id": "sr:competitor:5", "name": "Player, Other", "country_code": "DEU"},
            ],
        }
    }
    (season / "page-000-offset-000000.json").write_text(
        json.dumps({"summaries": [summary]}), encoding="utf-8"
    )
    report = build_candidate_report(capture_root=capture, canonical_root=history)
    assert report["authoritative_crosswalk"] is False
    assert report["counts"] == {
        "AMBIGUOUS_NAME": 1,
        "UNIQUE_NAME_COUNTRY_AGREES": 1,
        "UNIQUE_NAME_COUNTRY_CODE_CONVENTION": 1,
        "UNIQUE_NAME_COUNTRY_CONFLICT": 1,
        "UNMATCHED": 1,
    }


def test_changed_provider_identity_fails(tmp_path: Path) -> None:
    capture = tmp_path / "capture" / "seasons" / "sr_season_1"
    capture.mkdir(parents=True)
    for index, name in enumerate(("First", "Second")):
        (capture / f"page-{index:03d}-offset-{index:06d}.json").write_text(
            json.dumps(
                {
                    "summaries": [
                        {
                            "sport_event": {
                                "sport_event_context": {"category": {"id": "sr:category:3"}},
                                "competitors": [{"id": "sr:competitor:1", "name": name}],
                            }
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
    with pytest.raises(ValueError, match="identity changed"):
        build_candidate_report(capture_root=tmp_path / "capture", canonical_root=tmp_path)
