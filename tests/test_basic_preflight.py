from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd
import pytest

from tennis_genome.data.canonical import PreMatchState
from tennis_genome.experiments.basic_preflight import (
    _latest_start_month,
    _tour_report,
    build_basic_preflight_report,
)


def _state(
    *,
    match_id: str,
    tour: str,
    event_date: date,
    player_a_name: str,
    player_b_name: str,
) -> PreMatchState:
    return PreMatchState(
        match_id=match_id,
        tour=tour,  # type: ignore[arg-type]
        event_date=event_date,
        source_order=0,
        tournament_id=f"t-{match_id}",
        tournament_name="Synthetic Open",
        tournament_level="A",
        surface="Hard",
        round="R32",
        best_of=3,
        player_a_id=f"a-{match_id}",
        player_b_id=f"b-{match_id}",
        player_a_name=player_a_name,
        player_b_name=player_b_name,
        rank_a=10,
        rank_b=20,
        rank_points_a=2000,
        rank_points_b=1500,
    )


def _write_pre_match(path: Path, states: list[PreMatchState], *, leak: bool = False) -> None:
    rows = [asdict(state) for state in states]
    if leak:
        for row in rows:
            row["a_won"] = True
    pd.DataFrame(rows).to_parquet(path, index=False)


def _market_definition(
    *,
    event_id: str,
    event_name: str,
    market_time: datetime,
    player_a: str,
    player_b: str,
) -> dict[str, object]:
    return {
        "eventId": event_id,
        "eventTypeId": "2",
        "marketType": "MATCH_ODDS",
        "eventName": event_name,
        "marketTime": market_time.isoformat(),
        "status": "OPEN",
        "inPlay": False,
        "runners": [
            {"id": 101, "name": player_a, "status": "ACTIVE"},
            {"id": 202, "name": player_b, "status": "ACTIVE"},
        ],
    }


def _basic_line(
    *,
    market_id: str,
    event_id: str,
    market_time: datetime,
    player_a: str,
    player_b: str,
) -> str:
    published = int(market_time.timestamp() * 1000) - 60_000
    return json.dumps(
        {
            "op": "mcm",
            "pt": published,
            "mc": [
                {
                    "id": market_id,
                    "marketDefinition": _market_definition(
                        event_id=event_id,
                        event_name=f"{player_a} v {player_b}",
                        market_time=market_time,
                        player_a=player_a,
                        player_b=player_b,
                    ),
                }
            ],
        },
        sort_keys=True,
    )


def test_basic_preflight_is_deterministic_and_outcome_blind(tmp_path: Path) -> None:
    root = tmp_path / "basic"
    root.mkdir()
    states = [
        _state(
            match_id="atp-2024-1",
            tour="ATP",
            event_date=date(2024, 6, 10),
            player_a_name="Alpha One",
            player_b_name="Beta Two",
        ),
        _state(
            match_id="wta-2024-1",
            tour="WTA",
            event_date=date(2024, 7, 10),
            player_a_name="Gamma Three",
            player_b_name="Delta Four",
        ),
    ]
    pre_match = tmp_path / "pre_match.parquet"
    _write_pre_match(pre_match, states)
    lines = [
        _basic_line(
            market_id="1.100",
            event_id="e1",
            market_time=datetime(2024, 6, 10, 18, tzinfo=UTC),
            player_a="Alpha One",
            player_b="Beta Two",
        ),
        _basic_line(
            market_id="1.200",
            event_id="e2",
            market_time=datetime(2024, 7, 10, 18, tzinfo=UTC),
            player_a="Gamma Three",
            player_b="Delta Four",
        ),
    ]
    (root / "markets.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")

    first = build_basic_preflight_report(
        betfair_root=root,
        pre_match_path=pre_match,
        requested_start_date="2024-01-01",
        requested_end_date="2024-12-31",
    )
    second = build_basic_preflight_report(
        betfair_root=root,
        pre_match_path=pre_match,
        requested_start_date="2024-01-01",
        requested_end_date="2024-12-31",
    )
    assert first == second
    assert first.data_package == "BASIC"
    assert first.markets_reconstructed == 2
    assert first.markets_matched == 2
    assert first.markets_unmatched == 0
    assert first.markets_ambiguous == 0
    assert first.recommendation_class == "INSUFFICIENT_BASIC_PRIOR_HISTORY"
    assert len(first.artifact_sha256) == 64
    assert all(item.basic_matched_rows == 1 for item in first.tours)


