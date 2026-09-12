from __future__ import annotations

import json
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from tennis_genome.data.canonical import HistoricalMatch, MatchOutcome, MatchStats, PreMatchState
from tennis_genome.experiments.pattern_confirm_live_identity import (
    build_identity_mapping,
    parse_sportradar_prematch_event,
)
from tennis_genome.experiments.pattern_confirm_production import (
    verify_core_artifact,
    verify_profile_artifact,
)
from tennis_genome.experiments.pattern_confirm_sportradar_crosswalk import (
    crosswalk_as_dict,
    seal_crosswalk,
)
from tennis_genome.experiments.pattern_confirm_sportradar_pipeline import (
    build_sportradar_prospective_state,
    training_population_hash,
    verified_frozen_base_history,
)
from tennis_genome.experiments.pattern_confirm_sportradar_state import (
    build_state_bundle,
    build_target_context_artifact,
    state_bundle_as_dict,
    target_context_as_dict,
)

ROOT = Path(__file__).resolve().parents[1]


def _profile():
    return verify_profile_artifact(
        json.loads((ROOT / "research/installment_01/profile_production_001.json").read_text())
    )


def _core():
    return verify_core_artifact(
        json.loads((ROOT / "research/installment_01/core_production_001.json").read_text())
    )


def _pre(match_id: str, event_date: date, a: str, b: str, order: int) -> PreMatchState:
    return PreMatchState(
        match_id=match_id,
        tour="ATP",
        event_date=event_date,
        source_order=order,
        tournament_id="base",
        tournament_name="Base Open",
        tournament_level="A",
        surface="Hard",
        round="R32",
        best_of=3,
        player_a_id=a,
        player_b_id=b,
        player_a_name=a,
        player_b_name=b,
        rank_a=None,
        rank_b=None,
        rank_points_a=None,
        rank_points_b=None,
        seed_a=None,
        seed_b=None,
        entry_a=None,
        entry_b=None,
        hand_a="R",
        hand_b="R",
        height_cm_a=185,
        height_cm_b=188,
        age_years_a=25.0,
        age_years_b=26.0,
        ioc_a="USA",
        ioc_b="USA",
    )


def _match(match_id: str, when: date, a: str, b: str, order: int, a_won: bool) -> HistoricalMatch:
    return HistoricalMatch(
        pre_match=_pre(match_id, when, a, b, order),
        outcome=MatchOutcome(
            match_id=match_id,
            a_won=a_won,
            score=None,
            retirement=False,
            walkover=False,
        ),
        stats=MatchStats(
            match_id=match_id,
            service_points_a=60,
            service_points_b=58,
            first_serve_points_won_a=28,
            second_serve_points_won_a=14,
            first_serve_points_won_b=25,
            second_serve_points_won_b=13,
            duration_minutes=90,
        ),
    )


def _base() -> list[HistoricalMatch]:
    return [
        _match("b1", date(2025, 1, 2), "A", "C", 1, True),
        _match("b2", date(2025, 2, 3), "B", "C", 2, False),
    ]


def _toy_models(base: list[HistoricalMatch]):
    row_hash = training_population_hash(base)
    profile = replace(_profile(), training_n=len(base), training_rows_sha256=row_hash)
    core = replace(_core(), training_n=len(base), training_rows_sha256=row_hash)
    return profile, core


def _summary(
    *,
    event_id: str,
    season_start: str,
    status: str,
    winner_id: str | None = None,
) -> dict[str, object]:
    status_payload: dict[str, object] = {"status": status}
    if winner_id is not None:
        status_payload["winner_id"] = winner_id
    return {
        "sport_event": {
            "id": event_id,
            "start_time": "2026-03-15T17:00:00+00:00",
            "start_time_confirmed": True,
            "sport_event_context": {
                "category": {"id": "sr:category:3", "name": "ATP"},
                "competition": {
                    "id": "sr:competition:55",
                    "name": "ATP Test Men Singles",
                    "type": "singles",
                    "level": "atp_250",
                },
                "season": {
                    "id": f"sr:season:{season_start}",
                    "name": "ATP Test 2026",
                    "start_date": season_start,
                    "end_date": "2026-03-20",
                    "competition_id": "sr:competition:55",
                },
                "round": {"name": "round_of_32"},
                "mode": {"best_of": 3},
            },
            "competitors": [
                {
                    "id": "sr:competitor:11",
                    "name": "Player A",
                    "qualifier": "home",
                    "country_code": "USA",
                    "virtual": False,
                },
                {
                    "id": "sr:competitor:22",
                    "name": "Player B",
                    "qualifier": "away",
                    "country_code": "USA",
                    "virtual": False,
                },
            ],
        },
        "sport_event_status": status_payload,
    }


