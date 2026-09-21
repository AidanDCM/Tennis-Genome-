from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import settle_web_shadow_prediction as runner
from tennis_genome.prospective.web_shadow import WebShadowFixture, WebShadowPrediction


def _prediction(tmp_path: Path) -> tuple[Path, dict[str, object]]:
    path = tmp_path / "web-shadow/predictions/test.json"
    path.parent.mkdir(parents=True)
    record = WebShadowPrediction(
        fixture=WebShadowFixture(
            match_id="web:wta:test:1",
            tour="WTA",
            tournament="Test Open",
            round="F",
            surface="Hard",
            scheduled_start="2026-09-20T12:00:00+00:00",
            player_a="Alpha",
            player_b="Beta",
            source_url="https://example.com/fixture",
            source_observed_at="2026-09-19T10:00:00+00:00",
        ),
        committed_at="2026-09-19T10:05:00+00:00",
        p_player_a=0.7,
        p_player_b=0.3,
        model_source_sha="a" * 40,
        input_manifest_sha256="b" * 64,
    ).record()
    path.write_text(json.dumps(record), encoding="utf-8")
    return path, record


def test_settlement_runner_scores_frozen_prediction(monkeypatch, tmp_path: Path) -> None:
    prediction_path, prediction = _prediction(tmp_path)
    result_path = tmp_path / "web-shadow/results/test.json"
    result_path.parent.mkdir(parents=True)
    result_path.write_text(
        json.dumps(
            {
                "prediction_path": prediction_path.relative_to(tmp_path).as_posix(),
                "expected_prediction_record_sha256": prediction["record_sha256"],
                "winner": "Alpha",
                "status": "COMPLETED",
                "result_source_url": "https://example.com/result",
                "result_observed_at": "2026-09-20T15:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    output = tmp_path / "settlement.json"
    settlement = runner.settle_from_result_file(
        result_path=Path("web-shadow/results/test.json"),
        output_path=output,
    )

    assert settlement["prediction_correct"] is True
    assert settlement["winner"] == "Alpha"
    assert settlement["production_eligible"] is False
    assert settlement["prediction_record_sha256"] == prediction["record_sha256"]
    assert output.is_file()


def test_settlement_runner_rejects_prediction_sha_drift(
    monkeypatch, tmp_path: Path
) -> None:
    prediction_path, _ = _prediction(tmp_path)
    result_path = tmp_path / "web-shadow/results/test.json"
    result_path.parent.mkdir(parents=True)
    result_path.write_text(
        json.dumps(
            {
                "prediction_path": prediction_path.relative_to(tmp_path).as_posix(),
                "expected_prediction_record_sha256": "0" * 64,
                "winner": "Alpha",
                "status": "COMPLETED",
                "result_source_url": "https://example.com/result",
                "result_observed_at": "2026-09-20T15:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValueError, match="prediction SHA"):
        runner.settle_from_result_file(
            result_path=Path("web-shadow/results/test.json"),
            output_path=tmp_path / "settlement.json",
        )


def test_settlement_runner_accepts_official_run_scoped_prediction(
    monkeypatch,
    tmp_path: Path,
) -> None:
    legacy_path, prediction = _prediction(tmp_path)
    official_path = (
        tmp_path
        / "web-shadow/slates/test-run/predictions/test.json"
    )
    official_path.parent.mkdir(parents=True)
    official_path.write_text(legacy_path.read_text(encoding="utf-8"), encoding="utf-8")

    result_path = tmp_path / "web-shadow/results/test-official.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(
        json.dumps(
            {
                "prediction_path": official_path.relative_to(tmp_path).as_posix(),
                "expected_prediction_record_sha256": prediction["record_sha256"],
                "winner": "Alpha",
                "status": "COMPLETED",
                "result_source_url": "https://example.com/result",
                "result_observed_at": "2026-09-20T15:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    settlement = runner.settle_from_result_file(
        result_path=Path("web-shadow/results/test-official.json"),
        output_path=tmp_path / "settlement-official.json",
    )

    assert settlement["prediction_correct"] is True
    assert settlement["prediction_record_sha256"] == prediction["record_sha256"]
