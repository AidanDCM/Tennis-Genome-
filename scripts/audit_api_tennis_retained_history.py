"""Audit retained fixture captures offline before they can update player state."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from tennis_genome.research_workbench.api_tennis_enrichment import (
    ApiTennisMatchEnrichment,
    api_tennis_point_count_issues,
    parse_api_tennis_match_enrichment,
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path.name}")
    return value


def verify_capture(root: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Verify locally retained bytes against their receipt; no live authentication."""
    manifest_path, audit_path = root / "manifest.json", root / "audit.json"
    manifest, audit = _json(manifest_path), _json(audit_path)
    receipt_path = root / "github-receipt.json"
    if not receipt_path.is_file():
        receipt_path = root.parent / "api-tennis-filtered-range-github-receipt.json"
    receipt = _json(receipt_path)
    schema = receipt.get("schema_version")
    if schema == "tennis-genome-api-tennis-trial-backfill-receipt-v1":
        expected_files = {
            "manifest.json": receipt["manifest_sha256"],
            "audit.json": receipt["audit_sha256"],
        }
    elif schema == "tennis-genome-api-tennis-filtered-range-github-receipt-v1":
        expected_files = {"audit.json": receipt["audit_file_sha256"]}
    else:
        raise ValueError("unsupported retained capture receipt")
    for filename, expected in expected_files.items():
        if _sha((root / filename).read_bytes()) != expected:
            raise ValueError(f"retained {filename} SHA mismatch")
    if receipt.get("repository") != "AidanDCM/Tennis-Genome-":
        raise ValueError("unexpected receipt repository")
    if type(receipt.get("workflow_run_id")) is not int or receipt["workflow_run_id"] <= 0:
        raise ValueError("receipt requires positive workflow run identity")
    start, stop = date.fromisoformat(audit["date_start"]), date.fromisoformat(audit["date_stop"])
    if start > stop:
        raise ValueError("capture date window is inverted")
    if [receipt["date_start"], receipt["date_stop"]] != [start.isoformat(), stop.isoformat()]:
        raise ValueError("capture receipt date window mismatch")
    observed = receipt.get("observed_at_utc", receipt.get("created_at_utc", ""))
    observed_at = datetime.fromisoformat(observed)
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise ValueError("capture observation must be timezone-aware")
    if manifest.get("historical_actual_start_admissible") is not False:
        raise ValueError("scheduled source time must not become actual start")
    if manifest.get("provider_request_count") != 2 or receipt.get("provider_request_count") != 2:
        raise ValueError("unexpected original capture request count")
    rows: list[dict[str, Any]] = []
    hashes: dict[str, str] = {}
    for tour, event_type in (("atp", "Atp Singles"), ("wta", "Wta Singles")):
        raw = (root / f"raw-{tour}-fixtures.json").read_bytes()
        digest = _sha(raw)
        field = f"raw_{tour}_sha256"
        if any(value.get(field) != digest for value in (manifest, audit, receipt)):
            raise ValueError(f"{tour} raw SHA mismatch")
        hashes[field] = digest
        payload = json.loads(raw)
        if not isinstance(payload, dict) or type(payload.get("success")) not in (int, str):
            raise ValueError("invalid provider success response")
        if payload["success"] not in (1, "1") or not isinstance(payload.get("result"), list):
            raise ValueError("provider response did not report a fixture array")
        for row in payload["result"]:
            if not isinstance(row, dict) or row.get("event_type_type") != event_type:
                raise ValueError("retained tour response contains unexpected event type")
            if not start <= date.fromisoformat(row["event_date"]) <= stop:
                raise ValueError("fixture falls outside capture window")
            rows.append(row)
    for value in (manifest, receipt):
        if value.get("fixture_count") != len(rows):
            raise ValueError("receipt/manifest fixture count mismatch")
    if audit.get("event_key_count") != len(rows):
        raise ValueError("audit fixture count mismatch")
    return {
        "workflow_run_id": receipt["workflow_run_id"],
        "date_start": start.isoformat(),
        "date_stop": stop.isoformat(),
        "observed_at": observed,
        "receipt_sha256": _sha(receipt_path.read_bytes()),
        "manifest_file_sha256": _sha(manifest_path.read_bytes()),
        "audit_file_sha256": _sha(audit_path.read_bytes()),
        "fixture_count": len(rows),
        "retained_bytes_verified": True,
        "live_github_or_provider_authentication_performed": False,
        **hashes,
    }, rows