def test_preflight_rejects_outcome_leakage_in_pre_match(tmp_path: Path) -> None:
    root = tmp_path / "basic"
    root.mkdir()
    (root / "one.jsonl").write_text("{}\n", encoding="utf-8")
    state = _state(
        match_id="m1",
        tour="ATP",
        event_date=date(2024, 1, 1),
        player_a_name="A",
        player_b_name="B",
    )
    pre_match = tmp_path / "pre_match.parquet"
    _write_pre_match(pre_match, [state], leak=True)
    with pytest.raises(ValueError, match="outcome fields leaked"):
        build_basic_preflight_report(
            betfair_root=root,
            pre_match_path=pre_match,
            requested_start_date="2024-01-01",
            requested_end_date="2024-12-31",
        )


def test_preflight_enforces_provider_and_development_boundaries(tmp_path: Path) -> None:
    root = tmp_path / "basic"
    root.mkdir()
    (root / "one.jsonl").write_text("{}\n", encoding="utf-8")
    pre_match = tmp_path / "pre_match.parquet"
    _write_pre_match(
        pre_match,
        [
            _state(
                match_id="m1",
                tour="ATP",
                event_date=date(2024, 1, 1),
                player_a_name="A",
                player_b_name="B",
            )
        ],
    )
    with pytest.raises(ValueError, match="2015-04-01"):
        build_basic_preflight_report(
            betfair_root=root,
            pre_match_path=pre_match,
            requested_start_date="2015-03-31",
            requested_end_date="2025-12-31",
        )
    with pytest.raises(ValueError, match="2025-12-31"):
        build_basic_preflight_report(
            betfair_root=root,
            pre_match_path=pre_match,
            requested_start_date="2020-01-01",
            requested_end_date="2026-01-01",
        )


def test_latest_start_month_is_mechanical() -> None:
    states: list[PreMatchState] = []
    counter = 0
    for month in range(1, 13):
        for index in range(100):
            counter += 1
            states.append(
                _state(
                    match_id=f"m-{counter}",
                    tour="ATP",
                    event_date=date(2020, month, min(index % 28 + 1, 28)),
                    player_a_name=f"A {counter}",
                    player_b_name=f"B {counter}",
                )
            )
    assert _latest_start_month(states, interval_start=date(2019, 1, 1)) == "2020-03-01"


def test_tour_report_uses_21_day_safe_population_and_frozen_recent_checks() -> None:
    states: list[PreMatchState] = []
    matched: set[str] = set()
    counter = 0
    for year in range(2019, 2026):
        rows = 600 if year < 2021 else 120
        for index in range(rows):
            counter += 1
            match_id = f"atp-{counter}"
            state = _state(
                match_id=match_id,
                tour="ATP",
                event_date=date(year, 6, index % 28 + 1),
                player_a_name=f"A {counter}",
                player_b_name=f"B {counter}",
            )
            states.append(state)
            matched.add(match_id)
    boundary = _state(
        match_id="boundary",
        tour="ATP",
        event_date=date(2025, 12, 20),
        player_a_name="Boundary A",
        player_b_name="Boundary B",
    )
    states.append(boundary)
    matched.add(boundary.match_id)

    report = _tour_report(
        tour="ATP",
        states=states,
        matched_ids=matched,
        start=date(2019, 1, 1),
        safe_end=date(2025, 12, 10),
    )
    assert report.overall_coverage_pass
    assert report.recent_coverage_pass
    assert report.recent_count_pass
    assert report.prior_history_pass
    assert report.latest_start_month_with_1000_prior is not None
    assert report.basic_matched_rows == len(states) - 1


def test_preflight_rejects_two_markets_joining_same_canonical_match(tmp_path: Path) -> None:
    root = tmp_path / "basic"
    root.mkdir()
    state = _state(
        match_id="m1",
        tour="ATP",
        event_date=date(2024, 5, 1),
        player_a_name="Same Alpha",
        player_b_name="Same Beta",
    )
    pre_match = tmp_path / "pre_match.parquet"
    _write_pre_match(pre_match, [state])
    market_time = datetime(2024, 5, 1, 18, tzinfo=UTC)
    (root / "markets.jsonl").write_text(
        "\n".join(
            [
                _basic_line(
                    market_id="1.1",
                    event_id="e1",
                    market_time=market_time,
                    player_a="Same Alpha",
                    player_b="Same Beta",
                ),
                _basic_line(
                    market_id="1.2",
                    event_id="e2",
                    market_time=market_time,
                    player_a="Same Alpha",
                    player_b="Same Beta",
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="multiple BASIC source markets"):
        build_basic_preflight_report(
            betfair_root=root,
            pre_match_path=pre_match,
            requested_start_date="2024-01-01",
            requested_end_date="2024-12-31",
        )