def _target_context():
    summary = _summary(
        event_id="sr:sport_event:target",
        season_start="2026-03-01",
        status="not_started",
    )
    event = parse_sportradar_prematch_event(summary)
    mapping = build_identity_mapping(
        market_event_id="odds-target",
        market_player_a_name="Player A",
        market_player_b_name="Player B",
        player_a_canonical_id="A",
        player_b_canonical_id="B",
        sportradar_event=event,
        method="EXPLICIT_CROSSWALK",
        created_at="2026-02-28T15:00:00+00:00",
    )
    season_info = {
        "season": {
            "id": mapping.season_id,
            "competition_id": mapping.competition_id,
            "competition": {
                "id": mapping.competition_id,
                "name": mapping.competition_name,
                "type": "singles",
                "level": "atp_250",
            },
            "info": {"surface": "hard", "number_of_competitors": 32},
        }
    }
    profile_a = {
        "competitor": {"id": mapping.player_a_sportradar_id, "country_code": "USA"},
        "info": {"date_of_birth": "1998-01-01", "handedness": "right", "height": 185},
    }
    profile_b = {
        "competitor": {"id": mapping.player_b_sportradar_id, "country_code": "USA"},
        "info": {"date_of_birth": "1997-01-01", "handedness": "right", "height": 188},
    }
    context = build_target_context_artifact(
        match_id="target",
        identity_mapping=mapping,
        summary_payload=summary,
        season_info_payload=season_info,
        profile_a_payload=profile_a,
        profile_b_payload=profile_b,
    )
    return mapping, context


def _crosswalk() -> tuple[dict[str, str], dict[str, object]]:
    mapping = {
        "sr:competitor:11": "A",
        "sr:competitor:22": "B",
    }
    return mapping, crosswalk_as_dict(seal_crosswalk(mapping))


def test_frozen_base_must_reproduce_training_hash() -> None:
    base = _base()
    profile, core = _toy_models(base)
    assert verified_frozen_base_history(
        base, profile_artifact=profile, core_artifact=core
    ) == base
    with pytest.raises(ValueError, match="training-row hash"):
        verified_frozen_base_history(
            [replace(base[0], outcome=replace(base[0].outcome, a_won=False)), base[1]],
            profile_artifact=profile,
            core_artifact=core,
        )


def test_sportradar_bundle_and_target_build_internal_state() -> None:
    base = _base()
    profile, core = _toy_models(base)
    mapping, context = _target_context()
    extension_summary = _summary(
        event_id="sr:sport_event:ext",
        season_start="2026-02-01",
        status="closed",
        winner_id="sr:competitor:11",
    )
    crosswalk, crosswalk_payload = _crosswalk()
    bundle = build_state_bundle(summaries=[extension_summary], crosswalk=crosswalk)
    artifact = build_sportradar_prospective_state(
        base_history=base,
        state_bundle_payload=state_bundle_as_dict(bundle),
        target_context_payload=target_context_as_dict(context),
        crosswalk_payload=crosswalk_payload,
        identity_mapping=mapping,
        profile_artifact=profile,
        core_artifact=core,
    )
    assert artifact.match_id == "target"
    assert artifact.event_date == "2026-03-01"
    assert artifact.history_n == 3
    assert artifact.history_source_id.startswith("CANONICAL_2000_2025_PLUS_SPORTRADAR")
    assert 0.0 < artifact.core_probability_a < 1.0


def test_extension_must_be_post_2025_and_pre_target() -> None:
    base = _base()
    profile, core = _toy_models(base)
    mapping, context = _target_context()
    crosswalk, crosswalk_payload = _crosswalk()
    for bad_date, message in [
        ("2025-12-01", "pre-2026"),
        ("2026-03-01", "strictly earlier"),
    ]:
        bundle = build_state_bundle(
            summaries=[
                _summary(
                    event_id=f"sr:sport_event:{bad_date}",
                    season_start=bad_date,
                    status="closed",
                    winner_id="sr:competitor:11",
                )
            ],
            crosswalk=crosswalk,
        )
        with pytest.raises(ValueError, match=message):
            build_sportradar_prospective_state(
                base_history=base,
                state_bundle_payload=state_bundle_as_dict(bundle),
                target_context_payload=target_context_as_dict(context),
                crosswalk_payload=crosswalk_payload,
                identity_mapping=mapping,
                profile_artifact=profile,
                core_artifact=core,
            )


def test_target_identity_must_match_sealed_crosswalk() -> None:
    base = _base()
    profile, core = _toy_models(base)
    mapping, context = _target_context()
    state_mapping = {
        "sr:competitor:11": "wrong-a",
        "sr:competitor:22": "B",
    }
    bundle = build_state_bundle(summaries=[], crosswalk=state_mapping)
    with pytest.raises(ValueError, match="target player A identity"):
        build_sportradar_prospective_state(
            base_history=base,
            state_bundle_payload=state_bundle_as_dict(bundle),
            target_context_payload=target_context_as_dict(context),
            crosswalk_payload=crosswalk_as_dict(seal_crosswalk(state_mapping)),
            identity_mapping=mapping,
            profile_artifact=profile,
            core_artifact=core,
        )
