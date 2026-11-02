"""Compare retained API-Tennis match counts with a curated official reference.

The reference is a separately observed post-match source. This audit never
creates a historical pre-match forecast or admits a source to production.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from scripts.audit_api_tennis_retained_history import verify_capture
from tennis_genome.research_workbench.api_tennis_enrichment import (
    api_tennis_point_count_issues,
    parse_api_tennis_match_enrichment,
)


def adjudicate_row(row: dict[str, Any], reference: dict[str, Any]) -> dict[str, Any]:
    """Compare exact service-point numerators and denominators by provider ID."""
    event_key = reference["event_key"]
    if type(event_key) is not int or row.get("event_key") != event_key:
        raise ValueError("reference event identity mismatch")
    if row.get("event_date") != reference["event_date"]:
        raise ValueError("reference event date mismatch")
    if row.get("event_status") != "Finished":
        raise ValueError("reference event is not marked Finished")
    if row.get("event_type_type") != reference["tour_event_type"]:
        raise ValueError("reference tour mismatch")
    official_url = urlparse(str(reference["official_url"]))
    if official_url.scheme != "https" or official_url.hostname != "www.wtatennis.com":
        raise ValueError("reference must link to an official WTA match page")

    players = reference["players"]
    if not isinstance(players, list) or len(players) != 2:
        raise ValueError("reference requires exactly two players")
    stats = row.get("statistics")
    if not isinstance(stats, list):
        raise ValueError("provider match has no statistic array")
    comparisons = []
    for side, player in zip(("first", "second"), players, strict=True):
        provider_id = row.get(f"{side}_player_key")
        if type(provider_id) is not int or provider_id != player["provider_player_key"]:
            raise ValueError("reference player identity mismatch")
        if row.get(f"event_{side}_player") != player["provider_player_name"]:
            raise ValueError("reference player name mismatch")
        matches = [
            stat
            for stat in stats
            if isinstance(stat, dict)
            and stat.get("player_key") == provider_id
            and stat.get("stat_period") == "match"
            and stat.get("stat_type") == "Points"
            and stat.get("stat_name") == "Service Points Won"
        ]
        if len(matches) != 1:
            raise ValueError("provider service-point statistic is missing or duplicated")
        provider_won, provider_total = matches[0].get("stat_won"), matches[0].get("stat_total")
        official_won, official_total = (
            player["official_service_points_won"],
            player["official_service_points_total"],
        )
        if any(
            type(value) is not int or value < 0
            for value in (provider_won, provider_total, official_won, official_total)
        ):
            raise ValueError("service-point counts must be nonnegative integers")
        if provider_won > provider_total or official_won > official_total:
            raise ValueError("service-point wins exceed denominator")
        comparisons.append(
            {
                "provider_player_key": provider_id,
                "provider_player_name": player["provider_player_name"],
                "provider_won": provider_won,
                "provider_total": provider_total,
                "official_won": official_won,
                "official_total": official_total,
                "won_delta": provider_won - official_won,
                "total_delta": provider_total - official_total,
                "exact_agreement": (provider_won, provider_total) == (official_won, official_total),
            }
        )
    if comparisons[0]["provider_player_key"] == comparisons[1]["provider_player_key"]:
        raise ValueError("duplicate provider player identities")
    try:
        issues = list(api_tennis_point_count_issues(parse_api_tennis_match_enrichment(row)))
    except ValueError as exc:
        issues = [f"PARSE_FAILURE:{type(exc).__name__}"]
    return {
        "event_key": event_key,
        "event_date": row["event_date"],
        "official_url": reference["official_url"],
        "players": comparisons,
        "provider_internal_issues": issues,
        "official_point_agreement": all(p["exact_agreement"] for p in comparisons),
        "source_admission": "RESEARCH_ONLY",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-dir", type=Path, action="append", required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    captures = []
    rows = []
    for root in args.capture_dir:
        capture, retained_rows = verify_capture(root)
        captures.append(capture)
        rows.extend(retained_rows)
    raw_reference = args.reference.read_bytes()
    references = json.loads(raw_reference)
    if not isinstance(references, list) or not references:
        raise ValueError("reference must contain a nonempty case array")
    by_id: dict[int, dict[str, Any]] = {}
    for row in rows:
        key = row["event_key"]
        if key in by_id:
            raise ValueError("duplicate provider event identity")
        by_id[key] = row
    seen: set[int] = set()
    cases = []
    for reference in references:
        key = reference["event_key"]
        if key in seen or key not in by_id:
            raise ValueError("duplicate or absent reference event")
        seen.add(key)
        cases.append(adjudicate_row(by_id[key], reference))
    result = {
        "schema_version": "api-tennis-official-point-adjudication-v1",
        "captures": captures,
        "reference_sha256": hashlib.sha256(raw_reference).hexdigest(),
        "case_count": len(cases),
        "exact_agreement_count": sum(case["official_point_agreement"] for case in cases),
        "cases": cases,
        "scope": (
            "curated post-match source comparison; no production admission or pre-match evidence"
        ),
    }
    with args.output.open("x", encoding="utf-8", newline="\n") as output:
        output.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {"case_count": len(cases), "exact_agreement_count": result["exact_agreement_count"]}
        )
    )


if __name__ == "__main__":
    main()
