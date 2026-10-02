from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from tennis_genome.research_workbench.sportradar_stat_overlap import audit_stat_overlap


def test_overlap_counts_field_disagreement_without_harmonizing(tmp_path: Path) -> None:
    csv = tmp_path / "atp_matches_2026.csv"
    pd.DataFrame(
        [
            {
                "tourney_name": "Test",
                "winner_name": "Rafael Nadal",
                "loser_name": "Roger Federer",
                "w_ace": 4,
                "l_ace": 5,
                "w_df": 1,
                "l_df": 2,
                "w_1stIn": 60,
                "l_1stIn": 55,
                "w_1stWon": 40,
                "l_1stWon": 38,
                "w_2ndWon": 20,
                "l_2ndWon": 18,
                "w_svpt": 90,
                "l_svpt": 85,
            }
        ]
    ).to_csv(csv, index=False)
    season = tmp_path / "seasons" / "sr_season_1"
    season.mkdir(parents=True)
    competitors = [
        {"id": "sr:competitor:1", "name": "Nadal, Rafael", "qualifier": "home"},
        {"id": "sr:competitor:2", "name": "Federer, Roger", "qualifier": "away"},
    ]
    stats = [
        {
            "id": "sr:competitor:1",
            "statistics": {
                "aces": 4,
                "double_faults": 1,
                "first_serve_successful": 61,
                "first_serve_points_won": 40,
                "second_serve_points_won": 20,
                "service_points_won": 60,
                "service_points_lost": 30,
            },
        },
        {
            "id": "sr:competitor:2",
            "statistics": {
                "aces": 5,
                "double_faults": 2,
                "first_serve_successful": 55,
                "first_serve_points_won": 38,
                "second_serve_points_won": 18,
                "service_points_won": 56,
                "service_points_lost": 29,
            },
        },
    ]
    (season / "page-000-offset-000000.json").write_text(
        json.dumps(
            {
                "summaries": [
                    {
                        "sport_event": {"competitors": competitors},
                        "sport_event_status": {"status": "closed", "winner_id": "sr:competitor:1"},
                        "statistics": {"totals": {"competitors": stats}},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (season / "page-000-offset-000000.headers").write_text(
        "HTTP/1.1 200\nX-Max-Results: 1\nX-Offset: 0\nX-Result: 1\n",
        encoding="utf-8",
    )
    report = audit_stat_overlap(
        capture_root=tmp_path / "seasons",
        canonical_csv=csv,
        season_tournaments={"sr:season:1": "Test"},
    )
    counts = report["total_counts"]
    assert counts["pair_matches"] == 1
    assert counts["first_serve_successful_compared"] == 2
    assert counts["first_serve_successful_equal"] == 1
    assert counts["service_points_equal"] == 2
    assert report["mixed_source_stats_approved"] is False
