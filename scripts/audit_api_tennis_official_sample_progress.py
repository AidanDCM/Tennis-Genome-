"""Reconcile a frozen API-Tennis official-stat sample with retained reviews.

The input reviews are curated post-match observations, not independently
authenticated official pages or production source approval.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


def reconcile(
    sample: dict[str, Any],
    reviews: list[dict[str, Any]],
    identities: dict[str, Any],
) -> dict[str, Any]:
    if sample.get("schema_version") != "api-tennis-official-source-sample-v1":
        raise ValueError("unexpected frozen sample schema")
    if identities.get("production_admitted") is not False:
        raise ValueError("identity report must be research-only")
    selected = sample.get("selected")
    if not isinstance(selected, list) or len(selected) != sample.get("selected_count"):
        raise ValueError("frozen sample count mismatch")
    by_event: dict[int, dict[str, Any]] = {}
    for row in selected:
        key = row["event_key"]
        if type(key) is not int or key in by_event:
            raise ValueError("duplicate or invalid frozen sample event")
        by_event[key] = row
    identity_events = {
        (row["tour"], row["event_key"]): row for row in identities["events"]
    }
    capture_evidence = {
        row["workflow_run_id"]: row for row in sample["captures"]
    }
    identity_captures = {
        row["workflow_run_id"]: row for row in identities["captures"]
    }
    for run_id, capture in capture_evidence.items():
        reference = identity_captures.get(run_id)
        if reference is None or any(
            capture[field] != reference[field]
            for field in ("raw_atp_sha256", "raw_wta_sha256", "receipt_sha256")
        ):
            raise ValueError("identity report capture differs from frozen sample")
    reviewed: dict[int, dict[str, Any]] = {}
    for review in reviews:
        if review.get("schema_version") != "api-tennis-official-point-adjudication-v1":
            raise ValueError("unexpected adjudication schema")
        if len(review["cases"]) != review["case_count"]:
            raise ValueError("adjudication case count mismatch")
        if sum(bool(case["official_point_agreement"]) for case in review["cases"]) != review[
            "exact_agreement_count"
        ]:
            raise ValueError("adjudication agreement count mismatch")
        for capture in review["captures"]:
            source = capture_evidence.get(capture["workflow_run_id"])
            if source is None or any(
                capture[field] != source[field]
                for field in ("raw_atp_sha256", "raw_wta_sha256", "receipt_sha256")
            ):
                raise ValueError("adjudication capture differs from frozen sample")
        for case in review["cases"]:
            key = case["event_key"]
            selected_row = by_event.get(key)
            if selected_row is None or case["event_date"] != selected_row["event_date"]:
                raise ValueError("adjudication event absent from frozen sample")
            if selected_row["capture_workflow_run_id"] not in {
                capture["workflow_run_id"] for capture in review["captures"]
            }:
                raise ValueError("adjudication lacks event's capture evidence")
            if case["source_admission"] != "RESEARCH_ONLY":
                raise ValueError("adjudication cannot approve production source")
            if len(case["players"]) != 2 or {
                player["provider_player_key"] for player in case["players"]
            } != {selected_row["player_a_key"], selected_row["player_b_key"]}:
                raise ValueError("adjudication player identity mismatch")
            if case["provider_internal_issues"]:
                raise ValueError("frozen sample contains an internally rejected case")
            if case["official_point_agreement"] != all(
                player["exact_agreement"]
                and player["provider_won"] == player["official_won"]
                and player["provider_total"] == player["official_total"]
                for player in case["players"]
            ):
                raise ValueError("adjudication agreement contradicts player counts")
            prior = reviewed.get(key)
            if prior is not None and prior != case:
                raise ValueError("contradictory adjudication for sampled event")
            reviewed[key] = case
    rows = []
    counts: Counter[str] = Counter()
    for row in selected:
        identity = identity_events.get((row["tour"], row["event_key"]))
        if identity is None:
            raise ValueError("sample event absent from identity audit")
        if identity["point_disposition"] != "POINT_CONSISTENT":
            raise ValueError("frozen sample event no longer passes the point gate")
        case = reviewed.get(row["event_key"])
        if case is None:
            status = "PENDING_OFFICIAL_REVIEW"
        elif case["official_point_agreement"]:
            status = "SERVICE_POINTS_AGREE"
        else:
            status = "SERVICE_POINTS_DISAGREE"
        counts[status] += 1
        counts[f"{row['tour']}|{status}"] += 1
        rows.append(
            {
                "tour": row["tour"],
                "event_key": row["event_key"],
                "event_date": row["event_date"],
                "tournament_name": row["tournament_name"],
                "players": [row["player_a_name"], row["player_b_name"]],
                "identity_tier": identity["identity_tier"],
                "review_status": status,
                "official_url": case["official_url"] if case else None,
                "production_admitted": False,
            }
        )
    return {
        "schema_version": "tennis-genome-official-sample-progress-v1",
        "frozen_selected_count": len(selected),
        "unique_reviewed_count": len(reviewed),
        "counts": dict(sorted(counts.items())),
        "rows": rows,
        "source_admission": "RESEARCH_ONLY",
        "official_pages_authenticated_at_runtime": False,
        "checked_fields": "two players' service points won and played only",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", type=Path, required=True)
    parser.add_argument("--adjudication", type=Path, action="append", required=True)
    parser.add_argument("--identity-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sample_raw = args.sample.read_bytes()
    identity_raw = args.identity_report.read_bytes()
    review_raws = [path.read_bytes() for path in args.adjudication]
    result = reconcile(
        json.loads(sample_raw),
        [json.loads(raw) for raw in review_raws],
        json.loads(identity_raw),
    )
    result["input_sha256"] = {
        "sample": hashlib.sha256(sample_raw).hexdigest(),
        "identity_report": hashlib.sha256(identity_raw).hexdigest(),
        "adjudications": [hashlib.sha256(raw).hexdigest() for raw in review_raws],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as output:
        output.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result["counts"], sort_keys=True))


if __name__ == "__main__":
    main()
