"""Bind retained standings and profile evidence to one pre-start WTA fixture."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date, datetime
from pathlib import Path


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _digest(value: object) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _load(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _verified_source(root: Path, raw_name: str, hash_key: str) -> tuple[dict, dict, dict]:
    raw_path = root / raw_name
    manifest_path = root / "manifest.json"
    receipt_path = root / "github-receipt.json"
    raw, manifest, receipt = _load(raw_path), _load(manifest_path), _load(receipt_path)
    if _hash_file(raw_path) != manifest.get(hash_key):
        raise ValueError(f"retained raw hash mismatch: {raw_path}")
    if _hash_file(manifest_path) != receipt.get("manifest_sha256"):
        raise ValueError(f"retained manifest hash mismatch: {manifest_path}")
    if receipt.get("repository") != "AidanDCM/Tennis-Genome-":
        raise ValueError("source receipt identifies a different repository")
    return raw, manifest, receipt


def build_evidence(
    *,
    target_state_path: Path,
    fixture_path: Path,
    standings_root: Path,
    profile_root: Path,
    standings_artifact_id: int,
    profile_artifact_id: int,
    output_path: Path,
) -> dict[str, object]:
    state, fixture = _load(target_state_path), _load(fixture_path)
    if state.get("tour") != "WTA" or fixture.get("tour") != "WTA":
        raise ValueError("ranking evidence builder currently supports WTA only")
    if state.get("match_id") != fixture.get("match_id"):
        raise ValueError("target and fixture mismatch")
    scheduled = datetime.fromisoformat(str(fixture["scheduled_start"]))
    event_date = date.fromisoformat(str(state["event_date"]))
    if scheduled.date() != event_date:
        raise ValueError("fixture and target dates differ")
    standings, standings_manifest, standings_receipt = _verified_source(
        standings_root, "raw-wta-standings.json", "raw_wta_sha256"
    )
    profiles, profile_manifest, profile_receipt = _verified_source(
        profile_root, "raw-response.json", "raw_sha256"
    )
    if standings.get("success") != 1 or profiles.get("success") != 1:
        raise ValueError("provider source response was unsuccessful")
    if profile_manifest.get("method") != "get_players":
        raise ValueError("player identity source is not get_players")
    if standings_artifact_id <= 0 or profile_artifact_id <= 0:
        raise ValueError("source artifact IDs must be positive")
    observed_at = datetime.fromisoformat(str(standings_manifest["observed_at_utc"]))
    profile_at = datetime.fromisoformat(str(profile_manifest["received_at_utc"]))
    if observed_at >= scheduled or profile_at >= scheduled:
        raise ValueError("ranking or profile source was captured after scheduled start")
    rows = []
    for side in ("a", "b"):
        name = str(state[f"player_{side}_name"])
        matches = [item for item in profiles["result"] if item.get("player_full_name") == name]
        if len(matches) != 1:
            raise ValueError(f"profile identity is missing or ambiguous for {name}")
        profile = matches[0]
        dob = datetime.strptime(str(profile["player_bday"]), "%d.%m.%Y").date()
        age = (event_date - dob).days / 365.2425
        if abs(age - float(state[f"age_years_{side}"])) > 0.02:
            raise ValueError(f"profile birthdate conflicts with canonical age for {name}")
        key = profile["player_key"]
        rank_matches = [item for item in standings["result"] if item.get("player_key") == key]
        if len(rank_matches) != 1 or rank_matches[0].get("player") != name:
            raise ValueError(f"standings identity is missing or ambiguous for {name}")
        ranking = rank_matches[0]
        if ranking.get("league") != "WTA":
            raise ValueError(f"standings tour differs for {name}")
        position, points = int(ranking["place"]), int(ranking["points"])
        if position <= 0 or points <= 0:
            raise ValueError(f"standings value is invalid for {name}")
        rows.append(
            {
                "canonical_player_id": state[f"player_{side}_id"],
                "player_name": name,
                "api_tennis_player_key": key,
                "birthdate": dob.isoformat(),
                "country": profile["player_country"],
                "rank": position,
                "rank_points": points,
            }
        )
    if rows[0]["api_tennis_player_key"] == rows[1]["api_tennis_player_key"]:
        raise ValueError("players resolve to the same provider identity")
    result = {
        "schema_version": "simple-logit-retained-ranking-evidence-v1",
        "match_id": state["match_id"],
        "player_a_id": rows[0]["canonical_player_id"],
        "player_b_id": rows[1]["canonical_player_id"],
        "players": rows,
        "observed_at_utc": observed_at.isoformat(),
        "profile_observed_at_utc": profile_at.isoformat(),
        "standings_run_id": standings_receipt["workflow_run_id"],
        "standings_artifact_id": standings_artifact_id,
        "standings_raw_sha256": standings_manifest["raw_wta_sha256"],
        "standings_manifest_sha256": standings_receipt["manifest_sha256"],
        "profile_run_id": profile_receipt["workflow_run_id"],
        "profile_artifact_id": profile_artifact_id,
        "profile_raw_sha256": profile_manifest["raw_sha256"],
        "profile_manifest_sha256": profile_receipt["manifest_sha256"],
        "ranking_effective_date_claimed": False,
        "production_eligible": False,
    }
    result["record_sha256"] = _digest(result)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n"
    if output_path.exists():
        if output_path.read_text(encoding="utf-8") != data:
            raise ValueError("existing ranking evidence differs")
    else:
        temporary = output_path.with_name(output_path.name + ".tmp")
        temporary.write_text(data, encoding="utf-8")
        temporary.replace(output_path)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-state", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--standings-root", type=Path, required=True)
    parser.add_argument("--profile-root", type=Path, required=True)
    parser.add_argument("--standings-artifact-id", type=int, required=True)
    parser.add_argument("--profile-artifact-id", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            build_evidence(
                target_state_path=args.target_state,
                fixture_path=args.fixture,
                standings_root=args.standings_root,
                profile_root=args.profile_root,
                standings_artifact_id=args.standings_artifact_id,
                profile_artifact_id=args.profile_artifact_id,
                output_path=args.output,
            ),
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
    )


if __name__ == "__main__":
    main()
