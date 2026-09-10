from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from tennis_genome.independent.prediction import IndependentPrediction
from tennis_genome.market.comparison import compare_prediction_to_market
from tennis_genome.market.identity import MarketIdentityResolution
from tennis_genome.market.odds import proportional_novig_two_way
from tennis_genome.market.providers.the_odds_api import (
    canonical_payload_sha256,
    parse_h2h_snapshot,
)
from tennis_genome.market.snapshot import MarketSnapshot


def _resolution() -> MarketIdentityResolution:
    return MarketIdentityResolution(
        match_id="match-1",
        provider="the_odds_api",
        source_event_id="event-1",
        source_selection_a="Player Alpha",
        source_selection_b="Player Beta",
        player_a_id="player-a",
        player_b_id="player-b",
        resolved_at=datetime(2026, 9, 10, 14, 0, tzinfo=UTC),
        method="exact_alias",
    )


def _event() -> dict[str, object]:
    return {
        "id": "event-1",
        "sport_key": "tennis_atp_example",
        "commence_time": "2026-09-10T16:00:00Z",
        "home_team": "Player Alpha",
        "away_team": "Player Beta",
        "bookmakers": [
            {
                "key": "book-a",
                "title": "Book A",
                "last_update": "2026-09-10T14:04:00Z",
                "markets": [
                    {
                        "key": "h2h",
                        "last_update": "2026-09-10T14:05:00Z",
                        "outcomes": [
                            {"name": "Player Beta", "price": 2.2},
                            {"name": "Player Alpha", "price": 1.72},
                        ],
                    }
                ],
            }
        ],
    }


def _prediction() -> IndependentPrediction:
    cutoff = datetime(2026, 9, 10, 14, 0, tzinfo=UTC)
    return IndependentPrediction(
        prediction_id="pred-1",
        match_id="match-1",
        tour="ATP",
        created_at=cutoff,
        prediction_cutoff_at=cutoff,
        p_player_a=0.62,
        p_player_b=0.38,
        source_manifest_hashes=("a" * 64,),
    )


def _snapshot() -> MarketSnapshot:
    return parse_h2h_snapshot(
        event=_event(),
        bookmaker_key="book-a",
        collected_at=datetime(2026, 9, 10, 14, 6, tzinfo=UTC),
        resolution=_resolution(),
    )


def test_identity_resolution_hash_is_deterministic() -> None:
    first = _resolution()
    second = _resolution()
    assert first.resolution_hash() == second.resolution_hash()
    assert len(first.resolution_hash()) == 64


def test_the_odds_api_parser_maps_outcomes_into_canonical_orientation() -> None:
    snapshot = _snapshot()
    assert snapshot.player_a_id == "player-a"
    assert snapshot.player_b_id == "player-b"
    assert snapshot.selection_a_name == "Player Alpha"
    assert snapshot.selection_b_name == "Player Beta"
    assert snapshot.decimal_odds_a == pytest.approx(1.72)
    assert snapshot.decimal_odds_b == pytest.approx(2.2)
    assert snapshot.observed_at == datetime(2026, 9, 10, 14, 5, tzinfo=UTC)
    assert snapshot.is_live is False
    assert snapshot.identity_resolution_hash == _resolution().resolution_hash()


def test_provider_snapshot_id_and_payload_hash_are_deterministic() -> None:
    first = _snapshot()
    second = _snapshot()
    assert first.market_snapshot_id == second.market_snapshot_id
    assert first.source_payload_sha256 == second.source_payload_sha256
    assert first.source_payload_sha256 == canonical_payload_sha256(_event())


def test_parser_rejects_wrong_identity_event_and_american_prices() -> None:
    bad_resolution = MarketIdentityResolution(
        match_id="match-1",
        provider="the_odds_api",
        source_event_id="other-event",
        source_selection_a="Player Alpha",
        source_selection_b="Player Beta",
        player_a_id="player-a",
        player_b_id="player-b",
        resolved_at=datetime(2026, 9, 10, 14, 0, tzinfo=UTC),
        method="exact_alias",
    )
    with pytest.raises(ValueError, match="source_event_id"):
        parse_h2h_snapshot(
            event=_event(),
            bookmaker_key="book-a",
            collected_at=datetime(2026, 9, 10, 14, 6, tzinfo=UTC),
            resolution=bad_resolution,
        )

    event = _event()
    outcomes = event["bookmakers"][0]["markets"][0]["outcomes"]  # type: ignore[index]
    outcomes[0]["price"] = -110  # type: ignore[index]
    with pytest.raises(ValueError, match="oddsFormat=decimal"):
        parse_h2h_snapshot(
            event=event,
            bookmaker_key="book-a",
            collected_at=datetime(2026, 9, 10, 14, 6, tzinfo=UTC),
            resolution=_resolution(),
        )


