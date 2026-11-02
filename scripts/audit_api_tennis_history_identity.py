"""Audit retained historical player identity without approving source substitution."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

from scripts.audit_api_tennis_retained_history import verify_capture
from scripts.propose_api_tennis_player_crosswalk import (
    _date_from_api,
    _registry,
    _verified_metadata,
)
from tennis_genome.data.identity import normalize_player_name
from tennis_genome.research_workbench.api_tennis_enrichment import (
    api_tennis_point_count_issues,
    parse_api_tennis_match_enrichment,
)


def _verified_standings(root: Path) -> tuple[dict[tuple[str, int], str], dict[str, object]]:
    manifest_raw = (root / "manifest.json").read_bytes()
    manifest = json.loads(manifest_raw)
    receipt_raw = (root / "github-receipt.json").read_bytes()
    receipt = json.loads(receipt_raw)
    if hashlib.sha256(manifest_raw).hexdigest() != receipt["manifest_sha256"]:
        raise ValueError("standings manifest receipt mismatch")
    names: dict[tuple[str, int], str] = {}
    for tour in ("ATP", "WTA"):
        raw = (root / f"raw-{tour.lower()}-standings.json").read_bytes()
        if hashlib.sha256(raw).hexdigest() != manifest[f"raw_{tour.lower()}_sha256"]:
            raise ValueError(f"{tour} standings raw hash mismatch")
        payload = json.loads(raw)
        if payload.get("success") not in (1, "1"):
            raise ValueError(f"{tour} standings provider rejection")
        for row in payload["result"]:
            key = (tour, int(row["player_key"]))
            name = str(row["player"])
            if key in names and names[key] != name:
                raise ValueError(f"conflicting standing identity {key}")
            names[key] = name
    evidence = {
        "workflow_run_id": int(receipt["workflow_run_id"]),
        "manifest_sha256": hashlib.sha256(manifest_raw).hexdigest(),
        "receipt_sha256": hashlib.sha256(receipt_raw).hexdigest(),
    }
    return names, evidence


def classify_identity(
    *,
    tour: str,
    player_key: int,
    standing_name: str | None,
    profile: dict[str, object] | None,
    registry: dict[tuple[str, str, str], set[str]],
    name_index: dict[tuple[str, str], set[str]],
) -> tuple[str, str | None]:
    """Return evidence tier and unique candidate, never an approved crosswalk."""
    if profile is not None:
        name = profile.get("player_full_name")
        birth = _date_from_api(profile.get("player_bday"))
        if not isinstance(name, str) or not name.strip() or birth is None:
            return "PROFILE_INCOMPLETE", None
        matches = registry.get((tour, normalize_player_name(name), birth), set())
        if len(matches) == 1:
            return "EXACT_NAME_BIRTHDATE", next(iter(matches))
        return ("PROFILE_AMBIGUOUS" if matches else "PROFILE_NO_EXACT_MATCH"), None
    if standing_name:
        ids = name_index.get((tour, normalize_player_name(standing_name)), set())
        if len(ids) == 1:
            return "NAME_ONLY_PROPOSAL", next(iter(ids))
        return ("NAME_AMBIGUOUS" if ids else "NAME_NOT_IN_REGISTRY"), None
    return "NO_FULL_NAME", None


def profile_identity_consistent(first: dict[str, object], second: dict[str, object]) -> bool:
    """Season aggregates can change across captures; identity fields cannot."""
    return all(
        first.get(field) == second.get(field) for field in ("player_full_name", "player_bday")
    )


def audit(
    *,
    archive: Path,
    capture_dirs: list[Path],
    standings_dir: Path,
    profile_dirs: list[tuple[str, Path]],
) -> dict[str, object]:
    registry = _registry(archive)
    name_index: dict[tuple[str, str], set[str]] = defaultdict(set)
    for (tour, name, _), ids in registry.items():
        name_index[(tour, name)].update(ids)
    standings, standings_evidence = _verified_standings(standings_dir)
    captures = []
    events: dict[tuple[str, int], dict[str, object]] = {}
    for root in capture_dirs:
        evidence, rows = verify_capture(root)
        captures.append(evidence)
        for row in rows:
            tour = {"Atp Singles": "ATP", "Wta Singles": "WTA"}[row["event_type_type"]]
            key = (tour, int(row["event_key"]))
            if key in events:
                raise ValueError(f"duplicate historical event {key}")
            events[key] = row
    if not captures:
        raise ValueError("at least one verified capture is required")
    captures.sort(key=lambda item: item["date_start"])
    for previous, current in zip(captures, captures[1:], strict=False):
        expected = date.fromisoformat(previous["date_stop"]) + timedelta(days=1)
        if date.fromisoformat(current["date_start"]) != expected:
            raise ValueError("historical capture windows must be contiguous and disjoint")

    profiles: dict[tuple[str, int], dict[str, object]] = {}
    profile_evidence: list[dict[str, object]] = []
    profiled_tournaments: set[tuple[str, int]] = set()
    for tour, directory in profile_dirs:
        if tour not in {"ATP", "WTA"}:
            raise ValueError("profile tour must be ATP or WTA")
        name = directory.name
        rows, evidence = _verified_metadata(directory.parent, name)
        manifest = json.loads((directory / name / "manifest.json").read_bytes())
        profiled_tournaments.add((tour, int(manifest["tournament_key"])))
        profile_evidence.append({"artifact_name": name, **evidence})
        for profile in rows:
            key = (tour, int(profile["player_key"]))
            if key in profiles:
                if not profile_identity_consistent(profiles[key], profile):
                    raise ValueError(f"conflicting player identity fields {key}")
            else:
                profiles[key] = profile
    players = {
        (tour, int(player_key))
        for (tour, _), row in events.items()
        for player_key in (row.get("first_player_key"), row.get("second_player_key"))
        if player_key is not None
    }
    player_rows = []
    player_by_key: dict[tuple[str, int], dict[str, object]] = {}
    for tour, key in sorted(players):
        status, candidate = classify_identity(
            tour=tour,
            player_key=key,
            standing_name=standings.get((tour, key)),
            profile=profiles.get((tour, key)),
            registry=registry,
            name_index=name_index,
        )
        row = {
            "tour": tour,
            "api_player_key": key,
            "status": status,
            "candidate_canonical_id": candidate,
            "production_admitted": False,
        }
        player_rows.append(row)
        player_by_key[(tour, key)] = row

    event_counts: Counter[str] = Counter()
    event_rows = []
    for (tour, event_key), raw in sorted(events.items()):
        status = str(raw.get("event_status"))
        if status != "Finished":
            disposition = "NOT_FINISHED"
        else:
            try:
                parsed = parse_api_tennis_match_enrichment(raw)
            except ValueError:
                disposition = "NO_USABLE_POINT_STATS"
            else:
                disposition = (
                    "POINT_CONFLICT"
                    if api_tennis_point_count_issues(parsed)
                    else "POINT_CONSISTENT"
                )
        ids = (raw.get("first_player_key"), raw.get("second_player_key"))
        player_states = [
            player_by_key.get((tour, int(key))) if key is not None else None for key in ids
        ]
        if all(state and state["status"] == "EXACT_NAME_BIRTHDATE" for state in player_states):
            identity_tier = "BOTH_EXACT"
        elif all(state and state["candidate_canonical_id"] for state in player_states):
            identity_tier = "NAME_ONLY_OR_MIXED"
        else:
            identity_tier = "UNRESOLVED"
        event_counts[f"{disposition}|{identity_tier}"] += 1
        event_rows.append(
            {
                "tour": tour,
                "event_key": event_key,
                "tournament_key": int(raw["tournament_key"]),
                "tournament_season": str(raw["tournament_season"]),
                "api_player_keys": list(ids),
                "point_disposition": disposition,
                "identity_tier": identity_tier,
                "production_admitted": False,
            }
        )
    uncovered = {
        (row["tour"], row["api_player_key"])
        for row in player_rows
        if (row["tour"], row["api_player_key"]) not in profiles
    }
    tournament_players: dict[tuple[str, int, str], set[tuple[str, int]]] = defaultdict(set)
    for row in event_rows:
        tournament = (row["tour"], row["tournament_key"], row["tournament_season"])
        if (row["tour"], row["tournament_key"]) in profiled_tournaments:
            continue
        tournament_players[tournament].update(
            (row["tour"], int(key)) for key in row["api_player_keys"] if key is not None
        )
    probe_plan = []
    remaining = set(uncovered)
    for _ in range(10):
        candidates = [
            (len(players & remaining), tournament)
            for tournament, players in tournament_players.items()
        ]
        if not candidates:
            break
        potential, tournament = max(candidates)
        if potential == 0:
            break
        probe_plan.append(
            {
                "tour": tournament[0],
                "tournament_key": tournament[1],
                "season": tournament[2],
                "additional_player_profiles_possible": potential,
                "not_guaranteed": True,
            }
        )
        remaining.difference_update(tournament_players.pop(tournament))
    return {
        "schema_version": "tennis-genome-api-tennis-history-identity-audit-v1",
        "captures": captures,
        "standings_source": standings_evidence,
        "profile_sources": profile_evidence,
        "event_count": len(events),
        "player_count": len(players),
        "player_status_counts": dict(sorted(Counter(row["status"] for row in player_rows).items())),
        "event_disposition_counts": dict(sorted(event_counts.items())),
        "ten_call_profile_probe_plan": probe_plan,
        "ten_call_potential_distinct_players": len(uncovered) - len(remaining),
        "production_admitted": False,
        "players": player_rows,
        "events": event_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--capture-dir", type=Path, action="append", required=True)
    parser.add_argument("--standings-dir", type=Path, required=True)
    parser.add_argument(
        "--profile-dir", nargs=2, action="append", metavar=("TOUR", "OUTER_DIR"), default=[]
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(
        archive=args.archive,
        capture_dirs=args.capture_dir,
        standings_dir=args.standings_dir,
        profile_dirs=[(tour, Path(directory)) for tour, directory in args.profile_dir],
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps({k: result[k] for k in ("event_count", "player_count", "player_status_counts")})
    )


if __name__ == "__main__":
    main()