def _legacy_accepted(record: ApiTennisMatchEnrichment) -> bool:
    a, b = record.player_a_stats, record.player_b_stats
    return (
        a.service_points_total == b.return_points_total
        and b.service_points_total == a.return_points_total
        and a.first_serve_points_won + a.second_serve_points_won <= a.service_points_total
        and b.first_serve_points_won + b.second_serve_points_won <= b.service_points_total
    )


def point_component_sensitivity(records: list[ApiTennisMatchEnrichment]) -> dict[str, Any]:
    """Compare a fixed target set before/after quarantining inconsistent history.

    This is a retrospective engineering scenario using the frozen serve/return
    component and standardized best-of-three PointSim. It is not full-stack
    inference, a forecast amendment, or a predictive performance comparison.
    """
    from tennis_genome.data.canonical import (
        HistoricalMatch,
        MatchOutcome,
        MatchStats,
        PreMatchState,
    )
    from tennis_genome.ratings.serve_return import walk_forward_serve_return
    from tennis_genome.simulation.tennis import point_sim_match_probability

    result: dict[str, Any] = {}
    for tour in ("ATP", "WTA"):
        selected = sorted(
            (r for r in records if r.tour == tour), key=lambda r: (r.event_date, r.event_key)
        )
        scenarios: dict[str, dict[str, Any]] = {}
        for checked in (False, True):
            history = []
            for index, record in enumerate(selected):
                match_id = f"api-tennis:{record.event_key}"
                state = PreMatchState(
                    match_id=match_id,
                    tour=tour,
                    event_date=date.fromisoformat(record.event_date),
                    source_order=index,
                    tournament_id=str(record.tournament_key),
                    tournament_name=record.tournament_name,
                    tournament_level=None,
                    surface="Unknown",
                    round=None,
                    best_of=3,
                    player_a_id=str(record.player_a_key),
                    player_b_id=str(record.player_b_key),
                    player_a_name=record.player_a_name,
                    player_b_name=record.player_b_name,
                    rank_a=None,
                    rank_b=None,
                    rank_points_a=None,
                    rank_points_b=None,
                )
                admitted = _legacy_accepted(record) and (
                    not checked or not api_tennis_point_count_issues(record)
                )
                # Reproduce the old bridge's exact inputs only in this audit scenario.
                stats = None
                if admitted:
                    a, b = record.player_a_stats, record.player_b_stats
                    stats = MatchStats(
                        match_id=match_id,
                        service_points_a=a.service_points_total,
                        service_points_b=b.service_points_total,
                        first_serve_points_won_a=a.first_serve_points_won,
                        second_serve_points_won_a=a.second_serve_points_won,
                        first_serve_points_won_b=b.first_serve_points_won,
                        second_serve_points_won_b=b.second_serve_points_won,
                    )
                history.append(
                    HistoricalMatch(
                        pre_match=state,
                        outcome=MatchOutcome(match_id, False, None, False, False),
                        stats=stats,
                    )
                )
            scenarios["checked" if checked else "legacy"] = {
                s.match_id: s for s in walk_forward_serve_return(history)
            }
        changes = []
        for record in selected:
            match_id = f"api-tennis:{record.event_key}"
            probabilities = {}
            for name, snapshots in scenarios.items():
                s = snapshots[match_id]
                probabilities[name] = point_sim_match_probability(
                    s.probability_a_serve_point, s.probability_b_serve_point, best_of=3
                )
            changes.append(
                {
                    "event_key": record.event_key,
                    "event_date": record.event_date,
                    "legacy_probability_a": probabilities["legacy"],
                    "checked_probability_a": probabilities["checked"],
                    "absolute_difference": abs(probabilities["legacy"] - probabilities["checked"]),
                }
            )
        result[tour] = {
            "target_count": len(changes),
            "changed_target_count": sum(x["absolute_difference"] > 1e-12 for x in changes),
            "mean_absolute_probability_difference": (
                sum(x["absolute_difference"] for x in changes) / len(changes) if changes else None
            ),
            "max_absolute_probability_difference": max(
                (x["absolute_difference"] for x in changes), default=None
            ),
            "largest_changes": sorted(
                changes, key=lambda x: (-x["absolute_difference"], x["event_key"])
            )[:10],
        }
    return {
        "comparison": "LEGACY_VS_QUARANTINED_HISTORY_FIXED_TARGETS",
        "component": "FROZEN_SERVE_RETURN_AND_STANDARDIZED_BEST_OF_THREE_POINTSIM",
        "same_day_updates_allowed": False,
        "target_outcomes_consumed": False,
        "full_stack_comparison": False,
        "predictive_performance_claim": False,
        "tours": result,
    }


