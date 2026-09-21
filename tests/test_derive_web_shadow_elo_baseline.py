from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import pytest

from scripts.derive_web_shadow_elo_baseline import (
    derive_elo_baseline,
    derive_elo_baseline_candidate,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    matchup = tmp_path / "matchup-input.json"
    matchup.write_text(
        json.dumps(
            {
                "match_id": "web:wta:test:1",
                "player_a_id": "wta:id:100",
                "player_b_id": "wta:id:200",
                "foundational": {"elo_logit": math.log(3.0)},
            }
        ),
        encoding="utf-8",
    )
    manifest = tmp_path / "local-input-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "production_eligible": False,
                "matchup_input_sha256": _sha(matchup),
            }
        ),
        encoding="utf-8",
    )
    prediction = tmp_path / "prediction.json"
    prediction.write_text(
        json.dumps(
            {
                "record_type": "WEB_SHADOW_PREDICTION",
                "production_eligible": False,
                "record_sha256": "a" * 64,
                "player_a_id": "wta:id:100",
                "player_b_id": "wta:id:200",
                "fixture": {
                    "match_id": "web:wta:test:1",
                    "player_a": "Alpha",
                    "player_b": "Beta",
                },
            }
        ),
        encoding="utf-8",
    )
    return matchup, manifest, prediction


def test_derive_elo_baseline_is_artifact_bound(tmp_path: Path) -> None:
    matchup, manifest, prediction = _fixture(tmp_path)
    output = tmp_path / "baseline.json"

    record = derive_elo_baseline(
        matchup_input_path=matchup,
        local_input_manifest_path=manifest,
        prediction_path=prediction,
        slate_id="test-run",
        artifact_id=123,
        artifact_sha256="b" * 64,
        output_path=output,
    )

    assert record["record_type"] == "WEB_SHADOW_BASELINE"
    assert record["baseline_name"] == "overall_elo_v1"
    assert record["p_player_a"] == pytest.approx(0.75)
    assert record["p_player_b"] == pytest.approx(0.25)
    assert record["selected_player"] == "Alpha"
    assert record["prediction_record_sha256"] == "a" * 64
    assert record["artifact_id"] == 123
    assert record["artifact_sha256"] == "b" * 64
    assert record["production_eligible"] is False
    assert output.is_file()


def test_derive_elo_baseline_rejects_matchup_hash_drift(tmp_path: Path) -> None:
    matchup, manifest, prediction = _fixture(tmp_path)
    matchup.write_text(
        json.dumps(
            {
                "match_id": "web:wta:test:1",
                "player_a_id": "wta:id:100",
                "player_b_id": "wta:id:200",
                "foundational": {"elo_logit": 0.0},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="matchup input SHA differs"):
        derive_elo_baseline(
            matchup_input_path=matchup,
            local_input_manifest_path=manifest,
            prediction_path=prediction,
            slate_id="test-run",
            artifact_id=123,
            artifact_sha256="b" * 64,
            output_path=tmp_path / "baseline.json",
        )


def test_derive_elo_baseline_rejects_identity_drift(tmp_path: Path) -> None:
    matchup, manifest, prediction = _fixture(tmp_path)
    payload = json.loads(prediction.read_text(encoding="utf-8"))
    payload["player_b_id"] = "wta:id:999"
    prediction.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="player B identity differs"):
        derive_elo_baseline(
            matchup_input_path=matchup,
            local_input_manifest_path=manifest,
            prediction_path=prediction,
            slate_id="test-run",
            artifact_id=123,
            artifact_sha256="b" * 64,
            output_path=tmp_path / "baseline.json",
        )


def test_derive_elo_baseline_candidate_freezes_preartifact_state(
    tmp_path: Path,
) -> None:
    matchup, manifest, prediction = _fixture(tmp_path)
    output = tmp_path / "baseline-candidate.json"

    record = derive_elo_baseline_candidate(
        matchup_input_path=matchup,
        local_input_manifest_path=manifest,
        prediction_path=prediction,
        output_path=output,
    )

    assert record["record_type"] == "WEB_SHADOW_BASELINE_CANDIDATE"
    assert record["schema_version"] == "tennis-genome-web-shadow-baseline-candidate-v1"
    assert record["baseline_name"] == "overall_elo_v1"
    assert record["match_id"] == "web:wta:test:1"
    assert record["prediction_record_sha256"] == "a" * 64
    assert record["matchup_input_sha256"] == _sha(matchup)
    assert record["p_player_a"] == pytest.approx(0.75)
    assert record["p_player_b"] == pytest.approx(0.25)
    assert record["selected_player"] == "Alpha"
    assert record["production_eligible"] is False
    assert "artifact_id" not in record
    assert "artifact_sha256" not in record
    assert output.is_file()


def test_final_baseline_matches_candidate_values(tmp_path: Path) -> None:
    matchup, manifest, prediction = _fixture(tmp_path)
    candidate = derive_elo_baseline_candidate(
        matchup_input_path=matchup,
        local_input_manifest_path=manifest,
        prediction_path=prediction,
        output_path=tmp_path / "candidate.json",
    )
    baseline = derive_elo_baseline(
        matchup_input_path=matchup,
        local_input_manifest_path=manifest,
        prediction_path=prediction,
        slate_id="test-run",
        artifact_id=123,
        artifact_sha256="b" * 64,
        output_path=tmp_path / "baseline.json",
    )

    for key in (
        "match_id",
        "prediction_record_sha256",
        "matchup_input_sha256",
        "elo_logit",
        "p_player_a",
        "p_player_b",
        "selected_player",
    ):
        assert baseline[key] == candidate[key]
