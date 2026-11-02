"""Audit retained API-Tennis slate context offline; never forecast or admit data."""

import argparse
import hashlib
import json
from collections import Counter
from datetime import date
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--retained-root", type=Path, required=True)
parser.add_argument("--schedule-date", required=True)
parser.add_argument("--standings-date", required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
BASE = args.retained_root
DATE = args.schedule_date
SEASON = date.fromisoformat(DATE).year
if date.fromisoformat(args.standings_date) > date.fromisoformat(DATE):
    raise ValueError("standings snapshot cannot be later than the scheduled slate")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def retained(name):
    outer = BASE / name
    root = outer / name
    manifest_bytes = (root / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    receipt = json.loads((root / "github-receipt.json").read_bytes())
    require(
        hashlib.sha256(manifest_bytes).hexdigest() == receipt["manifest_sha256"],
        f"{name}: manifest receipt mismatch",
    )
    raw_name = "raw-response.json" if name.startswith("api-tennis-metadata") else None
    if raw_name:
        raw = (root / raw_name).read_bytes()
        require(
            hashlib.sha256(raw).hexdigest() == manifest["raw_sha256"],
            f"{name}: raw response hash mismatch",
        )
        return json.loads(raw)["result"], manifest, receipt
    return root, manifest, receipt


inventory_name = f"api-tennis-daily-inventory-{DATE}"
inventory_root = BASE / inventory_name / inventory_name
inventory_manifest = json.loads((inventory_root / "manifest.json").read_bytes())
inventory_receipt = json.loads((inventory_root / "github-receipt.json").read_bytes())
require(
    hashlib.sha256((inventory_root / "manifest.json").read_bytes()).hexdigest()
    == inventory_receipt["manifest_file_sha256"],
    "fixture inventory manifest receipt mismatch",
)
inventory_raw = (inventory_root / "raw-fixtures.json").read_bytes()
require(
    hashlib.sha256(inventory_raw).hexdigest() == inventory_manifest["raw_sha256"],
    "fixture inventory raw hash mismatch",
)
require(
    inventory_manifest["raw_sha256"] == inventory_receipt["raw_sha256"],
    "fixture inventory raw receipt mismatch",
)
filtered_raw = (inventory_root / "atp-wta-singles.json").read_bytes()
require(
    hashlib.sha256(filtered_raw).hexdigest() == inventory_manifest["atp_wta_singles_sha256"],
    "fixture inventory filtered hash mismatch",
)
fixtures = json.loads(filtered_raw)["result"]

standing_name = f"api-tennis-trial-standings-{args.standings_date}"
standing_root, standing_manifest, standing_receipt = retained(standing_name)
standings = {}
for tour in ("atp", "wta"):
    raw = (standing_root / f"raw-{tour}-standings.json").read_bytes()
    require(
        hashlib.sha256(raw).hexdigest() == standing_manifest[f"raw_{tour}_sha256"],
        f"{tour}: standings raw hash mismatch",
    )
    standing_rows = json.loads(raw)["result"]
    standings[tour.upper()] = {int(row["player_key"]): row for row in standing_rows}
    require(
        len(standings[tour.upper()]) == len(standing_rows), f"{tour}: duplicate standings player ID"
    )

draw_matches = {}
surfaces = {}
players = {}
run_ids = {
    "inventory": inventory_receipt["workflow_run_id"],
    "standings": standing_receipt["workflow_run_id"],
}
for key in sorted({int(fixture["tournament_key"]) for fixture in fixtures}):
    draw_name = f"api-tennis-metadata-get_draw-{key}-{SEASON}"
    draw, manifest, receipt = retained(draw_name)
    run_ids[draw_name] = receipt["workflow_run_id"]
    for item in [draw] if isinstance(draw, dict) else draw:
        tournament = item["tournament"]
        require(int(tournament["tournament_key"]) == key, f"{draw_name}: tournament ID mismatch")
        surfaces[key] = tournament.get("tournament_surface")
        for bracket in item.get("brackets", []):
            for round_ in bracket.get("rounds", []):
                for match in round_.get("matches", []):
                    if match.get("match_key") is not None:
                        match_key = int(match["match_key"])
                        require(
                            match_key not in draw_matches, f"duplicate draw match ID: {match_key}"
                        )
                        draw_matches[match_key] = (key, match)
    player_name = f"api-tennis-metadata-get_players-{key}-{SEASON}"
    if (BASE / player_name / player_name / "manifest.json").exists():
        player_rows, _, receipt = retained(player_name)
        run_ids[player_name] = receipt["workflow_run_id"]
        for row in player_rows:
            player_key = int(row["player_key"])
            if player_key in players:
                require(
                    players[player_key]["player_full_name"] == row["player_full_name"],
                    f"conflicting player identity for {player_key}",
                )
            players[player_key] = row

rows = []
for fixture in fixtures:
    key = int(fixture["tournament_key"])
    tour = "ATP" if fixture["event_type_type"] == "Atp Singles" else "WTA"
    event_key = int(fixture["event_key"])
    ids = (int(fixture["first_player_key"]), int(fixture["second_player_key"]))
    draw = draw_matches.get(event_key)
    draw_ids = (
        [draw[1]["first_player"]["player_key"], draw[1]["second_player"]["player_key"]]
        if draw and draw[1].get("first_player") and draw[1].get("second_player")
        else None
    )
    identity_match = bool(draw and draw[0] == key and draw_ids and set(draw_ids) == set(ids))
    fields = {
        "draw_identity": identity_match,
        "surface": bool(surfaces.get(key)),
        "both_current_ranks": all(i in standings[tour] for i in ids),
        "both_birthdates": all(players.get(i, {}).get("player_bday") for i in ids),
    }
    rows.append(
        {
            "event_key": event_key,
            "tour": tour,
            "tournament_key": key,
            "players": [fixture["event_first_player"], fixture["event_second_player"]],
            "fixture_player_keys": list(ids),
            "draw_player_keys": draw_ids,
            "fixture_status_at_capture": fixture["event_status"],
            "surface": surfaces.get(key),
            "fields": fields,
            "missing": [name for name, present in fields.items() if not present],
            "production_eligible": False,
            "reason": (
                "Chronological full-stack player state and verified actual start "
                "are not established by these source captures"
            ),
        }
    )

coverage = {
    field: sum(row["fields"][field] for row in rows)
    for field in ("draw_identity", "surface", "both_current_ranks", "both_birthdates")
}
report = {
    "schema_version": "tennis-genome-offline-slate-field-audit-v1",
    "schedule_date": DATE,
    "source_run_ids": run_ids,
    "fixture_count": len(rows),
    "tour_counts": dict(Counter(row["tour"] for row in rows)),
    "status_counts_at_capture": dict(
        Counter(str(row["fixture_status_at_capture"]) for row in rows)
    ),
    "field_coverage": coverage,
    "full_stack_forecast_count": 0,
    "notes": [
        "This report verifies retained artifact bytes, not provider truth or "
        "complete tour coverage.",
        f"Current standings are a {args.standings_date} snapshot, not historical ranks.",
        "Draws may include results. Only identity and tournament context are inspected here.",
        "Scheduled fixture time is not verified actual start.",
        "A non-scheduled status needs independent chronology review before prediction.",
        "Provider player profiles do not contain height or handedness in tested responses.",
    ],
    "matches": rows,
}
path = args.output
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(
    json.dumps(
        {
            k: report[k]
            for k in ("fixture_count", "tour_counts", "field_coverage", "full_stack_forecast_count")
        },
        indent=2,
    )
)
print(path)
