from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from tennis_genome.data.canonical import HistoricalMatch, MatchOutcome, MatchStats, PreMatchState
from tennis_genome.experiments.pattern_confirm_live_state import (
    build_prospective_state_artifact,
    prospective_state_as_dict,
    verify_prospective_state_artifact,
)
from tennis_genome.experiments.pattern_confirm_production import (
    verify_core_artifact,
    verify_profile_artifact,
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


def _pre(
    match_id: str,
    event_date: date,
    *,
    a: str,
    b: str,
    order: int,
) -> PreMatchState:
    return PreMatchState(
        match_id=match_id,
        tour="ATP",
        event_date=event_date,
        source_order=order,
        tournament_id="T1",
        tournament_name="Test Open",
        tournament_level="A",
        surface="Hard",
        round="R32",
        best_of=3,
        player_a_id=a,
        player_b_id=b,
        player_a_name=f"Player {a}",
        player_b_name=f"Player {b}",
        rank_a=10 + order,
        rank_b=20 + order,
        rank_points_a=3000 - order * 10,
        rank_points_b=2000 - order * 10,
        seed_a=1,
        seed_b=2,
        entry_a=None,
        entry_b=None,
        hand_a="R",
        hand_b="R",
        height_cm_a=185,
        height_cm_b=180,
        age_years_a=25.0,
        age_years_b=27.0,
        ioc_a="USA",
        ioc_b="ESP",
    )


def _match(
    match_id: str,
    event_date: date,
    *,
    a: str,
    b: str,
    order: int,
    a_won: bool,
    retirement: bool = False,
    walkover: bool = False,
) -> HistoricalMatch:
    return HistoricalMatch(
        pre_match=_pre(match_id, event_date, a=a, b=b, order=order),
        outcome=MatchOutcome(
            match_id=match_id,
            a_won=a_won,
            score=None,
            retirement=retirement,
            walkover=walkover,
        ),
        stats=MatchStats(
            match_id=match_id,
            service_points_a=60,
            service_points_b=58,
            first_serve_points_won_a=28,
            second_serve_points_won_a=14,
            first_serve_points_won_b=25,
            second_serve_points_won_b=13,
            duration_minutes=92,
        ),
    )


def _history() -> list[HistoricalMatch]:
    return [
        _match("m1", date(2026, 1, 2), a="A", b="C", order=1, a_won=True),
        _match("m2", date(2026, 1, 4), a="B", b="C", order=2, a_won=False),
        _match("m3", date(2026, 1, 7), a="A", b="B", order=3, a_won=True),
        _match("m4", date(2026, 1, 10), a="C", b="A", order=4, a_won=False),
    ]


def _target() -> PreMatchState:
    return _pre("target", date(2026, 1, 15), a="A", b="B", order=100)


def _rehash(payload: dict[str, object]) -> None:
    unsigned = dict(payload)
    unsigned.pop("artifact_sha256", None)
    raw = json.dumps(
        unsigned,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    payload["artifact_sha256"] = hashlib.sha256(raw).hexdigest()


def test_builds_and_verifies_internal_profile_and_core_values() -> None:
    artifact = build_prospective_state_artifact(
        history=_history(),
        target=_target(),
        history_source_id="synthetic-state-source",
        history_source_sha256="a" * 64,
        profile_artifact=_profile(),
        core_artifact=_core(),
    )
    assert artifact.match_id == "target"
    assert artifact.event_date == "2026-01-15"
    assert artifact.history_n == 4
    assert artifact.profile_model_sha256 == _profile().artifact_sha256
    assert artifact.core_model_sha256 == _core().artifact_sha256
    assert artifact.core_probability_a > 0.0
    assert artifact.core_probability_a < 1.0
    verified = verify_prospective_state_artifact(
        prospective_state_as_dict(artifact),
        profile_artifact=_profile(),
        core_artifact=_core(),
    )
    assert verified.artifact_sha256 == artifact.artifact_sha256


def test_rehashed_signal_tampering_does_not_verify() -> None:
    artifact = build_prospective_state_artifact(
        history=_history(),
        target=_target(),
        history_source_id="synthetic-state-source",
        history_source_sha256="b" * 64,
        profile_artifact=_profile(),
        core_artifact=_core(),
    )
    payload = prospective_state_as_dict(artifact)
    payload["profile_gap"] = float(payload["profile_gap"]) + 0.5
    _rehash(payload)
    with pytest.raises(ValueError, match="Profile Gap does not reproduce"):
        verify_prospective_state_artifact(
            payload,
            profile_artifact=_profile(),
            core_artifact=_core(),
        )


def test_same_day_or_future_history_is_rejected_before_replay() -> None:
    history = _history()
    history.append(
        _match(
            "same-day",
            _target().event_date,
            a="C",
            b="A",
            order=5,
            a_won=True,
        )
    )
    with pytest.raises(ValueError, match="strictly earlier"):
        build_prospective_state_artifact(
            history=history,
            target=_target(),
            history_source_id="synthetic-state-source",
            history_source_sha256="c" * 64,
            profile_artifact=_profile(),
            core_artifact=_core(),
        )


def test_retirements_and_walkovers_do_not_update_live_state() -> None:
    history = _history()
    history.extend(
        [
            _match(
                "retired",
                date(2026, 1, 11),
                a="A",
                b="C",
                order=5,
                a_won=True,
                retirement=True,
            ),
            _match(
                "walkover",
                date(2026, 1, 12),
                a="B",
                b="C",
                order=6,
                a_won=True,
                walkover=True,
            ),
        ]
    )
    artifact = build_prospective_state_artifact(
        history=history,
        target=_target(),
        history_source_id="synthetic-state-source",
        history_source_sha256="d" * 64,
        profile_artifact=_profile(),
        core_artifact=_core(),
    )
    assert artifact.history_n == 4


def test_target_identity_cannot_already_exist_in_history() -> None:
    base = _history()[0]
    assert base.stats is not None
    duplicate = HistoricalMatch(
        pre_match=replace(base.pre_match, match_id="target"),
        outcome=replace(base.outcome, match_id="target"),
        stats=replace(base.stats, match_id="target"),
    )
    with pytest.raises(ValueError, match="already exists"):
        build_prospective_state_artifact(
            history=[duplicate, *_history()[1:]],
            target=_target(),
            history_source_id="synthetic-state-source",
            history_source_sha256="e" * 64,
            profile_artifact=_profile(),
            core_artifact=_core(),
        )


def test_source_hash_must_be_real_sha256_shape() -> None:
    with pytest.raises(ValueError, match="history_source_sha256"):
        build_prospective_state_artifact(
            history=_history(),
            target=_target(),
            history_source_id="synthetic-state-source",
            history_source_sha256="not-a-hash",
            profile_artifact=_profile(),
            core_artifact=_core(),
        )
