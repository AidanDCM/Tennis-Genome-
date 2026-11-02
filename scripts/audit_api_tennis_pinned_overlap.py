"""Compare verified retained API-Tennis points to the pinned 2026 archive.

This is source-quality research, not source admission or prospective validation.
Only exact name/DOB identity candidates and unique chronological joins are used.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import zipfile
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

from scripts.audit_api_tennis_retained_history import verify_capture
from tennis_genome.research_workbench.api_tennis_enrichment import (
    api_tennis_point_count_issues,
    parse_api_tennis_match_enrichment,
)

FIELDS = ("svpt", "1stIn", "1stWon", "2ndWon")


def _tournament_equivalent(api_name: str, pinned_name: str) -> bool:
    left, right = api_name.casefold().strip(), pinned_name.casefold().strip()
    return left == right or (left, right) in {
        ("rome", "rome masters"),
        ("french open", "roland garros"),
    }


def _archive_rows(archive: Path) -> dict[str, list[dict[str, str]]]:
    with zipfile.ZipFile(archive) as bundle:
        rows = {}
        for tour in ("ATP", "WTA"):
            suffix = f"/{tour.lower()}_matches_2026.csv"
            matches = [name for name in bundle.namelist() if name.endswith(suffix)]
            if len(matches) != 1:
                raise ValueError(f"expected one pinned {tour} main-tour 2026 file")
            with bundle.open(matches[0]) as raw:
                rows[tour] = list(csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8")))
        return rows


def _source_id(canonical_id: str) -> str:
    return canonical_id.rsplit(":", 1)[-1]


def _candidate_rows(
    *,
    tournament_name: str,
    event_date: date,
    first_id: str,
    second_id: str,
    winner_id: str,
    archive_rows: list[dict[str, str]],
    require_tournament: bool = True,
) -> list[dict[str, str]]:
    pair = frozenset((first_id, second_id))
    return [
        row
        for row in archive_rows
        if frozenset((row["winner_id"], row["loser_id"])) == pair
        and row["winner_id"] == winner_id
        and (not require_tournament or _tournament_equivalent(tournament_name, row["tourney_name"]))
        and (start := date.fromisoformat(
            f"{row['tourney_date'][:4]}-{row['tourney_date'][4:6]}-{row['tourney_date'][6:8]}"
        )) <= event_date <= start + timedelta(days=28)
    ]


def _point_differences(record: object, pinned: dict[str, str]) -> dict[str, int]:
    winner = record.player_a_stats if record.winner_side == "A" else record.player_b_stats
    loser = record.player_b_stats if record.winner_side == "A" else record.player_a_stats
    attr = {
        "svpt": "service_points_total",
        "1stIn": "first_serve_points_total",
        "1stWon": "first_serve_points_won",
        "2ndWon": "second_serve_points_won",
    }
    differences = {}
    for prefix, player in (("w", winner), ("l", loser)):
        for field in FIELDS:
            name = f"{prefix}_{field}"
            if pinned[name].strip():
                differences[name] = getattr(player, attr[field]) - int(pinned[name])
    return differences


def audit(archive: Path, capture_dir: Path, identity_report: Path) -> dict[str, object]:
    capture, raw_events = verify_capture(capture_dir)
    identities = json.loads(identity_report.read_bytes())
    if not any(
        row["workflow_run_id"] == capture["workflow_run_id"]
        and row["raw_atp_sha256"] == capture["raw_atp_sha256"]
        and row["raw_wta_sha256"] == capture["raw_wta_sha256"]
        for row in identities["captures"]
    ):
        raise ValueError("identity report does not authenticate this capture")
    if identities.get("production_admitted") is not False:
        raise ValueError("identity report must remain research-only")
    players = {
        (row["tour"], row["api_player_key"]): row
        for row in identities["players"]
    }
    dispositions = {
        (row["tour"], row["event_key"]): row
        for row in identities["events"]
    }
    pinned = _archive_rows(archive)
    counts: Counter[str] = Counter()
    compared = []
    discrepancies = []
    quarantined_joined = []
    unresolved_tournament_name_pairs: Counter[tuple[str, str]] = Counter()
    for raw in raw_events:
        tour = {"Atp Singles": "ATP", "Wta Singles": "WTA"}[raw["event_type_type"]]
        key = (tour, raw["event_key"])
        disposition = dispositions.get(key)
        if disposition is None:
            raise ValueError(f"capture event absent from identity report: {key}")
        if raw["event_status"] != "Finished":
            counts["nonfinished"] += 1
            continue
        ids = [players.get((tour, raw[name])) for name in ("first_player_key", "second_player_key")]
        if not all(row and row["status"] == "EXACT_NAME_BIRTHDATE" for row in ids):
            counts["identity_not_both_exact"] += 1
            continue
        if raw["event_winner"] not in ("First Player", "Second Player"):
            counts["winner_unresolved"] += 1
            continue
        first_id, second_id = (_source_id(row["candidate_canonical_id"]) for row in ids)
        winner_id = first_id if raw["event_winner"] == "First Player" else second_id
        matches = _candidate_rows(
            tournament_name=raw["tournament_name"],
            event_date=date.fromisoformat(raw["event_date"]),
            first_id=first_id,
            second_id=second_id,
            winner_id=winner_id,
            archive_rows=pinned[tour],
        )
        if len(matches) != 1:
            if not matches:
                loose = _candidate_rows(
                    tournament_name=raw["tournament_name"],
                    event_date=date.fromisoformat(raw["event_date"]),
                    first_id=first_id,
                    second_id=second_id,
                    winner_id=winner_id,
                    archive_rows=pinned[tour],
                    require_tournament=False,
                )
                if len(loose) == 1:
                    unresolved_tournament_name_pairs[
                        (raw["tournament_name"], loose[0]["tourney_name"])
                    ] += 1
            counts["pinned_no_unique_join" if not matches else "pinned_ambiguous_join"] += 1
            continue
        if disposition["point_disposition"] == "NO_USABLE_POINT_STATS":
            counts["joined_no_usable_point_stats"] += 1
            continue
        record = parse_api_tennis_match_enrichment(raw)
        actual_issues = api_tennis_point_count_issues(record)
        if (bool(actual_issues)) != (disposition["point_disposition"] == "POINT_CONFLICT"):
            raise ValueError(f"identity report point classification changed: {key}")
        differences = _point_differences(record, matches[0])
        if len(differences) != 8:
            label = "conflict" if actual_issues else "consistent"
            counts[f"joined_{label}_incomplete_pinned_points"] += 1
            continue
        equal = all(delta == 0 for delta in differences.values())
        row = {
            "tour": tour,
            "event_key": raw["event_key"],
            "event_date": raw["event_date"],
            "tournament_name_api": raw["tournament_name"],
            "tournament_name_pinned": matches[0]["tourney_name"],
            "winner_id": winner_id,
            "pinned_match_id": (
                f"{tour.lower()}:{matches[0]['tourney_id']}:{matches[0]['match_num']}"
            ),
            "point_differences_api_minus_pinned": differences,
        }
        if actual_issues:
            counts["joined_conflict_equal" if equal else "joined_conflict_disagreement"] += 1
            row["internal_point_issues"] = list(actual_issues)
            quarantined_joined.append(row)
            continue
        counts["all_eight_equal" if equal else "point_disagreement"] += 1
        compared.append(row)
        if not equal:
            discrepancies.append(row)
    return {
        "schema_version": "tennis-genome-api-tennis-pinned-overlap-audit-v1",
        "capture_evidence": capture,
        "pinned_archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "identity_report_sha256": hashlib.sha256(identity_report.read_bytes()).hexdigest(),
        "identity_report_schema": identities["schema_version"],
        "identity_report_production_admitted": identities["production_admitted"],
        "research_only": True,
        "join_requires_unique_pair_winner_tournament_and_event_after_tournament_start": True,
        "counts": dict(sorted(counts.items())),
        "compared": compared,
        "discrepancies": discrepancies,
        "quarantined_joined": quarantined_joined,
        "unresolved_tournament_name_pairs": [
            {"api_name": pair[0], "pinned_name": pair[1], "count": count}
            for pair, count in unresolved_tournament_name_pairs.most_common()
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--capture-dir", type=Path, required=True)
    parser.add_argument("--identity-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.archive, args.capture_dir, args.identity_report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["counts"], sort_keys=True))


if __name__ == "__main__":
    main()
