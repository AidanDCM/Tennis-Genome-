from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import settle_web_shadow_result_batch as batch
from tennis_genome.prospective.web_shadow import WebShadowFixture, WebShadowPrediction


def _prediction(
    root: Path,
    *,
    slate_id: str,
    stem: str,
    match_id: str,
    player_a: str,
    player_b: str,
    p_player_a: float,
) -> tuple[Path, dict[str, object]]:
    path = root / f"web-shadow/slates/{slate_id}/predictions/{stem}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    record = WebShadowPrediction(
        fixture=WebShadowFixture(
            match_id=match_id,
            tour="WTA",
            tournament="Test Open",
            round="R32",
            surface="Hard",
            scheduled_start="2026-09-22T12:00:00+00:00",
            player_a=player_a,
            player_b=player_b,
            source_url="https://example.com/fixture",
            source_observed_at="2026-09-21T10:00:00+00:00",
        ),
        committed_at="2026-09-21T10:05:00+00:00",
        p_player_a=p_player_a,
        p_player_b=1.0 - p_player_a,
        model_source_sha="a" * 40,
        input_manifest_sha256="b" * 64,
    ).record()
    path.write_text(json.dumps(record), encoding="utf-8")
    return path, record


def _write_scorecard(
    root: Path,
    *,
    slate_id: str,
    entries: list[tuple[Path, dict[str, object], str]],
) -> Path:
    predictions = []
    for path, record, match_id in entries:
        predictions.append(
            {
                "match_id": match_id,
                "prediction_path": path.relative_to(root).as_posix(),
                "prediction_record_sha256": record["record_sha256"],
                "status": "PENDING",
            }
        )
    scorecard = {
        "schema_version": "tennis-genome-web-shadow-scorecard-v1",
        "production_eligible": False,
        "slates": [
            {
                "slate_id": slate_id,
                "predictions": predictions,
            }
        ],
    }
    path = root / "web-shadow/scorecard.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(scorecard), encoding="utf-8")
    return path


def _write_result(
    root: Path,
    *,
    stem: str,
    prediction_path: Path,
    prediction: dict[str, object],
    match_id: str,
    winner: str,
    status: str = "COMPLETED",
) -> Path:
    path = root / f"web-shadow/results/{stem}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "match_id": match_id,
                "prediction_path": prediction_path.relative_to(root).as_posix(),
                "expected_prediction_record_sha256": prediction["record_sha256"],
                "winner": winner,
                "status": status,
                "score": "6-3 6-4",
                "result_source_url": "https://example.com/result",
                "result_observed_at": "2026-09-22T16:00:00+00:00",
                "production_eligible": False,
            }
        ),
        encoding="utf-8",
    )
    return path


def test_batch_settles_pending_official_predictions(
    monkeypatch,
    tmp_path: Path,
) -> None:
    slate_id = "test-run"
    first_path, first = _prediction(
        tmp_path,
        slate_id=slate_id,
        stem="first",
        match_id="web:wta:test:1",
        player_a="Alpha",
        player_b="Beta",
        p_player_a=0.7,
    )
    second_path, second = _prediction(
        tmp_path,
        slate_id=slate_id,
        stem="second",
        match_id="web:wta:test:2",
        player_a="Gamma",
        player_b="Delta",
        p_player_a=0.6,
    )
    scorecard = _write_scorecard(
        tmp_path,
        slate_id=slate_id,
        entries=[
            (first_path, first, "web:wta:test:1"),
            (second_path, second, "web:wta:test:2"),
        ],
    )
    first_result = _write_result(
        tmp_path,
        stem="first",
        prediction_path=first_path,
        prediction=first,
        match_id="web:wta:test:1",
        winner="Alpha",
    )
    second_result = _write_result(
        tmp_path,
        stem="second",
        prediction_path=second_path,
        prediction=second,
        match_id="web:wta:test:2",
        winner="Delta",
    )
    manifest = tmp_path / "web-shadow/active-results.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "tennis-genome-web-shadow-result-batch-v1",
                "result_paths": [
                    first_result.relative_to(tmp_path).as_posix(),
                    second_result.relative_to(tmp_path).as_posix(),
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    summary = batch.settle_web_shadow_result_batch(
        manifest_path=Path("web-shadow/active-results.json"),
        scorecard_path=scorecard.relative_to(tmp_path),
        output_root=Path("batch-output"),
    )

    assert summary["requested_result_count"] == 2
    assert summary["settlement_count"] == 2
    assert summary["evaluation_eligible_count"] == 2
    assert summary["excluded_noncompleted_count"] == 0
    assert summary["correct_prediction_count"] == 1
    assert summary["accuracy"] == pytest.approx(0.5)
    assert summary["production_eligible"] is False
    assert len(summary["results"][0]["result_record_sha256"]) == 64
    assert all(row["evaluation_eligible"] is True for row in summary["results"])
    assert (tmp_path / "batch-output/test-run/settlements/first.json").is_file()
    assert (tmp_path / "batch-output/test-run/settlements/second.json").is_file()


def test_batch_rejects_duplicate_result_paths(monkeypatch, tmp_path: Path) -> None:
    slate_id = "test-run"
    prediction_path, prediction = _prediction(
        tmp_path,
        slate_id=slate_id,
        stem="first",
        match_id="web:wta:test:1",
        player_a="Alpha",
        player_b="Beta",
        p_player_a=0.7,
    )
    scorecard = _write_scorecard(
        tmp_path,
        slate_id=slate_id,
        entries=[(prediction_path, prediction, "web:wta:test:1")],
    )
    result = _write_result(
        tmp_path,
        stem="first",
        prediction_path=prediction_path,
        prediction=prediction,
        match_id="web:wta:test:1",
        winner="Alpha",
    )
    manifest = tmp_path / "web-shadow/active-results.json"
    relative = result.relative_to(tmp_path).as_posix()
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "tennis-genome-web-shadow-result-batch-v1",
                "result_paths": [relative, relative],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValueError, match="duplicate result path"):
        batch.settle_web_shadow_result_batch(
            manifest_path=Path("web-shadow/active-results.json"),
            scorecard_path=scorecard.relative_to(tmp_path),
            output_root=Path("batch-output"),
        )


