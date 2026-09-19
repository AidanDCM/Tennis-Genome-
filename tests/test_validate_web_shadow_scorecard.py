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
        "official_slate_count": 1,
        "official_match_count": 5,
        "pending_match_count": 5,
        "settled_match_count": 0,
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
