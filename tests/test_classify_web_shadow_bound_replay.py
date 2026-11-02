from copy import deepcopy

import pytest

from scripts.classify_web_shadow_bound_replay import classify


def _case():
    manifest = {
        "schema_version": "tennis-genome-web-shadow-bound-evidence-v1",
        "production_eligible": False,
        "workflow_run_id": 42,
        "workflow_source_sha": "a" * 40,
        "predicted_target_count": 2,
        "results": [{"match_id": "match-1"}, {"match_id": "match-2"}],
    }
    scorecard = {
        "schema_version": "tennis-genome-web-shadow-scorecard-v1",
        "slates": [{"predictions": [{"match_id": "match-1"}, {"match_id": "match-2"}]}],
    }
    return manifest, scorecard


def test_fully_repeated_run_keeps_original_predictions() -> None:
    manifest, scorecard = _case()
    result = classify(manifest, scorecard, run_id=42, source_sha="a" * 40)
    assert result["status"] == "FULLY_REPEATED"
    assert result["new_match_count"] == 0

    scorecard["slates"] = []
    assert classify(manifest, scorecard, run_id=42, source_sha="a" * 40)["status"] == "NEW"


def test_partial_overlap_and_wrong_source_fail_closed() -> None:
    manifest, scorecard = _case()
    partial = deepcopy(scorecard)
    partial["slates"][0]["predictions"].pop()
    with pytest.raises(ValueError, match="mixes already-frozen and new"):
        classify(manifest, partial, run_id=42, source_sha="a" * 40)
    with pytest.raises(ValueError, match="source SHA mismatch"):
        classify(manifest, scorecard, run_id=42, source_sha="b" * 40)
