"""Freeze a deterministic source-check sample from verified retained history."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from scripts.audit_api_tennis_retained_history import verify_capture
from tennis_genome.research_workbench.api_tennis_enrichment import (
    api_tennis_point_count_issues,
    parse_api_tennis_match_enrichment,
)


def select_sample(
    candidates: list[dict[str, Any]], *, seed: str, per_tour_month: int
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Select by tour/month using only frozen identity and a predeclared seed."""
    if not seed or per_tour_month < 1:
        raise ValueError("seed and positive per_tour_month are required")
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        key = (candidate["tour"], candidate["event_date"][:7])
        groups[key].append(candidate)
    selected: list[dict[str, Any]] = []
    denominators: dict[str, int] = {}
    for key, values in sorted(groups.items()):
        label = f"{key[0]}:{key[1]}"
        denominators[label] = len(values)
        ranked = sorted(
            values,
            key=lambda row: (
                hashlib.sha256(f"{seed}|{row['tour']}|{row['event_key']}".encode()).hexdigest(),
                row["event_key"],
            ),
        )
        selected.extend(ranked[:per_tour_month])
    return selected, denominators


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-dir", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", default="TGE-SOURCE-CHECK-2026-11-02-v1")
    parser.add_argument("--per-tour-month", type=int, default=2)
    args = parser.parse_args()
    candidates: list[dict[str, Any]] = []
    captures = []
    seen: set[int] = set()
    for root in args.capture_dir:
        receipt, rows = verify_capture(root)
        captures.append(receipt)
        for row in rows:
            event_key = row["event_key"]
            if event_key in seen:
                raise ValueError("duplicate event identity across retained captures")
            seen.add(event_key)
            try:
                parsed = parse_api_tennis_match_enrichment(row)
            except ValueError:
                continue
            if api_tennis_point_count_issues(parsed):
                continue
            candidates.append(
                {
                    "tour": parsed.tour,
                    "event_key": parsed.event_key,
                    "event_date": parsed.event_date,
                    "tournament_name": parsed.tournament_name,
                    "player_a_name": parsed.player_a_name,
                    "player_b_name": parsed.player_b_name,
                    "player_a_key": parsed.player_a_key,
                    "player_b_key": parsed.player_b_key,
                    "raw_match_sha256": parsed.raw_match_sha256,
                    "capture_workflow_run_id": receipt["workflow_run_id"],
                }
            )
    selected, denominators = select_sample(
        candidates, seed=args.seed, per_tour_month=args.per_tour_month
    )
    report = {
        "schema_version": "api-tennis-official-source-sample-v1",
        "selection_seed": args.seed,
        "per_tour_month": args.per_tour_month,
        "eligible_count": len(candidates),
        "eligible_denominators": denominators,
        "selected_count": len(selected),
        "captures": captures,
        "selected": selected,
        "selection_rule": (
            "parseable internally consistent finished matches; "
            "lowest SHA256(seed|tour|event_key) per tour and UTC month"
        ),
        "official_review_status": "NOT_STARTED",
    }
    with args.output.open("x", encoding="utf-8", newline="\n") as output:
        output.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "eligible_count": len(candidates),
                "selected_count": len(selected),
                "eligible_denominators": denominators,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
