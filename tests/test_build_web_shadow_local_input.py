from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import build_web_shadow_local_input as builder


def _fixture(tmp_path: Path) -> Path:
    path = tmp_path / "fixture.json"
    path.write_text(
        json.dumps(
            {
                "match_id": "web:wta:test:1",
                "tour": "WTA",
                "tournament": "Test Open",
                "round": "R32",
                "surface": "Hard",
                "scheduled_start": "2026-09-21T12:00:00+09:00",
                "player_a": "Alpha",
                "player_b": "Beta",
                "source_url": "https://example.com/fixture",
                "source_observed_at": "2026-09-20T12:00:00+09:00",
            }
        ),
        encoding="utf-8",
    )
    return path


def _target(tmp_path: Path) -> Path:
    path = tmp_path / "target.json"
    payload = {
        "match_id": "web:wta:test:1",
        "tour": "WTA",
        "event_date": "2026-09-21",
        "source_order": 1,
        "tournament_id": "web:test",
        "tournament_name": "Test Open",
        "tournament_level": "I",
        "surface": "Hard",
        "round": "R32",
        "best_of": 3,
        "player_a_id": "wta:id:100",
        "player_b_id": "wta:id:200",
        "player_a_name": "Alpha",
        "player_b_name": "Beta",
        "rank_a": None,
        "rank_b": None,
        "rank_points_a": None,
        "rank_points_b": None,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _history():
    outcome = SimpleNamespace(walkover=False, retirement=False)
    return [
        SimpleNamespace(
            pre_match=SimpleNamespace(
                event_date=date(2025, 12, 30),
                player_a_id="wta:id:100",
                player_b_id="wta:id:999",
            ),
            outcome=outcome,
        ),
        SimpleNamespace(
            pre_match=SimpleNamespace(
                event_date=date(2025, 12, 31),
                player_a_id="wta:id:200",
                player_b_id="wta:id:998",
            ),
            outcome=outcome,
        ),
    ]


@dataclass(frozen=True)
class _FoundSnapshot:
    match_id: str
    event_date: date
    value: float


@dataclass(frozen=True)
class _ServeSnapshot:
    match_id: str
    event_date: date
    prior_serve_points_a: int
    prior_serve_points_b: int
    prior_return_points_a: int
    prior_return_points_b: int


def _found_snapshot(match_id: str) -> _FoundSnapshot:
    return _FoundSnapshot(match_id=match_id, event_date=date(2026, 9, 21), value=1.0)


def _serve_snapshot(match_id: str) -> _ServeSnapshot:
    return _ServeSnapshot(
        match_id=match_id,
        event_date=date(2026, 9, 21),
        prior_serve_points_a=100,
        prior_serve_points_b=120,
        prior_return_points_a=90,
        prior_return_points_b=110,
    )


def test_local_builder_marks_history_limitation_and_writes_input(
    monkeypatch, tmp_path: Path
) -> None:
    base = tmp_path / "base"
    base.mkdir()
    for name in ("wta_pre_match.parquet", "wta_outcomes.parquet", "wta_stats.parquet"):
        (base / name).write_bytes(name.encode())

    monkeypatch.setattr(builder, "load_canonical_parquet", lambda **kwargs: _history())
    monkeypatch.setattr(
        builder,
        "walk_forward_foundational_features",
        lambda combined, exclude_retirements: [_found_snapshot("web:wta:test:1")],
    )
    monkeypatch.setattr(
        builder,
        "walk_forward_serve_return",
        lambda combined, exclude_retirements: [_serve_snapshot("web:wta:test:1")],
    )

    output = tmp_path / "matchup.json"
    manifest_path = tmp_path / "manifest.json"
    manifest = builder.build_local_web_shadow_matchup(
        fixture_path=_fixture(tmp_path),
        target_state_path=_target(tmp_path),
        base_dir=base,
        output_path=output,
        manifest_path=manifest_path,
    )

    payload = json.loads(output.read_text())
    assert payload["match_id"] == "web:wta:test:1"
    assert payload["player_a_id"] == "wta:id:100"
    assert payload["player_b_id"] == "wta:id:200"
    assert manifest["history_mode"] == "FROZEN_LOCAL_HISTORY_ONLY"
    assert manifest["production_eligible"] is False
    assert manifest["target_history_match_counts"] == {
        "wta:id:100": 1,
        "wta:id:200": 1,
    }
    assert manifest["minimum_point_exposure"] == 90
    assert manifest_path.is_file()


def test_local_builder_rejects_noncanonical_identity_order(tmp_path: Path) -> None:
    target = json.loads(_target(tmp_path).read_text())
    target["player_a_id"] = "wta:id:900"
    target["player_b_id"] = "wta:id:200"
    target_path = tmp_path / "target-bad.json"
    target_path.write_text(json.dumps(target))

    with pytest.raises(ValueError, match="canonical ascending"):
        builder._load_target_state(target_path, builder._load_fixture(_fixture(tmp_path)))


def test_local_builder_rejects_missing_target_history(monkeypatch, tmp_path: Path) -> None:
    base = tmp_path / "base-missing"
    base.mkdir()
    for name in ("wta_pre_match.parquet", "wta_outcomes.parquet", "wta_stats.parquet"):
        (base / name).write_bytes(name.encode())

    outcome = SimpleNamespace(walkover=False, retirement=False)
    history = [
        SimpleNamespace(
            pre_match=SimpleNamespace(
                event_date=date(2025, 12, 31),
                player_a_id="wta:id:100",
                player_b_id="wta:id:999",
            ),
            outcome=outcome,
        )
    ]
    monkeypatch.setattr(builder, "load_canonical_parquet", lambda **kwargs: history)

    with pytest.raises(RuntimeError, match="no frozen historical matches"):
        builder.build_local_web_shadow_matchup(
            fixture_path=_fixture(tmp_path),
            target_state_path=_target(tmp_path),
            base_dir=base,
            output_path=tmp_path / "matchup.json",
            manifest_path=tmp_path / "manifest.json",
        )


def test_local_builder_rejects_unexpected_history_cutoff(
    monkeypatch, tmp_path: Path
) -> None:
    base = tmp_path / "base-cutoff"
    base.mkdir()
    for name in ("wta_pre_match.parquet", "wta_outcomes.parquet", "wta_stats.parquet"):
        (base / name).write_bytes(name.encode())

    monkeypatch.setattr(builder, "load_canonical_parquet", lambda **kwargs: _history())

    with pytest.raises(RuntimeError, match="maximum date differs"):
        builder.build_local_web_shadow_matchup(
            fixture_path=_fixture(tmp_path),
            target_state_path=_target(tmp_path),
            base_dir=base,
            output_path=tmp_path / "matchup.json",
            manifest_path=tmp_path / "manifest.json",
            history_mode="PINNED_PUBLIC_HISTORY_THROUGH_2026_06_02",
            expected_history_max_date=date(2026, 6, 2),
        )
