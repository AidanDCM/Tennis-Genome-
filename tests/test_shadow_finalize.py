from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from scripts.finalize_live_shadows import build as build_live_finalization
from tennis_genome.research_workbench.component_challengers import (
    build_component_shadow_bundle,
    canonical_record_json,
)
from tennis_genome.research_workbench.shadow_finalize import (
    binding_from_verified_dossier,
    finalize_shadow_match,
)

CUTOFF = datetime(2026, 9, 16, 16, 30, tzinfo=UTC)
START = datetime(2026, 9, 16, 19, 0, tzinfo=UTC)
ACTUAL_START = datetime(2026, 9, 16, 19, 7, tzinfo=UTC)
SETTLED = datetime(2026, 9, 16, 21, 0, tzinfo=UTC)
BUNDLE_SHA = "3" * 64
CODE_SHA = "4" * 64
PREDICTION_SHA = "5" * 64


def _dossier() -> dict[str, object]:
    return {
        "schema_version": "full-stack-forward-verified-settlement-dossier-v1",
        "prediction_artifact_id": 12345,
        "prediction_record_sha256": PREDICTION_SHA,
        "match_id": "sr:sport_event:74574088",
        "player_a_id": "211684",
        "player_b_id": "214452",
        "winner_player_id": "214452",
        "p_player_a": 0.604,
        "p_player_b": 0.396,
        "actual_start": ACTUAL_START.isoformat(),
        "provider_status": "closed",
        "finish_status": "COMPLETED",
        "timing_status": "PRE_START_VERIFIED",
        "anchor_status": "PRE_START_ANCHORED",
        "primary_evaluation_eligible": True,
        "period_scores": [
            {"number": 1, "type": "set", "home_score": 4, "away_score": 6},
            {"number": 2, "type": "set", "home_score": 3, "away_score": 6},
        ],
    }


def _component_bundle():
    prediction_dossier = {
        "calculation": {
            "player_a_id": "211684",
            "player_b_id": "214452",
            "production_bundle_sha256": BUNDLE_SHA,
            "prediction": {
                "prediction_id": "FULL-STACK-FORWARD-TEST-001",
                "match_id": "sr:sport_event:74574088",
                "tour": "WTA",
                "model_version": "TGE-Independent-v1",
                "prediction_cutoff_at": CUTOFF.isoformat(),
                "p_player_a": 0.604,
                "p_player_b": 0.396,
                "source_manifest_hashes": ["1" * 64, "2" * 64],
                "component_probabilities": {
                    "strict_core_v1": 0.72,
                    "strict_core_geometry_historical_alignment_k100": 0.614,
                    "pointsim_conditional_meta_input": 0.50,
                    "pointsim_conditional_meta_final": 0.604,
                },
                "diagnostics": {
                    "model_disagreement": 0.22,
                    "alignment_missing_fraction": 0.30,
                    "pointsim_min_prior_point_history": 300,
                },
            },
        }
    }
    matchup = {
        "match_id": "sr:sport_event:74574088",
        "player_a_id": "211684",
        "player_b_id": "214452",
        "foundational": {"serve_return_edge": 0.02, "h2h_edge": 0.10},
    }
    target = {
        "event_id": "sr:sport_event:74574088",
        "scheduled_start": START.isoformat(),
    }
    return build_component_shadow_bundle(
        prediction_dossier=prediction_dossier,
        matchup_input=matchup,
        target_resolution=target,
        created_at=CUTOFF + timedelta(minutes=5),
        implementation_sha256=CODE_SHA,
        registered_at=CUTOFF - timedelta(days=1),
    )


def _binding(**updates: object):
    dossier = _dossier()
    dossier.update(updates)
    serialized = json.dumps(dossier, sort_keys=True).encode("utf-8")
    return binding_from_verified_dossier(
        dossier=dossier,
        verified_settlement_artifact_id=999,
        verified_settlement_dossier_sha256=hashlib.sha256(serialized).hexdigest(),
    )


def test_verified_binding_rejects_nonqualified_or_nonterminal_settlement() -> None:
    with pytest.raises(ValidationError, match="primary-evaluation eligible"):
        _binding(primary_evaluation_eligible=False)
    with pytest.raises(ValidationError, match="must be closed"):
        _binding(provider_status="live")
    with pytest.raises(ValidationError, match="must be COMPLETED"):
        _binding(finish_status="RETIRED")


def test_finalize_shadow_match_scores_all_component_views_and_builds_atlas() -> None:
    component = _component_bundle()
    binding = _binding()
    result = finalize_shadow_match(
        predictions=component.predictions,
        snapshot=component.snapshot,
        binding=binding,
        source_shadow_artifact_id=777,
        settled_at=SETTLED,
    )

    assert len(result.settlements) == 3
    assert len(result.failure_atlas) == 3
    assert len(result.league_table) == 3
    assert all(item.correctness == 0 for item in result.settlements)
    by_id = {row.challenger_id: row for row in result.league_table}
    assert by_id["TGE-SHADOW-IDENTITY-V1"].mean_brier == pytest.approx(0.604**2)
    assert by_id["TGE-SHADOW-GEOMETRY-V1"].mean_brier == pytest.approx(0.614**2)
    assert by_id["TGE-SHADOW-POINTSIM-V1"].mean_brier == pytest.approx(0.50**2)
    for atlas in result.failure_atlas:
        assert atlas.evidence_role == "POST_RESULT_DIAGNOSTIC_ONLY"
        assert atlas.pre_match_component_probabilities["strict_core_v1"] == pytest.approx(
            0.72
        )
        assert atlas.post_result_diagnostics["winner_player_id"] == "214452"
        assert "WINNER_MISS" in atlas.deterministic_tags
        assert "HIGH_COMPONENT_DISAGREEMENT" in atlas.deterministic_tags
        assert "HIGH_MODEL_DISAGREEMENT" in atlas.deterministic_tags
        assert "HIGH_MISSINGNESS" in atlas.deterministic_tags
        assert "LOW_POINT_HISTORY" in atlas.deterministic_tags


