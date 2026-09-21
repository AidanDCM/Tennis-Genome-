from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from scripts.validate_web_shadow_scorecard import (
    _compute_baseline_comparison,
    _settlement_is_evaluation_eligible,
    validate_web_shadow_scorecard,
)


def test_repository_web_shadow_scorecard_is_valid() -> None:
    summary = validate_web_shadow_scorecard(
        scorecard_path=Path("web-shadow/scorecard.json"),
        repo_root=Path("."),
    )
    assert summary == {
        "official_slate_count": 5,
        "official_match_count": 20,
        "pending_match_count": 13,
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
    assert scorecard["official_slate_count"] == 5
    assert scorecard["pending_match_count"] == 13
    assert scorecard["settled_match_count"] == 7
    assert scorecard["slates"][-1]["status"] == "PENDING_SETTLEMENT"
    assert len(scorecard["slates"][-1]["predictions"]) == 2
    assert scorecard["metrics"]["settled_match_count"] == 7


def test_pending_scorecard_has_prospective_elo_baselines() -> None:
    scorecard = json.loads(
        Path("web-shadow/scorecard.json").read_text(encoding="utf-8")
    )
    baseline_entries = [
        entry
        for slate in scorecard["slates"]
        for entry in slate["predictions"]
        if "baseline_path" in entry
    ]
    assert scorecard["baseline_match_count"] == 13
    assert len(baseline_entries) == 13
    assert all(entry["status"] == "PENDING" for entry in baseline_entries)
    assert "baseline_comparison" not in scorecard


def test_scorecard_rejects_baseline_digest_drift(tmp_path: Path) -> None:
    import shutil

    scorecard = json.loads(
        Path("web-shadow/scorecard.json").read_text(encoding="utf-8")
    )
    entry = next(
        entry
        for slate in scorecard["slates"]
        for entry in slate["predictions"]
        if "baseline_path" in entry
    )
    baseline_path = Path(entry["baseline_path"])

    fake_root = tmp_path / "repo"
    fake_scorecard = fake_root / "web-shadow/scorecard.json"
    fake_scorecard.parent.mkdir(parents=True)
    fake_scorecard.write_text(json.dumps(scorecard), encoding="utf-8")
    shutil.copytree("web-shadow/slates", fake_root / "web-shadow/slates")
    shutil.copytree("web-shadow/results", fake_root / "web-shadow/results")

    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    baseline["record_sha256"] = "0" * 64
    (fake_root / baseline_path).write_text(json.dumps(baseline), encoding="utf-8")

    with pytest.raises(ValueError, match="baseline .* record digest mismatch"):
        validate_web_shadow_scorecard(
            scorecard_path=fake_scorecard,
            repo_root=fake_root,
        )


def test_scorecard_rejects_baseline_probability_drift(tmp_path: Path) -> None:
    import hashlib
    import shutil

    scorecard = json.loads(
        Path("web-shadow/scorecard.json").read_text(encoding="utf-8")
    )
    entry = next(
        entry
        for slate in scorecard["slates"]
        for entry in slate["predictions"]
        if "baseline_path" in entry
    )
    baseline_path = Path(entry["baseline_path"])

    fake_root = tmp_path / "repo"
    fake_scorecard = fake_root / "web-shadow/scorecard.json"
    fake_scorecard.parent.mkdir(parents=True)
    fake_scorecard.write_text(json.dumps(scorecard), encoding="utf-8")
    shutil.copytree("web-shadow/slates", fake_root / "web-shadow/slates")
    shutil.copytree("web-shadow/results", fake_root / "web-shadow/results")

    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    baseline["p_player_a"] = 0.99
    unsigned = dict(baseline)
    unsigned.pop("record_sha256", None)
    baseline["record_sha256"] = hashlib.sha256(
        json.dumps(
            unsigned,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    (fake_root / baseline_path).write_text(json.dumps(baseline), encoding="utf-8")

    with pytest.raises(ValueError, match="baseline probability mismatch"):
        validate_web_shadow_scorecard(
            scorecard_path=fake_scorecard,
            repo_root=fake_root,
        )


def test_baseline_comparison_computes_paired_probability_metrics() -> None:
    genome_rows = [
        {
            "p_player_a": 0.8,
            "p_player_b": 0.2,
            "selected_probability": 0.8,
            "actual_player_a_won": True,
            "prediction_correct": True,
        },
        {
            "p_player_a": 0.4,
            "p_player_b": 0.6,
            "selected_probability": 0.6,
            "actual_player_a_won": False,
            "prediction_correct": True,
        },
    ]
    baseline_rows = [
        {
            "p_player_a": 0.6,
            "p_player_b": 0.4,
            "selected_probability": 0.6,
            "actual_player_a_won": True,
            "prediction_correct": True,
        },
        {
            "p_player_a": 0.55,
            "p_player_b": 0.45,
            "selected_probability": 0.55,
            "actual_player_a_won": False,
            "prediction_correct": False,
        },
    ]

    comparison = _compute_baseline_comparison(
        genome_rows=genome_rows,
        baseline_rows=baseline_rows,
    )

    assert comparison["settled_match_count"] == 2
    assert comparison["genome"]["accuracy"] == pytest.approx(1.0)
    assert comparison["baseline"]["accuracy"] == pytest.approx(0.5)
    assert comparison["genome"]["brier_score"] == pytest.approx(0.10)
    assert comparison["baseline"]["brier_score"] == pytest.approx(0.23125)
    assert comparison["brier_improvement_baseline_minus_genome"] == pytest.approx(
        0.13125
    )
    assert comparison["genome"]["log_loss"] == pytest.approx(
        -0.5 * (math.log(0.8) + math.log(0.6))
    )
    assert comparison["baseline"]["log_loss"] == pytest.approx(
        -0.5 * (math.log(0.6) + math.log(0.45))
    )
    assert comparison["log_loss_improvement_baseline_minus_genome"] > 0.0


def test_baseline_comparison_rejects_denominator_drift() -> None:
    row = {
        "p_player_a": 0.6,
        "p_player_b": 0.4,
        "selected_probability": 0.6,
        "actual_player_a_won": True,
        "prediction_correct": True,
    }

    with pytest.raises(ValueError, match="comparison denominators differ"):
        _compute_baseline_comparison(
            genome_rows=[row],
            baseline_rows=[row, row],
        )


def test_baseline_comparison_rejects_empty_cohort() -> None:
    with pytest.raises(ValueError, match="requires at least one settled match"):
        _compute_baseline_comparison(
            genome_rows=[],
            baseline_rows=[],
        )


def test_scorecard_rejects_settlement_link_hash_drift(tmp_path: Path) -> None:
    scorecard = json.loads(
        Path("web-shadow/scorecard.json").read_text(encoding="utf-8")
    )
    scorecard["slates"][0]["predictions"][0]["settlement_record_sha256"] = "0" * 64
    path = tmp_path / "scorecard.json"
    path.write_text(json.dumps(scorecard), encoding="utf-8")

    with pytest.raises(ValueError, match="scorecard settlement SHA mismatch"):
        validate_web_shadow_scorecard(
            scorecard_path=path,
            repo_root=Path("."),
        )


def test_scorecard_rejects_result_score_tampering(tmp_path: Path) -> None:
    import shutil

    scorecard = json.loads(
        Path("web-shadow/scorecard.json").read_text(encoding="utf-8")
    )
    entry = scorecard["slates"][0]["predictions"][0]
    settlement_path = Path(entry["settlement_path"])
    settlement = json.loads(settlement_path.read_text(encoding="utf-8"))
    result_path = Path(settlement["result_record_path"])

    fake_root = tmp_path / "repo"
    fake_scorecard = fake_root / "web-shadow/scorecard.json"
    fake_scorecard.parent.mkdir(parents=True)
    fake_scorecard.write_text(json.dumps(scorecard), encoding="utf-8")
    shutil.copytree("web-shadow/slates", fake_root / "web-shadow/slates")
    shutil.copytree("web-shadow/results", fake_root / "web-shadow/results")

    result = json.loads(result_path.read_text(encoding="utf-8"))
    result["score"] = "0-6 0-6"
    (fake_root / result_path).write_text(json.dumps(result), encoding="utf-8")

    with pytest.raises(ValueError, match="scorecard result SHA mismatch"):
        validate_web_shadow_scorecard(
            scorecard_path=fake_scorecard,
            repo_root=fake_root,
        )


@pytest.mark.parametrize(
    ("status", "eligible"),
    [
        ("COMPLETED", True),
        ("RETIREMENT", False),
        ("WALKOVER", False),
        ("DEFAULTED", False),
    ],
)
def test_scorecard_metrics_only_use_completed_settlements(
    status: str,
    eligible: bool,
) -> None:
    assert _settlement_is_evaluation_eligible({"status": status}) is eligible
