from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.audit_api_tennis_retained_history import audit_retained_history
from tests.test_api_tennis_enrichment import _finished_row


def _capture(root: Path, rows: list[dict], *, tour: str = "wta") -> Path:
    root.mkdir()
    hashes = {}
    for name in ("atp", "wta"):
        raw = json.dumps({"success": 1, "result": rows if name == tour else []}).encode()
        (root / f"raw-{name}-fixtures.json").write_bytes(raw)
        hashes[f"raw_{name}_sha256"] = hashlib.sha256(raw).hexdigest()
    audit = {
        "date_start": "2026-09-15",
        "date_stop": "2026-09-17",
        "event_key_count": len(rows),
        **hashes,
    }
    manifest = {
        "provider_request_count": 2,
        "fixture_count": len(rows),
        "historical_actual_start_admissible": False,
        **hashes,
    }
    for name, payload in (("audit", audit), ("manifest", manifest)):
        (root / f"{name}.json").write_text(json.dumps(payload), encoding="utf-8")
    receipt = {
        "schema_version": "tennis-genome-api-tennis-trial-backfill-receipt-v1",
        "repository": "AidanDCM/Tennis-Genome-",
        "workflow_run_id": 123,
        "date_start": "2026-09-15",
        "date_stop": "2026-09-17",
        "observed_at_utc": "2026-09-18T12:00:00+00:00",
        "provider_request_count": 2,
        "fixture_count": len(rows),
        **hashes,
        "manifest_sha256": hashlib.sha256((root / "manifest.json").read_bytes()).hexdigest(),
        "audit_sha256": hashlib.sha256((root / "audit.json").read_bytes()).hexdigest(),
    }
    (root / "github-receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
    return root


def _conflicting_row(*, event_key: int = 101, date: str = "2026-09-16") -> dict:
    row = _finished_row(event_key=event_key, date=date)
    for stat in row["statistics"]:
        if stat["player_key"] == 11 and stat["stat_name"] == "Service Points Won":
            stat["stat_won"] = 31
    return row


def test_retained_audit_accounts_for_every_finished_record_and_quarantines_conflicts(tmp_path):
    good = _finished_row(event_key=100)
    missing = _finished_row(event_key=102)
    missing["statistics"] = []
    root = _capture(tmp_path / "capture", [good, _conflicting_row(), missing])
    report = audit_retained_history([root])
    counts = report["tours"]["WTA"]["counts"]
    assert counts["finished"] == counts["parsed"] + counts["unparseable_enrichment"] == 3
    assert counts["parsed"] == counts["point_consistent"] + counts["point_inconsistent"] == 2
    assert counts["legacy_bridge_accepted"] == 2
    assert [row["event_key"] for row in report["quarantined"]] == [101, 102]
    assert report["provider_calls_this_audit"] == 0
    assert report["production_eligible"] is False
    assert report["captures"][0]["live_github_or_provider_authentication_performed"] is False


@pytest.mark.parametrize("filename", ["raw-wta-fixtures.json", "manifest.json", "audit.json"])
def test_retained_audit_rejects_modified_evidence(tmp_path, filename):
    root = _capture(tmp_path / "capture", [_finished_row()])
    with (root / filename).open("ab") as handle:
        handle.write(b" ")
    with pytest.raises(ValueError, match="SHA mismatch"):
        audit_retained_history([root])


def test_retained_audit_rejects_duplicate_events_across_captures(tmp_path):
    a = _capture(tmp_path / "a", [_finished_row()])
    b = _capture(tmp_path / "b", [_finished_row()])
    with pytest.raises(ValueError, match="duplicate event identity"):
        audit_retained_history([a, b])


def test_quarantine_sensitivity_changes_only_later_dates(tmp_path):
    bad = _conflicting_row(event_key=100, date="2026-09-15")
    same_day = _finished_row(event_key=101, date="2026-09-15")
    later = _finished_row(event_key=102, date="2026-09-16")
    root = _capture(tmp_path / "capture", [bad, same_day, later])
    report = audit_retained_history([root], sensitivity=True)
    sensitivity = report["component_sensitivity"]
    changes = {row["event_key"]: row for row in sensitivity["tours"]["WTA"]["largest_changes"]}
    assert changes[100]["absolute_difference"] == 0
    assert changes[101]["absolute_difference"] == 0
    assert changes[102]["absolute_difference"] > 0
    assert sensitivity["target_outcomes_consumed"] is False
    assert sensitivity["full_stack_comparison"] is False
    assert sensitivity["predictive_performance_claim"] is False
