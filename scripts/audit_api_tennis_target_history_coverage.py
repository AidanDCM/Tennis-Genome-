"""Rank target fixtures by retained historical identity/point coverage.

Research-only planning aid. This does not admit provider history, construct a
production MatchupInput, verify actual start, or produce a forecast.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def assess(identity: dict, crosswalk: dict) -> dict:
    if identity.get("schema_version") != "tennis-genome-api-tennis-history-identity-audit-v1":
        raise ValueError("unsupported history identity audit")
    if crosswalk.get("schema_version") != "tennis-genome-api-tennis-crosswalk-proposals-v1":
        raise ValueError("unsupported target crosswalk")
    target_date = date.fromisoformat(crosswalk["schedule_date"])
    captures = identity["captures"]
    if not captures or any(
        not capture.get("retained_bytes_verified")
        or date.fromisoformat(capture["date_stop"]) >= target_date
        for capture in captures
    ):
        raise ValueError("history is unverified or reaches target date")
    if identity.get("production_admitted") or crosswalk.get("production_admitted"):
        raise ValueError("expected research-only input reports")

    player_ids = {}
    for player in identity["players"]:
        key = (player["tour"], player["api_player_key"])
        if key in player_ids:
            raise ValueError("duplicate historical player key")
        player_ids[key] = player
    history = defaultdict(Counter)
    tournaments = defaultdict(set)
    seen_events = set()
    for event in identity["events"]:
        key = (event["tour"], event["event_key"])
        if key in seen_events:
            raise ValueError("duplicate historical event")
        seen_events.add(key)
        for player_key in event["api_player_keys"]:
            player = (event["tour"], player_key)
            history[player][event["point_disposition"] + "|" + event["identity_tier"]] += 1
            if (
                event["point_disposition"] == "POINT_CONSISTENT"
                and event["identity_tier"] == "BOTH_EXACT"
            ):
                tournaments[player].add(event["tournament_key"])

    results = []
    seen_targets = set()
    for target in crosswalk["matches"]:
        event_key = target["event_key"]
        if event_key in seen_targets:
            raise ValueError("duplicate target event")
        seen_targets.add(event_key)
        keys = [(target["tour"], key) for key in target["api_player_keys"]]
        counts = []
        for key in keys:
            player = player_ids.get(key)
            counts.append(
                {
                    "api_player_key": key[1],
                    "historical_identity_status": player["status"] if player else "ABSENT",
                    "point_consistent_both_exact": history[key]["POINT_CONSISTENT|BOTH_EXACT"],
                    "point_consistent_other_identity": sum(
                        count
                        for label, count in history[key].items()
                        if label.startswith("POINT_CONSISTENT|")
                        and label != "POINT_CONSISTENT|BOTH_EXACT"
                    ),
                    "point_conflict": sum(
                        count for label, count in history[key].items()
                        if label.startswith("POINT_CONFLICT|")
                    ),
                    "exact_consistent_tournament_count": len(tournaments[key]),
                }
            )
        exact_target = target["status"] == "EXACT_CANDIDATE"
        if exact_target and any(
            item["historical_identity_status"] not in {"EXACT_NAME_BIRTHDATE", "ABSENT"}
            for item in counts
        ):
            raise ValueError("exact target crosswalk conflicts with historical identity audit")
        results.append(
            {
                "event_key": event_key,
                "tour": target["tour"],
                "tournament_key": target["tournament_key"],
                "target_crosswalk_status": target["status"],
                "players": counts,
                "minimum_exact_consistent_history": min(
                    item["point_consistent_both_exact"] for item in counts
                ),
                "production_eligible": False,
            }
        )
    results.sort(
        key=lambda row: (
            row["target_crosswalk_status"] != "EXACT_CANDIDATE",
            -row["minimum_exact_consistent_history"],
            row["event_key"],
        )
    )
    return {
        "schema_version": "tennis-genome-api-tennis-target-history-coverage-v1",
        "target_date": target_date.isoformat(),
        "target_count": len(results),
        "exact_target_count": sum(
            row["target_crosswalk_status"] == "EXACT_CANDIDATE" for row in results
        ),
        "history_capture_run_ids": [item["workflow_run_id"] for item in captures],
        "production_admitted": False,
        "formal_prediction_count": 0,
        "matches": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--identity-report", type=Path, required=True)
    parser.add_argument("--crosswalk", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    identity_raw, crosswalk_raw = args.identity_report.read_bytes(), args.crosswalk.read_bytes()
    report = assess(json.loads(identity_raw), json.loads(crosswalk_raw))
    report["input_sha256"] = {"identity": _sha(identity_raw), "crosswalk": _sha(crosswalk_raw)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {key: report[key] for key in ("target_count", "exact_target_count")},
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
