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
_ALLOWED_SURFACES = {"Hard", "Clay", "Grass", "Carpet"}


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


def _required_text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _required_int(value: object, *, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be an integer")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be an integer") from exc


def _slug(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not slug:
        raise ValueError("cannot build an empty slug")
    return slug


def _normalize_name(value: str) -> str:
    return _slug(value).replace("-", "")


def _first_value(raw: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in raw and raw[key] not in (None, ""):
            return raw[key]
    return None


def _player(match: dict[str, Any], side: str) -> tuple[str, str]:
    if side not in {"A", "B"}:
        raise ValueError("player side must be A or B")
    number = "1" if side == "A" else "2"
    nested = _first_value(
        match,
        (
            f"Player{side}",
            f"Player{number}",
            f"Entrant{side}",
            f"Entrant{number}",
        ),
    )
    player_id: Any = None
    name: Any = None
    if isinstance(nested, dict):
        player_id = _first_value(nested, ("id", "ID", "playerId", "PlayerID"))
        name = _first_value(
            nested,
            ("fullName", "FullName", "name", "Name", "displayName"),
        )
        if not name:
            first = _first_value(nested, ("firstName", "FirstName", "first"))
            last = _first_value(nested, ("lastName", "LastName", "last"))
            if isinstance(first, str) and isinstance(last, str):
                name = f"{first.strip()} {last.strip()}".strip()

    if player_id in (None, ""):
        player_id = _first_value(
            match,
            (
                f"Player{side}ID",
                f"Player{side}Id",
                f"Player{number}ID",
                f"Player{number}Id",
                f"PlayerID{number}",
                f"PlayerId{number}",
                f"Entrant{side}ID",
                f"Entrant{side}Id",
            ),
        )
    if not name:
        name = _first_value(
            match,
            (
                f"Player{side}Name",
                f"Player{number}Name",
                f"PlayerName{number}",
                f"Entrant{side}Name",
            ),
        )
    if not name:
        first = _first_value(
            match,
            (f"Player{side}FirstName", f"Player{number}FirstName"),
        )
        last = _first_value(
            match,
            (f"Player{side}LastName", f"Player{number}LastName"),
        )
        if isinstance(first, str) and isinstance(last, str):
            name = f"{first.strip()} {last.strip()}".strip()

    raw_id = str(player_id) if player_id is not None else ""
    return (
        _required_text(raw_id, field=f"player_{side.lower()}_id"),
        _required_text(name, field=f"player_{side.lower()}_name"),
    )


def _fixture_identity(
    scheduled_start: datetime,
    player_a: str,
    player_b: str,
) -> tuple[str, tuple[str, str]]:
    instant = scheduled_start.astimezone(UTC).isoformat()
    players = tuple(sorted((_normalize_name(player_a), _normalize_name(player_b))))
    return instant, players


def _existing_fixture_keys(
    repo_root: Path,
) -> tuple[set[str], set[tuple[str, tuple[str, str]]]]:
    ids: set[str] = set()
    identities: set[tuple[str, tuple[str, str]]] = set()
    fixtures_root = repo_root / "web-shadow" / "fixtures"
    if not fixtures_root.exists():
        return ids, identities

    for path in sorted(fixtures_root.glob("*.json")):
        payload = _load_json(path)
        match_id = _required_text(payload.get("match_id"), field="match_id")
        if match_id in ids:
            raise ValueError(f"duplicate existing fixture match_id: {match_id}")
        ids.add(match_id)
        start = _parse_time(payload.get("scheduled_start"), field="scheduled_start")
        player_a = _required_text(payload.get("player_a"), field="player_a")
        player_b = _required_text(payload.get("player_b"), field="player_b")
        identity = _fixture_identity(start, player_a, player_b)
        if identity in identities:
            raise ValueError(f"duplicate existing fixture identity: {path}")
        identities.add(identity)
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
    maximum_horizon = float(rule.get("maximum_horizon_hours", -1))
    maximum_matches = _required_int(
        rule.get("maximum_matches_per_slate"),
        field="maximum_matches_per_slate",
    )
    if minimum_lead < 0 or maximum_horizon <= minimum_lead:
        raise ValueError("intake selection_rule chronology is invalid")
    if maximum_matches <= 0:
        raise ValueError("maximum_matches_per_slate must be positive")

    seen_groups: set[tuple[int, int]] = set()
    seen_slugs: set[str] = set()
    for tournament in tournaments:
        if not isinstance(tournament, dict):
            raise ValueError("intake tournament entries must be objects")
        group_id = _required_int(tournament.get("group_id"), field="group_id")
        year = _required_int(tournament.get("year"), field="year")
        slug = _required_text(tournament.get("slug"), field="slug")
        if slug != _slug(slug):
            raise ValueError(f"configured tournament slug is not canonical: {slug}")
        pair = group_id, year
        if pair in seen_groups or slug in seen_slugs:
            raise ValueError("configured WTA tournaments must be unique")
        seen_groups.add(pair)
        seen_slugs.add(slug)
        _required_text(tournament.get("display_name"), field="display_name")
        _required_text(tournament.get("tournament_id"), field="tournament_id")
        if tournament.get("tournament_level") not in _ALLOWED_LEVELS:
            raise ValueError("configured tournament_level is outside frozen WTA map")
    return rule, tournaments


def _tournament_identity(payload: dict[str, Any]) -> tuple[int, int]:
    group = payload.get("tournamentGroup")
    if not isinstance(group, dict):
        raise ValueError("WTA tournament payload lacks tournamentGroup")
    return (
        _required_int(group.get("id"), field="tournamentGroup.id"),
        _required_int(payload.get("year"), field="tournament.year"),
    )


def _surface(payload: dict[str, Any]) -> str:
    raw = _required_text(payload.get("surface"), field="tournament.surface")
    canonical = {
        "hard": "Hard",
        "clay": "Clay",
        "grass": "Grass",
        "carpet": "Carpet",
    }.get(raw.lower())
    if canonical not in _ALLOWED_SURFACES:
        raise ValueError(f"unsupported WTA tournament surface: {raw}")
    return canonical


def _eligible_candidate(
    *,
    match: dict[str, Any],
    group_id: int,
    year: int,
    tournament: dict[str, Any],
    surface: str,
    observed: datetime,
    minimum_start: datetime,
    maximum_start: datetime,
    existing_ids: set[str],
    existing_identities: set[tuple[str, tuple[str, str]]],
    exclusions: Counter[str],
) -> dict[str, Any] | None:
    draw_type = _required_text(match.get("DrawMatchType"), field="DrawMatchType")
    state = _required_text(match.get("MatchState"), field="MatchState")
    if draw_type != "S":
        exclusions["not_singles"] += 1
        return None
    if state != "U":
        exclusions["not_upcoming"] += 1
        return None

    unscheduled = match.get("Unscheduled")
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

    event_id = _required_text(match.get("EventID"), field="EventID")
    source_match_id = _required_text(match.get("MatchID"), field="MatchID")
    start = _parse_time(match.get("MatchTimeStamp"), field="MatchTimeStamp")
    if start < minimum_start:
        exclusions["insufficient_lead_time"] += 1
        return None
    if start > maximum_start:
        exclusions["outside_horizon"] += 1
        return None

    round_id = _required_int(match.get("RoundID"), field="RoundID")
    round_name = _ROUND_ID_MAP.get(round_id)
    if round_name is None:
        exclusions["unsupported_round_id"] += 1
        return None

    player_a_id, player_a = _player(match, "A")
    player_b_id, player_b = _player(match, "B")
    if player_a_id == player_b_id or _normalize_name(player_a) == _normalize_name(player_b):
        raise ValueError("WTA upcoming singles row resolves duplicate players")

    official_match_id = f"web:wta:{group_id}:{year}:{event_id}"
    identity = _fixture_identity(start, player_a, player_b)
    if official_match_id in existing_ids or identity in existing_identities:
        exclusions["already_consumed"] += 1
        return None

    slug = str(tournament["slug"])
    fixture = WebShadowFixture(
        match_id=official_match_id,
        tour="WTA",
        tournament=str(tournament["display_name"]),
        round=round_name,
        surface=surface,
        scheduled_start=start.isoformat(),
        player_a=player_a,
        player_b=player_b,
        source_url=(
            f"https://www.wtatennis.com/tournaments/{group_id}/{slug}/{year}/draws"
        ),
        source_observed_at=observed.isoformat(),
        tournament_id=str(tournament["tournament_id"]),
        tournament_level=str(tournament["tournament_level"]),
        schedule_source_url=(
            f"https://api.wtatennis.com/tennis/tournaments/{group_id}/{year}/matches"
        ),
    )
    fixture.validate()
    return {
        "sort_key": (start, group_id, event_id, source_match_id),
        "fixture": fixture,
        "source": {
            "group_id": group_id,
            "year": year,
            "slug": slug,
            "event_id": event_id,
            "match_id": source_match_id,
            "round_id": round_id,
            "player_a_wta_id": player_a_id,
            "player_b_wta_id": player_b_id,
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
    seen_source_events: set[tuple[int, int, str]] = set()

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
        if _tournament_identity(tournament_payload) != (group_id, year):
            raise ValueError(f"WTA tournament identity mismatch for {slug}")
        surface = _surface(tournament_payload)
        matches = matches_payload.get("matches")
        if not isinstance(matches, list):
            raise ValueError(f"WTA matches payload lacks matches array for {slug}")

        source_records.append(
            {
                "slug": slug,
                "group_id": group_id,
                "year": year,
                "tournament_sha256": _sha256_file(tournament_path),
                "matches_sha256": _sha256_file(matches_path),
                "source_url": (
                    f"https://api.wtatennis.com/tennis/tournaments/{group_id}/{year}"
                ),
                "matches_source_url": (
                    f"https://api.wtatennis.com/tennis/tournaments/"
                    f"{group_id}/{year}/matches"
                ),
                "raw_match_count": len(matches),
            }
        )

        for index, match in enumerate(matches):
            if not isinstance(match, dict):
                raise ValueError(f"WTA match row must be an object: {slug}[{index}]")
            draw_type = match.get("DrawMatchType")
            state = match.get("MatchState")
            if draw_type != "S":
                if not isinstance(draw_type, str) or not draw_type:
                    raise ValueError("DrawMatchType must be a non-empty string")
                exclusions["not_singles"] += 1
                continue
            if state != "U":
                if not isinstance(state, str) or not state:
                    raise ValueError("MatchState must be a non-empty string")
                exclusions["not_upcoming"] += 1
                continue

            event_id = _required_text(match.get("EventID"), field="EventID")
            source_key = group_id, year, event_id
            if source_key in seen_source_events:
                raise ValueError(f"duplicate WTA EventID in intake sources: {source_key}")
            seen_source_events.add(source_key)

            candidate = _eligible_candidate(
                match=match,
                group_id=group_id,
                year=year,
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
    capacity_excluded = max(0, len(candidates) - len(selected))
    if capacity_excluded:
        exclusions["capacity"] = capacity_excluded
    if not selected:
        raise RuntimeError("deterministic WTA intake found no eligible unseen matches")

    source_match_count = sum(row["raw_match_count"] for row in source_records)
    exclusion_counts = {
        key: value for key, value in sorted(exclusions.items()) if value
    }
    excluded_match_count = sum(exclusion_counts.values())
    if source_match_count != len(selected) + excluded_match_count:
        raise RuntimeError("WTA intake source denominator accounting drift")
    if len(candidates) != len(selected) + capacity_excluded:
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
            event_slug = _slug(str(source["event_id"]))
            filename = (
                f"{source['slug']}-{source['year']}-{fixture.round.lower()}-"
                f"{event_slug}-{_slug(fixture.player_a)}-"
                f"{_slug(fixture.player_b)}.json"
            )
            if filename in used_names:
                raise ValueError(
                    f"deterministic intake fixture filename collision: {filename}"
                )
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
                "draw_match_type": "S",
                "match_state": "U",
                "require_scheduled": True,
                "round_id_map": {
                    str(key): value for key, value in _ROUND_ID_MAP.items()
                },
                "sort_order": [
                    "scheduled_start",
                    "group_id",
                    "event_id",
                    "match_id",
                ],
            },
            "source_records": source_records,
            "source_match_count": source_match_count,
            "pre_capacity_eligible_count": len(candidates),
            "selected_match_count": len(selected),
            "excluded_match_count": excluded_match_count,
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
