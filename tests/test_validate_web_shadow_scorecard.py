from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.validate_web_shadow_scorecard import validate_web_shadow_scorecard


def test_repository_web_shadow_scorecard_is_valid() -> None:
    summary = validate_web_shadow_scorecard(
        scorecard_path=Path("web-shadow/scorecard.json"),
        repo_root=Path("."),
    )
    assert summary == {
        "official_slate_count": 3,
        "official_match_count": 16,
        "pending_match_count": 9,
        "settled_match_count": 7,
    }


def test_scorecard_rejects_probability_drift(tmp_path: Path) -> None:
    scorecard = json.loads(
        Path("web-shadow/scorecard.json").read_text(encoding="utf-8")
    )
    scorecard["slates"][0]["predictions"][0]["selected_probability"] = 0.99
    path = tmp_path / "scorecard.json"
    path.write_text(json.dumps(scorecard), encoding="utf-8")

    with pytest.raises(ValueError, match="selected probability mismatch"):
        validate_web_shadow_scorecard(
            scorecard_path=path,
            repo_root=Path("."),
        )


def test_scorecard_rejects_prediction_sha_drift(tmp_path: Path) -> None:
    scorecard = json.loads(
        Path("web-shadow/scorecard.json").read_text(encoding="utf-8")
    )
    scorecard["slates"][0]["predictions"][0]["prediction_record_sha256"] = "0" * 64
    path = tmp_path / "scorecard.json"
    path.write_text(json.dumps(scorecard), encoding="utf-8")

    with pytest.raises(ValueError, match="prediction SHA mismatch"):
        validate_web_shadow_scorecard(
            scorecard_path=path,
            repo_root=Path("."),
        )


def test_repository_scorecard_publishes_first_forward_metrics() -> None:
    scorecard = json.loads(
        Path("web-shadow/scorecard.json").read_text(encoding="utf-8")
    )
    metrics = scorecard["metrics"]
    assert metrics["settled_match_count"] == 7
    assert metrics["correct_prediction_count"] == 5
    assert metrics["accuracy"] == pytest.approx(5 / 7)
    assert metrics["brier_score"] == pytest.approx(0.24063277730212165)
    assert metrics["log_loss"] == pytest.approx(0.6771440099091525)
    assert metrics["mean_selected_probability"] == pytest.approx(
        0.5930637866971404
    )


def test_scorecard_rejects_metric_drift(tmp_path: Path) -> None:
    scorecard = json.loads(
        Path("web-shadow/scorecard.json").read_text(encoding="utf-8")
    )
    scorecard["metrics"]["accuracy"] = 1.0
    path = tmp_path / "scorecard.json"
    path.write_text(json.dumps(scorecard), encoding="utf-8")

    with pytest.raises(ValueError, match="scorecard metric mismatch"):
        validate_web_shadow_scorecard(
            scorecard_path=path,
            repo_root=Path("."),
        )


def test_scorecard_rejects_settlement_digest_drift(tmp_path: Path) -> None:
    scorecard = json.loads(
        Path("web-shadow/scorecard.json").read_text(encoding="utf-8")
    )
    settlement_path = Path(
        scorecard["slates"][0]["predictions"][0]["settlement_path"]
    )
    settlement = json.loads(settlement_path.read_text(encoding="utf-8"))
    settlement["record_sha256"] = "0" * 64

    fake_root = tmp_path / "repo"
    fake_scorecard = fake_root / "web-shadow/scorecard.json"
    fake_scorecard.parent.mkdir(parents=True)
    fake_scorecard.write_text(json.dumps(scorecard), encoding="utf-8")

    import shutil

    shutil.copytree("web-shadow/slates", fake_root / "web-shadow/slates")
    shutil.copytree("web-shadow/results", fake_root / "web-shadow/results")
    tampered_path = fake_root / settlement_path
    tampered_path.write_text(json.dumps(settlement), encoding="utf-8")

    with pytest.raises(ValueError, match="settlement .* record digest mismatch"):
        validate_web_shadow_scorecard(
            scorecard_path=fake_scorecard,
            repo_root=fake_root,
        )


def test_scorecard_retains_settled_metrics_with_pending_slate() -> None:
    scorecard = json.loads(
        Path("web-shadow/scorecard.json").read_text(encoding="utf-8")
    )
    assert scorecard["official_slate_count"] == 3
    assert scorecard["pending_match_count"] == 9
    assert scorecard["settled_match_count"] == 7
    assert scorecard["slates"][-1]["status"] == "PENDING_SETTLEMENT"
    assert len(scorecard["slates"][-1]["predictions"]) == 9
    assert scorecard["metrics"]["settled_match_count"] == 7
