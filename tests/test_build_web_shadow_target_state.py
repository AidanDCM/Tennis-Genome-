from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import build_web_shadow_target_state as builder


def _fixture(tmp_path: Path) -> Path:
    path = tmp_path / "fixture.json"
    path.write_text(
        json.dumps(
            {
                "match_id": "web:wta:singapore:2026:RS006",
                "tour": "WTA",
                "tournament": "Singapore Tennis Open",
                "round": "QFNL",
                "surface": "Hard",
                "scheduled_start": "2026-09-20T13:30:00+08:00",
                "player_a": "Mei Yamaguchi",
                "player_b": "Kyoka Okamura",
                "source_url": "https://www.wtatennis.com/example",
                "source_observed_at": "2026-09-19T22:00:00+08:00",
                "tournament_id": "web:wta:singapore:2026",
                "tournament_level": "P",
            }
        ),
        encoding="utf-8",
    )
    return path


def _registry(tmp_path: Path) -> Path:
    path = tmp_path / "wta_players.csv"
    path.write_text(
        "300,Mei,Yamaguchi,R,19990524,JPN,159\n"
        "200,Kyoka,Okamura,R,19951006,JPN,165\n",
        encoding="utf-8",
    )
    return path


def test_target_builder_resolves_and_canonicalizes_player_order(tmp_path: Path) -> None:
    target_path = tmp_path / "target.json"
    normalized_path = tmp_path / "normalized.json"

    target = builder.build_web_shadow_target_state(
        fixture_path=_fixture(tmp_path),
        registry_path=_registry(tmp_path),
        target_state_path=target_path,
        normalized_fixture_path=normalized_path,
    )

    assert target["player_a_id"] == "wta:id:200"
    assert target["player_a_name"] == "Kyoka Okamura"
    assert target["player_b_id"] == "wta:id:300"
    assert target["player_b_name"] == "Mei Yamaguchi"
    assert target["round"] == "QFNL"
    assert target["tournament_level"] == "P"

    normalized = json.loads(normalized_path.read_text(encoding="utf-8"))
    assert normalized["player_a"] == "Kyoka Okamura"
    assert normalized["player_b"] == "Mei Yamaguchi"


def test_target_builder_rejects_missing_registry_identity(tmp_path: Path) -> None:
    registry = tmp_path / "wta_players.csv"
    registry.write_text("300,Mei,Yamaguchi,R,19990524,JPN,159\n", encoding="utf-8")

    with pytest.raises(ValueError, match="absent from pinned WTA registry"):
        builder.build_web_shadow_target_state(
            fixture_path=_fixture(tmp_path),
            registry_path=registry,
            target_state_path=tmp_path / "target.json",
            normalized_fixture_path=tmp_path / "normalized.json",
        )


def test_target_builder_requires_frozen_level_mapping(tmp_path: Path) -> None:
    fixture = json.loads(_fixture(tmp_path).read_text(encoding="utf-8"))
    fixture["tournament_level"] = "WTA500"
    path = tmp_path / "bad-fixture.json"
    path.write_text(json.dumps(fixture), encoding="utf-8")

    with pytest.raises(ValueError, match="frozen WTA level map"):
        builder.build_web_shadow_target_state(
            fixture_path=path,
            registry_path=_registry(tmp_path),
            target_state_path=tmp_path / "target.json",
            normalized_fixture_path=tmp_path / "normalized.json",
        )
