from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from dataclasses import asdict, replace
from datetime import date, datetime
from pathlib import Path

from tennis_genome.data.identity import canonical_player_id
from tennis_genome.prospective.web_shadow import WebShadowFixture


def _normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.lower().replace("ß", "ss")
    return re.sub(r"[^a-z0-9]+", "", value)


def _load_fixture(path: Path) -> WebShadowFixture:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("fixture JSON must contain an object")
    fixture = WebShadowFixture(**raw)
    fixture.validate()
    if fixture.tour != "WTA":
        raise ValueError("automatic Web Shadow target-state builder supports WTA only")
    if not fixture.tournament_id.strip():
        raise ValueError("fixture tournament_id must be populated")
    if fixture.tournament_level not in {"G", "PM", "P", "I", "F"}:
        raise ValueError("fixture tournament_level is outside the frozen WTA level map")
    return fixture


def _load_registry(path: Path) -> dict[str, list[dict[str, str]]]:
    by_name: dict[str, list[dict[str, str]]] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        for row in reader:
            if len(row) < 7:
                continue
            player_id, first, last, hand, dob, country, height = [
                value.strip() for value in row[:7]
            ]
            if not player_id:
                continue
            key = _normalize_text(f"{first} {last}")
            by_name.setdefault(key, []).append(
                {
                    "id": player_id,
                    "first": first,
                    "last": last,
                    "hand": hand,
                    "dob": dob,
                    "country": country,
                    "height": height,
                }
            )
    if not by_name:
        raise ValueError("WTA player registry is empty")
    return by_name


def _resolve_player(
    name: str,
    *,
    registry: dict[str, list[dict[str, str]]],
) -> dict[str, str]:
    candidates = registry.get(_normalize_text(name), [])
    if not candidates:
        raise ValueError(f"player is absent from pinned WTA registry: {name}")
    if len(candidates) != 1:
        ids = ", ".join(sorted(candidate["id"] for candidate in candidates))
        raise ValueError(f"player name is ambiguous in pinned WTA registry: {name} ({ids})")
    return candidates[0]


def _optional_int(value: str) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _age_years(dob: str, event_date: date) -> float | None:
    if len(dob) != 8 or not dob.isdigit():
        return None
    try:
        born = date(int(dob[:4]), int(dob[4:6]), int(dob[6:8]))
    except ValueError:
        return None
    return (event_date - born).days / 365.2425


def build_web_shadow_target_state(
    *,
    fixture_path: Path,
    registry_path: Path,
    target_state_path: Path,
    normalized_fixture_path: Path,
) -> dict[str, object]:
    fixture = _load_fixture(fixture_path)
    registry = _load_registry(registry_path)
    source_players = [
        _resolve_player(fixture.player_a, registry=registry),
        _resolve_player(fixture.player_b, registry=registry),
    ]
    players = []
    for item in source_players:
        name = f"{item['first']} {item['last']}".strip()
        players.append(
            {
                **item,
                "canonical_id": canonical_player_id(
                    tour="WTA",
                    source_id=item["id"],
                    name=name,
                ),
            }
        )
    if players[0]["canonical_id"] == players[1]["canonical_id"]:
        raise ValueError("web fixture resolves both sides to the same canonical player")
    players.sort(key=lambda item: item["canonical_id"])

    scheduled = datetime.fromisoformat(fixture.scheduled_start)
    event_date = scheduled.date()
    names = [f"{item['first']} {item['last']}".strip() for item in players]
    normalized_fixture = replace(
        fixture,
        player_a=names[0],
        player_b=names[1],
    )
    normalized_fixture.validate()

    target = {
        "match_id": fixture.match_id,
        "tour": "WTA",
        "event_date": event_date.isoformat(),
        "source_order": 10**9,
        "tournament_id": fixture.tournament_id,
        "tournament_name": fixture.tournament,
        "tournament_level": fixture.tournament_level,
        "surface": fixture.surface,
        "round": fixture.round,
        "best_of": 3,
        "player_a_id": players[0]["canonical_id"],
        "player_b_id": players[1]["canonical_id"],
        "player_a_name": names[0],
        "player_b_name": names[1],
        "rank_a": None,
        "rank_b": None,
        "rank_points_a": None,
        "rank_points_b": None,
        "draw_size": None,
        "seed_a": None,
        "seed_b": None,
        "entry_a": None,
        "entry_b": None,
        "hand_a": players[0]["hand"] or None,
        "hand_b": players[1]["hand"] or None,
        "height_cm_a": _optional_int(players[0]["height"]),
        "height_cm_b": _optional_int(players[1]["height"]),
        "age_years_a": _age_years(players[0]["dob"], event_date),
        "age_years_b": _age_years(players[1]["dob"], event_date),
        "ioc_a": players[0]["country"] or None,
        "ioc_b": players[1]["country"] or None,
    }

    target_state_path.parent.mkdir(parents=True, exist_ok=True)
    target_state_path.write_text(
        json.dumps(target, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    normalized_fixture_path.parent.mkdir(parents=True, exist_ok=True)
    normalized_fixture_path.write_text(
        json.dumps(
            asdict(normalized_fixture),
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return target


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Resolve a Web Shadow WTA fixture against the pinned player registry"
    )
    parser.add_argument("--fixture", required=True, type=Path)
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--target-state", required=True, type=Path)
    parser.add_argument("--normalized-fixture", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    target = build_web_shadow_target_state(
        fixture_path=args.fixture,
        registry_path=args.registry,
        target_state_path=args.target_state,
        normalized_fixture_path=args.normalized_fixture,
    )
    print(json.dumps(target, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
