from copy import deepcopy

import pytest

from scripts.audit_api_tennis_official_sample_progress import reconcile


def _inputs():
    capture = {
        "workflow_run_id": 42,
        "raw_atp_sha256": "a" * 64,
        "raw_wta_sha256": "b" * 64,
        "receipt_sha256": "c" * 64,
    }
    sample = {
        "schema_version": "api-tennis-official-source-sample-v1",
        "selected_count": 1,
        "selected": [
            {
                "tour": "WTA",
                "event_key": 8,
                "event_date": "2026-10-01",
                "tournament_name": "Sample",
                "player_a_name": "A",
                "player_b_name": "B",
                "player_a_key": 1,
                "player_b_key": 2,
                "capture_workflow_run_id": 42,
            }
        ],
        "captures": [capture],
    }
    identities = {
        "production_admitted": False,
        "captures": [deepcopy(capture)],
        "events": [
            {
                "tour": "WTA",
                "event_key": 8,
                "identity_tier": "BOTH_EXACT",
                "point_disposition": "POINT_CONSISTENT",
            }
        ],
    }
    players = [
        {
            "provider_player_key": key,
            "provider_won": 30,
            "provider_total": 50,
            "official_won": 30,
            "official_total": 50,
            "exact_agreement": True,
        }
        for key in (1, 2)
    ]
    review = {
        "schema_version": "api-tennis-official-point-adjudication-v1",
        "captures": [deepcopy(capture)],
        "case_count": 1,
        "exact_agreement_count": 1,
        "cases": [
            {
                "event_key": 8,
                "event_date": "2026-10-01",
                "source_admission": "RESEARCH_ONLY",
                "official_point_agreement": True,
                "provider_internal_issues": [],
                "players": players,
                "official_url": "https://www.wtatennis.com/example",
            }
        ],
    }
    return sample, identities, review


def test_reconciles_unique_review_and_pending_count() -> None:
    sample, identities, review = _inputs()
    result = reconcile(sample, [review, deepcopy(review)], identities)
    assert result["unique_reviewed_count"] == 1
    assert result["counts"]["SERVICE_POINTS_AGREE"] == 1
    assert result["rows"][0]["production_admitted"] is False


def test_rejects_contradictory_review() -> None:
    sample, identities, review = _inputs()
    conflicting = deepcopy(review)
    conflicting["cases"][0]["official_url"] = "https://www.wtatennis.com/other"
    with pytest.raises(ValueError, match="contradictory"):
        reconcile(sample, [review, conflicting], identities)


def test_rejects_changed_capture_or_point_gate() -> None:
    sample, identities, review = _inputs()
    identities["captures"][0]["raw_wta_sha256"] = "d" * 64
    with pytest.raises(ValueError, match="capture differs"):
        reconcile(sample, [review], identities)
    identities["captures"][0]["raw_wta_sha256"] = "b" * 64
    identities["events"][0]["point_disposition"] = "POINT_CONFLICT"
    with pytest.raises(ValueError, match="point gate"):
        reconcile(sample, [review], identities)
