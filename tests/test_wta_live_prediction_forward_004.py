from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from scripts import wta_live_prediction_forward_004 as fwd


def _helper():
    def qualified_competitors(event):
        comps = event["competitors"]
        home = next(item for item in comps if item["qualifier"] == "home")
        away = next(item for item in comps if item["qualifier"] == "away")
        return home, away

    def resolve_competitor(comp, by_name, explicit):
        sr = str(comp["id"])
        if sr in explicit:
            return explicit[sr]
        return by_name.get(str(comp["name"]))

    return SimpleNamespace(
        ALLOWED_LEVELS={"wta_250", "wta_500"},
        LEVEL_MAP={"wta_250": "I", "wta_500": "P"},
        SURFACE_MAP={"hard": "Hard", "clay": "Clay"},
        ROUND_MAP={"quarterfinal": "QF"},
        TARGET_MATCH_ID="sr:sport_event:1",
        TARGET_SEASON_ID="sr:season:1",
        TARGET_TOURNEY_DATE=datetime(2026, 9, 18, tzinfo=UTC).date(),
        PARRY_SR="sr:competitor:1",
        STEARNS_SR="sr:competitor:2",
        PARRY_CANONICAL="100",
        STEARNS_CANONICAL="200",
        qualified_competitors=qualified_competitors,
        resolve_competitor=resolve_competitor,
        optional_int=lambda value: None if value is None else int(value),
        provider_full_name=lambda value: value,
        age_years=lambda dob, when: 25.0,
    )


def _summary(
    *,
    event_id: str,
    start: str,
    home_name: str = "Alpha",
    away_name: str = "Beta",
    level: str = "wta_250",
    status: str = "not_started",
    confirmed: bool = True,
):
    return {
        "sport_event": {
            "id": event_id,
            "start_time": start,
            "start_time_confirmed": confirmed,
            "sport_event_context": {
                "category": {"id": "sr:category:6", "name": "WTA"},
                "competition": {
                    "id": "sr:competition:10",
                    "name": "Test WTA",
                    "type": "singles",
                    "level": level,
                },
                "season": {
                    "id": "sr:season:10",
                    "competition_id": "sr:competition:10",
                    "start_date": "2026-09-18",
                },
                "round": {"name": "quarterfinal"},
                "mode": {"best_of": 3},
            },
            "competitors": [
                {
                    "id": "sr:competitor:1",
                    "name": home_name,
                    "qualifier": "home",
                    "seed": 1,
                },
                {
                    "id": "sr:competitor:2",
                    "name": away_name,
                    "qualifier": "away",
                    "seed": 2,
                },
            ],
        },
        "sport_event_status": {"status": status, "match_status": status},
    }


def test_selector_uses_earliest_confirmed_resolvable_target_after_fixed_lead() -> None:
    h = _helper()
    observed = datetime(2026, 9, 18, 12, 0, tzinfo=UTC)
    by_name = {"Alpha": "100", "Beta": "200"}
    summaries = [
        _summary(event_id="sr:sport_event:later", start="2026-09-18T16:00:00+00:00"),
        _summary(event_id="sr:sport_event:early", start="2026-09-18T14:00:00+00:00"),
        _summary(event_id="sr:sport_event:too-soon", start="2026-09-18T13:00:00+00:00"),
    ]

    selected, resolution = fwd.select_forward_004_target(
        h,
        summaries=summaries,
        by_name=by_name,
        capture_observed_at=observed,
    )

    assert selected["sport_event"]["id"] == "sr:sport_event:early"
    assert resolution["event_id"] == "sr:sport_event:early"
    assert resolution["minimum_capture_lead_minutes"] == "90"
    assert resolution["player_a_canonical_id"] == "100"
    assert resolution["player_b_canonical_id"] == "200"


def test_selector_tie_breaks_by_event_id_and_rejects_ineligible_rows() -> None:
    h = _helper()
    observed = datetime(2026, 9, 18, 12, 0, tzinfo=UTC)
    by_name = {"Alpha": "100", "Beta": "200"}
    start = "2026-09-18T15:00:00+00:00"
    summaries = [
        _summary(event_id="sr:sport_event:20", start=start),
        _summary(event_id="sr:sport_event:10", start=start),
        _summary(
            event_id="sr:sport_event:bad-level",
            start="2026-09-18T14:00:00+00:00",
            level="wta_125",
        ),
        _summary(
            event_id="sr:sport_event:unconfirmed",
            start="2026-09-18T14:00:00+00:00",
            confirmed=False,
        ),
        _summary(
            event_id="sr:sport_event:live",
            start="2026-09-18T14:00:00+00:00",
            status="live",
        ),
    ]

    selected, _ = fwd.select_forward_004_target(
        h,
        summaries=summaries,
        by_name=by_name,
        capture_observed_at=observed,
    )

    assert selected["sport_event"]["id"] == "sr:sport_event:10"


def test_selector_fails_when_no_resolvable_host_exists() -> None:
    h = _helper()
    with pytest.raises(RuntimeError, match="no resolvable pre-match WTA"):
        fwd.select_forward_004_target(
            h,
            summaries=[
                _summary(
                    event_id="sr:sport_event:1",
                    start="2026-09-18T16:00:00+00:00",
                    home_name="Unknown",
                )
            ],
            by_name={"Beta": "200"},
            capture_observed_at=datetime(2026, 9, 18, 12, 0, tzinfo=UTC),
        )


def test_generic_target_state_derives_level_surface_round_and_player_order() -> None:
    h = _helper()
    target = _summary(
        event_id="sr:sport_event:1",
        start="2026-09-18T16:00:00+00:00",
        level="wta_500",
    )
    by_id = {
        "100": {"hand": "R", "height": "180", "dob": "20000101", "country": "USA"},
        "200": {"hand": "L", "height": "175", "dob": "20010101", "country": "CAN"},
    }
    info = {
        "season": {
            "info": {
                "surface": "hard",
                "number_of_competitors": 32,
            }
        }
    }

    state = fwd._generic_target_state(h, target, info, by_id)

    assert state.tournament_level == "P"
    assert state.surface == "Hard"
    assert state.round == "QF"
    assert state.best_of == 3
    assert state.player_a_id == "100"
    assert state.player_b_id == "200"
    assert state.seed_a == 1
    assert state.seed_b == 2


def test_generic_target_state_fails_closed_on_unknown_surface() -> None:
    h = _helper()
    target = _summary(
        event_id="sr:sport_event:1",
        start="2026-09-18T16:00:00+00:00",
    )
    by_id = {
        "100": {"hand": "R", "height": "180", "dob": "20000101", "country": "USA"},
        "200": {"hand": "L", "height": "175", "dob": "20010101", "country": "CAN"},
    }

    with pytest.raises(RuntimeError, match="target surface is unsupported"):
        fwd._generic_target_state(
            h,
            target,
            {"season": {"info": {"surface": "ice"}}},
            by_id,
        )
