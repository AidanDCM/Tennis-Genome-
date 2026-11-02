"""Propose exact name-and-birthdate player links; never admit them to production."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import zipfile
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path

from tennis_genome.data.identity import canonical_player_id, normalize_player_name
from tennis_genome.independent.production import PINNED_SOURCE_COMMIT


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _date_from_registry(value: str) -> str | None:
    if len(value) != 8 or not value.isdigit():
        return None
    try:
        return date(int(value[:4]), int(value[4:6]), int(value[6:8])).isoformat()
    except ValueError:
        return None


def _date_from_api(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value, "%d.%m.%Y").date().isoformat()
    except ValueError:
        return None


def _registry(archive: Path) -> dict[tuple[str, str, str], set[str]]:
    output: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    with zipfile.ZipFile(archive) as source:
        for tour in ("ATP", "WTA"):
            member = (
                f"tennis-sackmann-archive-{PINNED_SOURCE_COMMIT}/"
                f"{tour.lower()}/{tour.lower()}_players.csv"
            )
            reader = csv.reader(io.StringIO(source.read(member).decode("utf-8")))
            for row in reader:
                if len(row) < 5 or not row[0].strip():
                    continue
                player_id, first, last, _, birth_raw = (cell.strip() for cell in row[:5])
                birth = _date_from_registry(birth_raw)
                if birth is None:
                    continue
                full_name = f"{first} {last}".strip()
                key = (tour, normalize_player_name(full_name), birth)
                output[key].add(canonical_player_id(tour=tour, source_id=player_id, name=full_name))
    return output


def _verified_metadata(root: Path, name: str) -> tuple[object, dict[str, object]]:
    directory = root / name / name
    manifest_raw = (directory / "manifest.json").read_bytes()
    manifest = json.loads(manifest_raw)
    receipt_raw = (directory / "github-receipt.json").read_bytes()
    receipt = json.loads(receipt_raw)
    raw = (directory / "raw-response.json").read_bytes()
    if _sha(manifest_raw) != receipt["manifest_sha256"]:
        raise ValueError(f"{name}: manifest receipt mismatch")
    if _sha(raw) != manifest["raw_sha256"]:
        raise ValueError(f"{name}: raw response hash mismatch")
    if manifest["method"] != "get_players":
        raise ValueError(f"{name}: expected player profile response")
    payload = json.loads(raw)
    if payload.get("success") not in (1, "1") or not isinstance(payload.get("result"), list):
        raise ValueError(f"{name}: invalid provider response")
    evidence = {
        "workflow_run_id": int(receipt["workflow_run_id"]),
        "raw_sha256": manifest["raw_sha256"],
        "manifest_sha256": _sha(manifest_raw),
        "receipt_sha256": _sha(receipt_raw),
    }
    return payload["result"], evidence


def propose(*, archive: Path, retained_root: Path, slate_report: Path) -> dict[str, object]:
    slate_raw = slate_report.read_bytes()
    slate = json.loads(slate_raw)
    if slate.get("schema_version") != "tennis-genome-offline-slate-field-audit-v1":
        raise ValueError("unsupported slate context report")
    if slate.get("fixture_count") != len(slate.get("matches", [])):
        raise ValueError("slate context fixture count mismatch")
    event_keys = [match["event_key"] for match in slate["matches"]]
    if len(event_keys) != len(set(event_keys)):
        raise ValueError("slate context contains duplicate event IDs")
    schedule_date = date.fromisoformat(slate["schedule_date"])
    season = schedule_date.year
    registry = _registry(archive)
    profiles: dict[tuple[str, int], dict[str, object]] = {}
    profile_sources: dict[str, dict[str, object]] = {}
    tournament_tours: dict[int, str] = {}
    for match in slate["matches"]:
        key = int(match["tournament_key"])
        tour = match["tour"]
        if key in tournament_tours and tournament_tours[key] != tour:
            raise ValueError(f"tournament {key} has conflicting tours")
        tournament_tours[key] = tour
    for tournament_key, tour in sorted(tournament_tours.items()):
        name = f"api-tennis-metadata-get_players-{tournament_key}-{season}"
        player_rows, evidence = _verified_metadata(retained_root, name)
        profile_sources[name] = evidence
        for profile in player_rows:
            player_key = int(profile["player_key"])
            profile_key = (tour, player_key)
            if profile_key in profiles and profiles[profile_key] != profile:
                raise ValueError(f"conflicting profile for {profile_key}")
            profiles[profile_key] = profile

    results = []
    statuses: Counter[str] = Counter()
    for match in slate["matches"]:
        reason = None
        candidates: list[str] = []
        failure_player_key: int | None = None
        failure_name: str | None = None
        if match["fixture_status_at_capture"] != "1":
            reason = "NON_SCHEDULED_STATUS"
        elif not match["fields"]["draw_identity"]:
            reason = "FIXTURE_DRAW_ID_CONFLICT"
        else:
            for player_key in match["fixture_player_keys"]:
                profile = profiles.get((match["tour"], int(player_key)))
                if profile is None:
                    reason = "PROFILE_MISSING"
                    failure_player_key = int(player_key)
                    break
                birth = _date_from_api(profile.get("player_bday"))
                if birth is None:
                    reason = "BIRTHDATE_MISSING"
                    failure_player_key = int(player_key)
                    break
                name = profile.get("player_full_name")
                if not isinstance(name, str) or not name.strip():
                    reason = "FULL_NAME_MISSING"
                    failure_player_key = int(player_key)
                    break
                ids = registry.get((match["tour"], normalize_player_name(name), birth), set())
                if not ids:
                    reason = "NO_EXACT_REGISTRY_MATCH"
                    failure_player_key = int(player_key)
                    failure_name = name
                    break
                if len(ids) != 1:
                    reason = "AMBIGUOUS_REGISTRY_MATCH"
                    failure_player_key = int(player_key)
                    failure_name = name
                    break
                candidates.append(next(iter(ids)))
            if reason is None and candidates[0] == candidates[1]:
                reason = "DUPLICATE_CANONICAL_ID"
        status = "EXACT_CANDIDATE" if reason is None else reason
        statuses[status] += 1
        results.append(
            {
                "event_key": match["event_key"],
                "tour": match["tour"],
                "tournament_key": match["tournament_key"],
                "api_player_keys": match["fixture_player_keys"],
                "canonical_player_ids": candidates if reason is None else None,
                "failure_player_key": failure_player_key,
                "failure_profile_name": failure_name,
                "status": status,
                "production_admitted": False,
            }
        )
    return {
        "schema_version": "tennis-genome-api-tennis-crosswalk-proposals-v1",
        "schedule_date": schedule_date.isoformat(),
        "pinned_archive_sha256": _sha(archive.read_bytes()),
        "slate_report_sha256": _sha(slate_raw),
        "profile_sources": profile_sources,
        "match_count": len(results),
        "status_counts": dict(sorted(statuses.items())),
        "production_admitted": False,
        "matches": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--retained-root", type=Path, required=True)
    parser.add_argument("--slate-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = propose(
        archive=args.archive,
        retained_root=args.retained_root,
        slate_report=args.slate_report,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps({"match_count": result["match_count"], "status_counts": result["status_counts"]})
    )


if __name__ == "__main__":
    main()