def test_finalize_requires_exact_champion_identity_probability_and_time() -> None:
    component = _component_bundle()

    with pytest.raises(ValueError, match="orientation differs"):
        finalize_shadow_match(
            predictions=component.predictions,
            snapshot=component.snapshot,
            binding=_binding(player_a_id="wrong"),
            source_shadow_artifact_id=777,
            settled_at=SETTLED,
        )

    with pytest.raises(ValueError, match="identity shadow"):
        finalize_shadow_match(
            predictions=component.predictions,
            snapshot=component.snapshot,
            binding=_binding(p_player_a=0.61, p_player_b=0.39),
            source_shadow_artifact_id=777,
            settled_at=SETTLED,
        )

    with pytest.raises(ValueError, match="cannot predate"):
        finalize_shadow_match(
            predictions=component.predictions,
            snapshot=component.snapshot,
            binding=_binding(),
            source_shadow_artifact_id=777,
            settled_at=ACTUAL_START - timedelta(seconds=1),
        )


def _write_shadow_artifact(root: Path, source_prediction_artifact_id: int = 12345) -> None:
    bundle = _component_bundle()
    (root / "predictions").mkdir(parents=True)
    (root / "anchors").mkdir(parents=True)
    (root / "snapshot.json").write_text(
        canonical_record_json(bundle.snapshot), encoding="utf-8"
    )
    for index, prediction in enumerate(bundle.predictions, start=1):
        (root / "predictions" / f"{prediction.output.challenger_id}.json").write_text(
            canonical_record_json(prediction), encoding="utf-8"
        )
        comment_id = 5000 + index
        payload = {
            "schema_version": "tennis-genome-challenger-shadow-anchor-v1",
            "source_prediction_artifact_id": source_prediction_artifact_id,
            "shadow_prediction_sha256": prediction.semantic_sha256,
            "shadow_record": prediction.canonical_payload(),
        }
        body = "<!-- X -->\n```json\n" + json.dumps(
            payload, sort_keys=True, separators=(",", ":")
        ) + "\n```"
        (root / "anchors" / f"request-{index:02d}.comment.json").write_text(
            json.dumps({"id": comment_id, "body": body}), encoding="utf-8"
        )
        (root / "anchors" / f"request-{index:02d}.comment.json.receipt.json").write_text(
            json.dumps(
                {
                    "comment_id": comment_id,
                    "shadow_prediction_id": prediction.shadow_prediction_id,
                    "shadow_prediction_sha256": prediction.semantic_sha256,
                    "snapshot_sha256": prediction.snapshot_sha256,
                    "registration_sha256": prediction.registration_sha256,
                    "scheduled_start": prediction.scheduled_start.isoformat().replace(
                        "+00:00", "Z"
                    ),
                }
            ),
            encoding="utf-8",
        )


def test_live_finalizer_builds_content_addressed_output_and_checks_dossier_sidecar(
    tmp_path: Path,
) -> None:
    shadow_root = tmp_path / "shadow"
    _write_shadow_artifact(shadow_root)
    dossier_path = tmp_path / "verified-settlement-dossier.json"
    dossier_bytes = (json.dumps(_dossier(), sort_keys=True) + "\n").encode("utf-8")
    dossier_path.write_bytes(dossier_bytes)
    dossier_path.with_suffix(".sha256").write_text(
        hashlib.sha256(dossier_bytes).hexdigest() + "\n", encoding="utf-8"
    )

    manifest = build_live_finalization(
        shadow_root=shadow_root,
        verified_settlement_dossier_path=dossier_path,
        verified_settlement_artifact_id=999,
        source_shadow_artifact_id=777,
        output_dir=tmp_path / "out",
        settled_at=SETTLED,
    )
    assert manifest["source_prediction_artifact_id"] == 12345
    assert len(manifest["shadow_anchor_comment_ids"]) == 3
    assert len(manifest["settlement_sha256"]) == 3
    assert len(manifest["failure_atlas_sha256"]) == 3
    assert (tmp_path / "out" / "finalization-bundle.json").is_file()

    dossier_path.with_suffix(".sha256").write_text("0" * 64 + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="does not match sidecar"):
        build_live_finalization(
            shadow_root=shadow_root,
            verified_settlement_dossier_path=dossier_path,
            verified_settlement_artifact_id=999,
            source_shadow_artifact_id=777,
            output_dir=tmp_path / "bad-out",
            settled_at=SETTLED,
        )