def test_batch_rejects_nonpending_prediction(monkeypatch, tmp_path: Path) -> None:
    slate_id = "test-run"
    prediction_path, prediction = _prediction(
        tmp_path,
        slate_id=slate_id,
        stem="first",
        match_id="web:wta:test:1",
        player_a="Alpha",
        player_b="Beta",
        p_player_a=0.7,
    )
    scorecard = _write_scorecard(
        tmp_path,
        slate_id=slate_id,
        entries=[(prediction_path, prediction, "web:wta:test:1")],
    )
    payload = json.loads(scorecard.read_text(encoding="utf-8"))
    payload["slates"][0]["predictions"][0]["status"] = "SETTLED"
    scorecard.write_text(json.dumps(payload), encoding="utf-8")
    result = _write_result(
        tmp_path,
        stem="first",
        prediction_path=prediction_path,
        prediction=prediction,
        match_id="web:wta:test:1",
        winner="Alpha",
    )
    manifest = tmp_path / "web-shadow/active-results.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "tennis-genome-web-shadow-result-batch-v1",
                "result_paths": [result.relative_to(tmp_path).as_posix()],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    with pytest.raises(RuntimeError, match="no pending predictions"):
        batch.settle_web_shadow_result_batch(
            manifest_path=Path("web-shadow/active-results.json"),
            scorecard_path=scorecard.relative_to(tmp_path),
            output_root=Path("batch-output"),
        )


def test_batch_retains_retirement_but_excludes_it_from_metrics(
    monkeypatch,
    tmp_path: Path,
) -> None:
    slate_id = "test-run"
    prediction_path, prediction = _prediction(
        tmp_path,
        slate_id=slate_id,
        stem="retired",
        match_id="web:wta:test:retired",
        player_a="Alpha",
        player_b="Beta",
        p_player_a=0.7,
    )
    scorecard = _write_scorecard(
        tmp_path,
        slate_id=slate_id,
        entries=[(prediction_path, prediction, "web:wta:test:retired")],
    )
    result = _write_result(
        tmp_path,
        stem="retired",
        prediction_path=prediction_path,
        prediction=prediction,
        match_id="web:wta:test:retired",
        winner="Alpha",
        status="RETIREMENT",
    )
    manifest = tmp_path / "web-shadow/active-results.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "tennis-genome-web-shadow-result-batch-v1",
                "result_paths": [result.relative_to(tmp_path).as_posix()],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    summary = batch.settle_web_shadow_result_batch(
        manifest_path=Path("web-shadow/active-results.json"),
        scorecard_path=scorecard.relative_to(tmp_path),
        output_root=Path("batch-output"),
    )

    assert summary["settlement_count"] == 1
    assert summary["evaluation_eligible_count"] == 0
    assert summary["excluded_noncompleted_count"] == 1
    assert summary["correct_prediction_count"] == 0
    assert summary["accuracy"] is None
    assert summary["results"][0]["evaluation_eligible"] is False