def test_collection_after_commence_marks_snapshot_live() -> None:
    snapshot = parse_h2h_snapshot(
        event=_event(),
        bookmaker_key="book-a",
        collected_at=datetime(2026, 9, 10, 16, 1, tzinfo=UTC),
        resolution=_resolution(),
    )
    assert snapshot.is_live is True


def test_novig_probabilities_are_complementary() -> None:
    p_a, p_b = proportional_novig_two_way(1.72, 2.2)
    assert p_a + p_b == pytest.approx(1.0)
    assert p_a > p_b


def test_market_comparison_calculates_edge_ev_and_margin() -> None:
    comparison = compare_prediction_to_market(
        comparison_id="cmp-1",
        created_at=datetime(2026, 9, 10, 14, 7, tzinfo=UTC),
        prediction=_prediction(),
        market=_snapshot(),
    )
    assert comparison.novig_p_a + comparison.novig_p_b == pytest.approx(1.0)
    assert comparison.edge_a_pp + comparison.edge_b_pp == pytest.approx(0.0)
    assert comparison.book_margin > 0.0
    assert comparison.ev_a_per_unit == pytest.approx(0.62 * 1.72 - 1.0)
    assert comparison.market_age_seconds_at_comparison == pytest.approx(120.0)
    assert comparison.decision_eligible is True
    assert comparison.reason_codes == ()


def test_stale_last_update_is_metadata_not_automatic_rejection() -> None:
    event = _event()
    event["bookmakers"][0]["markets"][0]["last_update"] = "2026-09-10T13:00:00Z"  # type: ignore[index]
    snapshot = parse_h2h_snapshot(
        event=event,
        bookmaker_key="book-a",
        collected_at=datetime(2026, 9, 10, 14, 6, tzinfo=UTC),
        resolution=_resolution(),
    )
    comparison = compare_prediction_to_market(
        comparison_id="cmp-stale",
        created_at=datetime(2026, 9, 10, 14, 7, tzinfo=UTC),
        prediction=_prediction(),
        market=snapshot,
    )
    assert comparison.market_age_seconds_at_comparison == pytest.approx(4020.0)
    assert comparison.decision_eligible is True


def test_live_or_mismatched_market_cannot_be_compared() -> None:
    live = parse_h2h_snapshot(
        event=_event(),
        bookmaker_key="book-a",
        collected_at=datetime(2026, 9, 10, 16, 1, tzinfo=UTC),
        resolution=_resolution(),
    )
    with pytest.raises(ValueError, match="live markets"):
        compare_prediction_to_market(
            comparison_id="cmp-live",
            created_at=datetime(2026, 9, 10, 16, 2, tzinfo=UTC),
            prediction=_prediction(),
            market=live,
        )

    mismatched = MarketSnapshot(
        **{**_snapshot().__dict__, "match_id": "other-match"}
    )
    with pytest.raises(ValueError, match="same match_id"):
        compare_prediction_to_market(
            comparison_id="cmp-other",
            created_at=datetime(2026, 9, 10, 14, 7, tzinfo=UTC),
            prediction=_prediction(),
            market=mismatched,
        )


def test_market_schemas_keep_raw_and_derived_records_separate() -> None:
    raw_schema = json.loads(
        Path("schemas/market_snapshot.schema.json").read_text(encoding="utf-8")
    )
    comparison_schema = json.loads(
        Path("schemas/market_comparison.schema.json").read_text(encoding="utf-8")
    )
    raw_fields = set(raw_schema["properties"])
    derived_fields = set(comparison_schema["properties"])

    assert "edge_a_pp" not in raw_fields
    assert "ev_a_per_unit" not in raw_fields
    assert "novig_p_a" not in raw_fields
    assert {"edge_a_pp", "ev_a_per_unit", "novig_p_a"}.issubset(derived_fields)


def test_independent_package_has_no_market_imports() -> None:
    for path in Path("src/tennis_genome/independent").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "tennis_genome.market" not in text
