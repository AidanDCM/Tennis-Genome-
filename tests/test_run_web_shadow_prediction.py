from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import run_web_shadow_prediction as runner


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


def _matchup(tmp_path: Path) -> Path:
    path = tmp_path / "matchup.json"
    path.write_text("{}", encoding="utf-8")
    return path


def _loaded_matchup():
    return SimpleNamespace(
        tour="WTA",
        match_id="web:wta:test:1",
        player_a_id="100",
        player_b_id="200",
        created_at=datetime(2026, 9, 20, 1, 0, tzinfo=UTC),
        prediction_cutoff_at=datetime(2026, 9, 20, 1, 0, tzinfo=UTC),
        foundational=SimpleNamespace(event_date=date(2026, 9, 21)),
    )


def _calculation():
    return SimpleNamespace(
        player_a_id="100",
        player_b_id="200",
        production_bundle_sha256="a" * 64,
        assessment_status="DIAGNOSTIC_ONLY_NO_HARD_PASS",
        prediction=SimpleNamespace(p_player_a=0.62, p_player_b=0.38),
    )


def test_runner_binds_fixture_to_genome_output(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(runner, "load_matchup_input", lambda path: _loaded_matchup())
    calculator = SimpleNamespace(calculate=lambda matchup: _calculation())
    monkeypatch.setattr(
        runner,
        "load_validated_matchup_calculator",
        lambda path: calculator,
    )
    output = tmp_path / "prediction.json"
    record = runner.run_web_shadow_prediction(
        fixture_path=_fixture(tmp_path),
        matchup_input_path=_matchup(tmp_path),
        bundle_path=tmp_path / "bundle.json",
        player_a_id="100",
        player_b_id="200",
        model_source_sha="b" * 40,
        output_path=output,
        committed_at=datetime(2026, 9, 20, 2, 0, tzinfo=UTC),
    )
    assert record["p_player_a"] == pytest.approx(0.62)
    assert record["selected_player"] == "Alpha"
    assert record["player_a_id"] == "100"
    assert record["player_b_id"] == "200"
    assert record["production_eligible"] is False
    assert output.is_file()


def test_runner_rejects_identity_mismatch(monkeypatch, tmp_path: Path) -> None:
    bad = _loaded_matchup()
    bad.player_b_id = "999"
    monkeypatch.setattr(runner, "load_matchup_input", lambda path: bad)
    with pytest.raises(ValueError, match="player IDs differ"):
        runner.run_web_shadow_prediction(
            fixture_path=_fixture(tmp_path),
            matchup_input_path=_matchup(tmp_path),
            bundle_path=tmp_path / "bundle.json",
            player_a_id="100",
            player_b_id="200",
            model_source_sha="b" * 40,
            output_path=tmp_path / "prediction.json",
            committed_at=datetime(2026, 9, 20, 2, 0, tzinfo=UTC),
        )


def test_runner_rejects_future_information_cutoff(monkeypatch, tmp_path: Path) -> None:
    matchup = _loaded_matchup()
    matchup.prediction_cutoff_at = datetime(2026, 9, 20, 3, 0, tzinfo=UTC)
    monkeypatch.setattr(runner, "load_matchup_input", lambda path: matchup)
    with pytest.raises(ValueError, match="cutoff occurs after"):
        runner.run_web_shadow_prediction(
            fixture_path=_fixture(tmp_path),
            matchup_input_path=_matchup(tmp_path),
            bundle_path=tmp_path / "bundle.json",
            player_a_id="100",
            player_b_id="200",
            model_source_sha="b" * 40,
            output_path=tmp_path / "prediction.json",
            committed_at=datetime(2026, 9, 20, 2, 0, tzinfo=UTC),
        )


def test_runner_reuses_supplied_calculator(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(runner, "load_matchup_input", lambda path: _loaded_matchup())

    def unexpected_load(path):
        raise AssertionError("calculator should not be reloaded")

    monkeypatch.setattr(runner, "load_validated_matchup_calculator", unexpected_load)
    calculator = SimpleNamespace(calculate=lambda matchup: _calculation())

    record = runner.run_web_shadow_prediction(
        fixture_path=_fixture(tmp_path),
        matchup_input_path=_matchup(tmp_path),
        bundle_path=tmp_path / "bundle.json",
        player_a_id="100",
        player_b_id="200",
        model_source_sha="b" * 40,
        output_path=tmp_path / "prediction-shared.json",
        committed_at=datetime(2026, 9, 20, 2, 0, tzinfo=UTC),
        calculator=calculator,
    )

    assert record["p_player_a"] == pytest.approx(0.62)