def audit_retained_history(
    capture_dirs: list[Path], *, sensitivity: bool = False
) -> dict[str, Any]:
    if not capture_dirs:
        raise ValueError("at least one retained capture is required")
    captures, parsed, quarantined = [], [], []
    counts = {tour: Counter() for tour in ("ATP", "WTA")}
    reasons = {tour: Counter() for tour in ("ATP", "WTA")}
    seen: set[int] = set()
    for root in sorted(capture_dirs, key=lambda p: str(p.resolve())):
        capture, rows = verify_capture(root)
        captures.append(capture)
        for row in rows:
            key = row.get("event_key")
            if type(key) is not int or key in seen:
                raise ValueError("invalid or duplicate event identity across captures")
            seen.add(key)
            tour = "ATP" if row["event_type_type"] == "Atp Singles" else "WTA"
            counts[tour]["fixtures"] += 1
            if row.get("event_status") != "Finished":
                counts[tour]["not_normal_finished"] += 1
                continue
            counts[tour]["finished"] += 1
            try:
                record = parse_api_tennis_match_enrichment(row)
            except ValueError as exc:
                counts[tour]["unparseable_enrichment"] += 1
                quarantined.append(
                    {
                        "event_key": key,
                        "tour": tour,
                        "reasons": ["MISSING_OR_INVALID_ENRICHMENT"],
                        "detail": str(exc),
                    }
                )
                continue
            parsed.append(record)
            counts[tour]["parsed"] += 1
            issues = api_tennis_point_count_issues(record)
            counts[tour]["legacy_bridge_accepted"] += int(_legacy_accepted(record))
            if issues:
                counts[tour]["point_inconsistent"] += 1
                reasons[tour].update(issues)
                quarantined.append(
                    {
                        "event_key": key,
                        "tour": tour,
                        "raw_match_sha256": record.raw_match_sha256,
                        "reasons": list(issues),
                    }
                )
            else:
                counts[tour]["point_consistent"] += 1
    captures.sort(key=lambda x: (x["date_start"], x["workflow_run_id"]))
    gaps = []
    covered_until = date.fromisoformat(captures[0]["date_stop"])
    for capture in captures[1:]:
        start, stop = (
            date.fromisoformat(capture["date_start"]),
            date.fromisoformat(capture["date_stop"]),
        )
        if start > covered_until + timedelta(days=1):
            gaps.append(
                {
                    "date_start": (covered_until + timedelta(days=1)).isoformat(),
                    "date_stop": (start - timedelta(days=1)).isoformat(),
                }
            )
        covered_until = max(covered_until, stop)
    report = {
        "schema_version": "tennis-genome-api-tennis-retained-quality-audit-v1",
        "provider_calls_this_audit": 0,
        "production_eligible": False,
        "runtime": platform.python_version(),
        "implementation_file_sha256": {
            name: _sha((Path(__file__).resolve().parents[1] / name).read_bytes())
            for name in (
                "scripts/audit_api_tennis_retained_history.py",
                "src/tennis_genome/research_workbench/api_tennis_enrichment.py",
                "src/tennis_genome/research_workbench/api_tennis_matchstats_bridge.py",
                "src/tennis_genome/ratings/serve_return.py",
                "src/tennis_genome/simulation/tennis.py",
            )
        },
        "captures": captures,
        "capture_window_gaps": gaps,
        "calendar_windows_prove_complete_tour_coverage": False,
        "tours": {
            tour: {
                "counts": dict(sorted(counts[tour].items())),
                "point_issue_counts": dict(sorted(reasons[tour].items())),
            }
            for tour in ("ATP", "WTA")
        },
        "quarantined": sorted(quarantined, key=lambda x: x["event_key"]),
        "remaining_admission_gates": [
            "INDEPENDENT_POINT_STAT_SOURCE_COMPARISON",
            "CANONICAL_PLAYER_AND_EVENT_IDENTITY",
            "SURFACE_DURATION_AND_PLAYER_CONTEXT_PROVENANCE",
            "COMPLETE_CHRONOLOGICAL_CURRENT_STATE_BUILD",
            "VERIFIED_ACTUAL_START_AND_PRESTART_ANCHOR",
        ],
    }
    if sensitivity:
        report["component_sensitivity"] = point_component_sensitivity(parsed)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-dir", type=Path, action="append", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--component-sensitivity", action="store_true")
    args = parser.parse_args()
    report = audit_retained_history(args.capture_dir, sensitivity=args.component_sensitivity)
    payload = (json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    (args.output_dir / "audit.json").write_bytes(payload)
    (args.output_dir / "audit.sha256").write_text(_sha(payload) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "report_sha256": _sha(payload),
                "tours": report["tours"],
                "provider_calls_this_audit": 0,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
