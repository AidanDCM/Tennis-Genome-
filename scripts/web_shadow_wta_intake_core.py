from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
import unicodedata
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from tennis_genome.prospective.web_shadow import WebShadowFixture

_CONFIG_SCHEMA = "tennis-genome-web-shadow-intake-config-v1"
_MANIFEST_SCHEMA = "tennis-genome-web-shadow-wta-intake-v1"
_ROUND_ID_MAP = {
    1: "F",
    2: "SF",
    3: "QF",
    4: "R16",
    5: "R32",
    6: "R64",
    7: "R128",
}
_ALLOWED_LEVELS = {"G", "PM", "P", "I", "F"}
_SURFACE_MAP = {
    "hard": "Hard",
    "clay": "Clay",
    "grass": "Grass",
    "carpet": "Carpet",
}


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON must contain an object: {path}")
    return payload


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_time(value: object, *, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.strip())
    except ValueError as exc:
        raise ValueError(f"{field} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return parsed


def _text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _integer(value: object, *, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be an integer")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be an integer") from exc


def _slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    normalized = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")
    if not slug:
        raise ValueError("cannot build an empty slug")
    return slug


def _name_key(value: str) -> str:
    return _slug(value).replace("-", "")


def _player(match: dict[str, Any], side: str) -> tuple[str, str]:
    player_id = _text(match.get(f"PlayerID{side}"), field=f"PlayerID{side}")
    first = _text(
        match.get(f"PlayerNameFirst{side}"),
        field=f"PlayerNameFirst{side}",
    )
    last = _text(
        match.get(f"PlayerNameLast{side}"),
        field=f"PlayerNameLast{side}",
    )
    return player_id, f"{first} {last}"


def _identity(
    start: datetime,
    player_a: str,
    player_b: str,
) -> tuple[str, tuple[str, str]]:
    instant = start.astimezone(UTC).isoformat()
    players = tuple(sorted((_name_key(player_a), _name_key(player_b))))
    return instant, players


def _existing_fixture_keys(
    repo_root: Path,
) -> tuple[set[str], set[tuple[str, tuple[str, str]]]]:
    ids: set[str] = set()
    identities: set[tuple[str, tuple[str, str]]] = set()
    root = repo_root / "web-shadow" / "fixtures"
    if not root.exists():
        return ids, identities
    for path in sorted(root.glob("*.json")):
        fixture = _load_json(path)
        match_id = _text(fixture.get("match_id"), field="match_id")
        if match_id in ids:
            raise ValueError(f"duplicate existing fixture match_id: {match_id}")
        ids.add(match_id)
        start = _parse_time(
            fixture.get("scheduled_start"),
            field="scheduled_start",
        )
        player_a = _text(fixture.get("player_a"), field="player_a")
        player_b = _text(fixture.get("player_b"), field="player_b")
        identities.add(_identity(start, player_a, player_b))
    return ids, identities


def _validate_config(
    config: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if config.get("schema_version") != _CONFIG_SCHEMA:
        raise ValueError("unsupported Web Shadow intake config schema")
    if config.get("production_eligible") is not False:
        raise ValueError("Web Shadow intake config must remain non-production")
    rule = config.get("selection_rule")
    tournaments = config.get("tournaments")
    if not isinstance(rule, dict):
        raise ValueError("intake config must define selection_rule")
    if not isinstance(tournaments, list) or not tournaments:
        raise ValueError("intake config must define tournaments")
    minimum_lead = float(rule.get("minimum_lead_hours", -1))
    horizon = float(rule.get("maximum_horizon_hours", -1))
    maximum = _integer(
        rule.get("maximum_matches_per_slate"),
        field="maximum_matches_per_slate",
    )
    if minimum_lead < 0 or horizon <= minimum_lead or maximum <= 0:
        raise ValueError("intake selection_rule is invalid")

    groups: set[tuple[int, int]] = set()
    slugs: set[str] = set()
    for tournament in tournaments:
        if not isinstance(tournament, dict):
            raise ValueError("intake tournament entries must be objects")
        group_id = _integer(tournament.get("group_id"), field="group_id")
        year = _integer(tournament.get("year"), field="year")
        slug = _text(tournament.get("slug"), field="slug")
        if slug != _slug(slug):
            raise ValueError(f"configured tournament slug is not canonical: {slug}")
        if (group_id, year) in groups or slug in slugs:
            raise ValueError("configured WTA tournaments must be unique")
        groups.add((group_id, year))
        slugs.add(slug)
        _text(tournament.get("display_name"), field="display_name")
        _text(tournament.get("tournament_id"), field="tournament_id")
        if tournament.get("tournament_level") not in _ALLOWED_LEVELS:
            raise ValueError("configured tournament_level is outside frozen WTA map")
    return rule, tournaments


def _tournament_metadata(
    payload: dict[str, Any],
    *,
    group_id: int,
    year: int,
) -> str:
    group = payload.get("tournamentGroup")
    if not isinstance(group, dict):
        raise ValueError("WTA tournament payload lacks tournamentGroup")
    if _integer(group.get("id"), field="tournamentGroup.id") != group_id:
        raise ValueError("WTA tournament identity mismatch")
    if _integer(payload.get("year"), field="tournament.year") != year:
        raise ValueError("WTA tournament identity mismatch")
    surface = _text(payload.get("surface"), field="tournament.surface")
    canonical = _SURFACE_MAP.get(surface.lower())
    if canonical is None:
        raise ValueError(f"unsupported WTA tournament surface: {surface}")
    return canonical


def _candidate(
    *,
    match: dict[str, Any],
    tournament: dict[str, Any],
    surface: str,
    observed: datetime,
    minimum_start: datetime,
    maximum_start: datetime,
    existing_ids: set[str],
    existing_identities: set[tuple[str, tuple[str, str]]],
    exclusions: Counter[str],
) -> dict[str, Any] | None:
    if match.get("DrawMatchType") != "S":
        exclusions["not_singles"] += 1
        return None
    if match.get("DrawLevelType") != "M":
        exclusions["not_main_draw"] += 1
        return None
    if match.get("MatchState") != "U":
        exclusions["not_upcoming"] += 1
        return None

    unscheduled = match.get("Unscheduled", False)
    if not isinstance(unscheduled, bool):
        raise ValueError("upcoming WTA singles row has non-boolean Unscheduled")
    not_before = match.get("NotBefore")
    followed_by = (
        isinstance(not_before, str)
        and not_before.strip().lower() == "followed by"
    )
    if unscheduled or followed_by:
        exclusions["unscheduled"] += 1
        return None

    group_id = int(tournament["group_id"])
    year = int(tournament["year"])
    event_id = _text(match.get("EventID"), field="EventID")
    event_year = _integer(match.get("EventYear"), field="EventYear")
    if event_id != str(group_id) or event_year != year:
        raise ValueError("WTA match row tournament identity mismatch")

    source_match_id = _text(match.get("MatchID"), field="MatchID")
    start = _parse_time(match.get("MatchTimeStamp"), field="MatchTimeStamp")
    if start < minimum_start:
        exclusions["insufficient_lead_time"] += 1
        return None
    if start > maximum_start:
        exclusions["outside_horizon"] += 1
        return None

    round_id = _integer(match.get("RoundID"), field="RoundID")
    round_name = _ROUND_ID_MAP.get(round_id)
    if round_name is None:
        exclusions["unsupported_round_id"] += 1
        return None

    player_a_id, player_a = _player(match, "A")
    player_b_id, player_b = _player(match, "B")
    if player_a_id == player_b_id or _name_key(player_a) == _name_key(player_b):
        raise ValueError("WTA upcoming singles row resolves duplicate players")

    official_id = f"web:wta:{group_id}:{year}:{source_match_id}"
    if official_id in existing_ids or _identity(start, player_a, player_b) in existing_identities:
        exclusions["already_consumed"] += 1
        return None

    slug = str(tournament["slug"])
    schedule_url = (
        f"https://api.wtatennis.com/tennis/tournaments/"
        f"{group_id}/{year}/matches"
    )
    fixture = WebShadowFixture(
        match_id=official_id,
        tour="WTA",
        tournament=str(tournament["display_name"]),
        round=round_name,
        surface=surface,
        scheduled_start=start.isoformat(),
        player_a=player_a,
        player_b=player_b,
        source_url=schedule_url,
        source_observed_at=observed.isoformat(),
        tournament_id=str(tournament["tournament_id"]),
        tournament_level=str(tournament["tournament_level"]),
        schedule_source_url=schedule_url,
    )
    fixture.validate()
    return {
        "sort_key": (start, group_id, source_match_id),
        "fixture": fixture,
        "source": {
            "group_id": group_id,
            "year": year,
            "event_id": event_id,
            "source_match_id": source_match_id,
            "round_id": round_id,
            "player_a_wta_id": player_a_id,
            "player_b_wta_id": player_b_id,
            "slug": slug,
        },
    }


def build_wta_web_shadow_intake(
    *,
    config_path: Path,
    source_root: Path,
    repo_root: Path,
    observed_at: str,
    snapshot_id: str,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    source_root = source_root.resolve()
    observed = _parse_time(observed_at, field="observed_at")
    if snapshot_id != _slug(snapshot_id):
        raise ValueError("snapshot_id must be a canonical slug")
    config = _load_json(config_path)
    rule, tournaments = _validate_config(config)
    minimum_start = observed + timedelta(hours=float(rule["minimum_lead_hours"]))
    maximum_start = observed + timedelta(hours=float(rule["maximum_horizon_hours"]))
    maximum_matches = int(rule["maximum_matches_per_slate"])
    existing_ids, existing_identities = _existing_fixture_keys(repo_root)

    candidates: list[dict[str, Any]] = []
    exclusions: Counter[str] = Counter()
    source_records: list[dict[str, Any]] = []
    seen_matches: set[tuple[int, int, str]] = set()

    for tournament in tournaments:
        group_id = int(tournament["group_id"])
        year = int(tournament["year"])
        slug = str(tournament["slug"])
        tournament_path = source_root / f"{slug}-tournament.json"
        matches_path = source_root / f"{slug}-matches.json"
        if not tournament_path.is_file() or not matches_path.is_file():
            raise FileNotFoundError(f"missing retained WTA source files for {slug}")
        tournament_payload = _load_json(tournament_path)
        matches_payload = _load_json(matches_path)
        surface = _tournament_metadata(
            tournament_payload,
            group_id=group_id,
            year=year,
        )
        matches = matches_payload.get("matches")
        if not isinstance(matches, list):
            raise ValueError(f"WTA matches payload lacks matches array for {slug}")
        source_records.append(
            {
                "slug": slug,
                "group_id": group_id,
                "year": year,
                "raw_match_count": len(matches),
                "tournament_sha256": _sha256_file(tournament_path),
                "matches_sha256": _sha256_file(matches_path),
                "source_url": (
                    f"https://api.wtatennis.com/tennis/tournaments/"
                    f"{group_id}/{year}"
                ),
                "matches_source_url": (
                    f"https://api.wtatennis.com/tennis/tournaments/"
                    f"{group_id}/{year}/matches"
                ),
            }
        )

        for index, match in enumerate(matches):
            if not isinstance(match, dict):
                raise ValueError(f"WTA match row must be an object: {slug}[{index}]")
            if match.get("DrawMatchType") != "S":
                exclusions["not_singles"] += 1
                continue
            if match.get("DrawLevelType") != "M":
                exclusions["not_main_draw"] += 1
                continue
            if match.get("MatchState") != "U":
                exclusions["not_upcoming"] += 1
                continue
            source_match_id = _text(match.get("MatchID"), field="MatchID")
            source_key = group_id, year, source_match_id
            if source_key in seen_matches:
                raise ValueError(f"duplicate WTA MatchID in intake sources: {source_key}")
            seen_matches.add(source_key)
            candidate = _candidate(
                match=match,
                tournament=tournament,
                surface=surface,
                observed=observed,
                minimum_start=minimum_start,
                maximum_start=maximum_start,
                existing_ids=existing_ids,
                existing_identities=existing_identities,
                exclusions=exclusions,
            )
            if candidate is not None:
                candidates.append(candidate)

    candidates.sort(key=lambda item: item["sort_key"])
    selected = candidates[:maximum_matches]
    capacity = max(0, len(candidates) - len(selected))
    if capacity:
        exclusions["capacity"] = capacity
    if not selected:
        raise RuntimeError("deterministic WTA intake found no eligible unseen matches")

    source_count = sum(row["raw_match_count"] for row in source_records)
    exclusion_counts = {
        key: value for key, value in sorted(exclusions.items()) if value
    }
    excluded_count = sum(exclusion_counts.values())
    if source_count != len(selected) + excluded_count:
        raise RuntimeError("WTA intake source denominator accounting drift")
    if len(candidates) != len(selected) + capacity:
        raise RuntimeError("WTA intake capacity accounting drift")

    active_slate = repo_root / "web-shadow" / "active-slate.json"
    evidence_root = repo_root / "web-shadow" / "intake-evidence" / snapshot_id
    if evidence_root.exists():
        raise FileExistsError(f"intake evidence snapshot already exists: {evidence_root}")
    original_active = active_slate.read_bytes() if active_slate.exists() else None
    created_fixtures: list[Path] = []

    with tempfile.TemporaryDirectory(prefix="wta-intake-") as temp_name:
        staging = Path(temp_name)
        staged_fixtures: list[tuple[Path, Path]] = []
        fixture_paths: list[str] = []
        selected_rows: list[dict[str, Any]] = []
        used_names: set[str] = set()
        for item in selected:
            fixture: WebShadowFixture = item["fixture"]
            source: dict[str, Any] = item["source"]
            filename = (
                f"{source['slug']}-{source['year']}-{fixture.round.lower()}-"
                f"{_slug(str(source['source_match_id']))}-"
                f"{_slug(fixture.player_a)}-{_slug(fixture.player_b)}.json"
            )
            if filename in used_names:
                raise ValueError(f"intake fixture filename collision: {filename}")
            used_names.add(filename)
            destination = repo_root / "web-shadow" / "fixtures" / filename
            if destination.exists():
                raise FileExistsError(f"intake fixture already exists: {destination}")
            staged = staging / "fixtures" / filename
            _write_json(staged, fixture.__dict__)
            staged_fixtures.append((staged, destination))
            repo_path = destination.relative_to(repo_root).as_posix()
            fixture_paths.append(repo_path)
            selected_rows.append(
                {
                    **source,
                    "fixture_path": repo_path,
                    "match_id": fixture.match_id,
                    "scheduled_start": fixture.scheduled_start,
                    "round": fixture.round,
                }
            )

        staged_active = staging / "active-slate.json"
        _write_json(
            staged_active,
            {
                "fixture_paths": fixture_paths,
                "rerun_reason": f"automatic-wta-intake-{snapshot_id}",
            },
        )
        manifest = {
            "schema_version": _MANIFEST_SCHEMA,
            "production_eligible": False,
            "snapshot_id": snapshot_id,
            "observed_at": observed.isoformat(),
            "selection_rule": {
                "minimum_lead_hours": float(rule["minimum_lead_hours"]),
                "maximum_horizon_hours": float(rule["maximum_horizon_hours"]),
                "maximum_matches_per_slate": maximum_matches,
                "draw_level_type": "M",
                "draw_match_type": "S",
                "match_state": "U",
                "round_id_map": {
                    str(key): value for key, value in _ROUND_ID_MAP.items()
                },
                "sort_order": [
                    "scheduled_start",
                    "group_id",
                    "source_match_id",
                ],
            },
            "source_records": source_records,
            "source_match_count": source_count,
            "pre_capacity_eligible_count": len(candidates),
            "selected_match_count": len(selected),
            "excluded_match_count": excluded_count,
            "exclusion_counts": exclusion_counts,
            "selected": selected_rows,
        }
        staged_manifest = staging / "intake-manifest.json"
        _write_json(staged_manifest, manifest)

        try:
            evidence_root.mkdir(parents=True)
            shutil.copyfile(staged_manifest, evidence_root / "intake-manifest.json")
            for record in source_records:
                slug = str(record["slug"])
                source_dir = evidence_root / slug
                source_dir.mkdir(parents=True)
                shutil.copyfile(
                    source_root / f"{slug}-tournament.json",
                    source_dir / "tournament.json",
                )
                shutil.copyfile(
                    source_root / f"{slug}-matches.json",
                    source_dir / "matches.json",
                )
            for staged, destination in staged_fixtures:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(staged, destination)
                created_fixtures.append(destination)
            active_slate.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(staged_active, active_slate)
        except Exception:
            if original_active is None:
                active_slate.unlink(missing_ok=True)
            else:
                active_slate.write_bytes(original_active)
            for path in reversed(created_fixtures):
                path.unlink(missing_ok=True)
            shutil.rmtree(evidence_root, ignore_errors=True)
            raise

    return manifest
