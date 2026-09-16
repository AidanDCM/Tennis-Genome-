from __future__ import annotations

import json
import types
from datetime import date
from pathlib import Path

TARGET_PLAYER_NAMES = {"magdalenafrech", "carolinedolehide"}


def _load_forward_module():
    source_path = Path(__file__).with_name("wta_live_prediction_002.py")
    source = source_path.read_text(encoding="utf-8")
    source = source.replace("FULL-STACK-FORWARD-001-", "FULL-STACK-FORWARD-003-")
    module = types.ModuleType("wta_live_prediction_002_forward_003")
    module.__file__ = str(source_path)
    exec(compile(source, str(source_path), "exec"), module.__dict__)
    return module


def _find_target_summary(h) -> dict[str, object]:
    pages_dir = Path("trusted-provider-artifact/trusted-provider-capture/pages")
    candidates: list[dict[str, object]] = []
    for path in sorted(pages_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload.get("summaries")
        if not isinstance(rows, list):
            continue
        for summary in rows:
            if not isinstance(summary, dict):
                continue
            event = summary.get("sport_event")
            status = summary.get("sport_event_status")
            if not isinstance(event, dict) or not isinstance(status, dict):
                continue
            context = event.get("sport_event_context")
            if not isinstance(context, dict):
                continue
            category = context.get("category") or {}
            competition = context.get("competition") or {}
            if (
                not isinstance(category, dict)
                or str(category.get("id")) != "sr:category:6"
            ):
                continue
            if (
                not isinstance(competition, dict)
                or str(competition.get("type", "")).lower() != "singles"
            ):
                continue
            competitors = event.get("competitors")
            if not isinstance(competitors, list) or len(competitors) != 2:
                continue
            names = {
                h.normalize_text(h.provider_full_name(str(comp.get("name", ""))))
                for comp in competitors
                if isinstance(comp, dict)
            }
            if names == TARGET_PLAYER_NAMES:
                candidates.append(summary)
    if len(candidates) != 1:
        raise RuntimeError(
            f"expected exactly one Frech-Dolehide target, found {len(candidates)}"
        )
    return candidates[0]


def main() -> None:
    module = _load_forward_module()
    h = module.h
    by_name, _ = h.player_index(Path("data/wta_players.csv"))
    target_summary = _find_target_summary(h)
    event = target_summary["sport_event"]
    context = event["sport_event_context"]
    status = target_summary["sport_event_status"]
    if str(status.get("status", "")).lower() not in {"not_started", "scheduled"}:
        raise RuntimeError(f"Frech-Dolehide is no longer pre-match: {status}")

    home, away = h.qualified_competitors(event)
    home_sr = str(home["id"])
    away_sr = str(away["id"])
    home_id = h.resolve_competitor(home, by_name, {})
    away_id = h.resolve_competitor(away, by_name, {})
    if not home_id or not away_id:
        raise RuntimeError(
            f"unable to resolve canonical target ids: home={home_id!r} away={away_id!r}"
        )
    if home_id == away_id:
        raise RuntimeError("target canonical ids are not unique")

    ordered = sorted(((home_id, home_sr), (away_id, away_sr)), key=lambda item: item[0])
    (player_a_id, player_a_sr), (player_b_id, player_b_sr) = ordered

    season = context.get("season")
    competition = context.get("competition")
    if not isinstance(season, dict) or not isinstance(competition, dict):
        raise RuntimeError("target season/competition context missing")
    scheduled_start = str(event.get("start_time", ""))
    if not scheduled_start:
        raise RuntimeError("target start time missing")

    receipt = json.loads(
        Path("trusted-provider-artifact/provider_batch_anchor_receipt.json").read_text(
            encoding="utf-8"
        )
    )
    anchor_comment_id = int(
        Path("trusted-provider-artifact/provider_batch_anchor_comment_id.txt")
        .read_text(encoding="utf-8")
        .strip()
    )

    h.TARGET_EVENT_ID = str(event["id"])
    h.TARGET_MATCH_ID = h.TARGET_EVENT_ID
    h.TARGET_SEASON_ID = str(season["id"])
    h.TARGET_COMPETITION_ID = str(competition["id"])
    h.TARGET_TOURNEY_DATE = date.fromisoformat(str(season["start_date"]))
    h.SCHEDULED_START = scheduled_start
    h.PARRY_CANONICAL = player_a_id
    h.STEARNS_CANONICAL = player_b_id
    h.PARRY_SR = player_a_sr
    h.STEARNS_SR = player_b_sr
    h.PROVIDER_BATCH_SHA = str(receipt["batch_record_sha256"])
    h.PROVIDER_ANCHOR_COMMENT_ID = anchor_comment_id

    resolved = {
        "schema_version": "wta-forward-003-target-resolution-v1",
        "forward_protocol": "FULL-STACK-FORWARD-003",
        "event_id": h.TARGET_EVENT_ID,
        "season_id": h.TARGET_SEASON_ID,
        "competition_id": h.TARGET_COMPETITION_ID,
        "tournament_start_date": h.TARGET_TOURNEY_DATE.isoformat(),
        "scheduled_start": h.SCHEDULED_START,
        "player_a_canonical_id": h.PARRY_CANONICAL,
        "player_a_sportradar_id": h.PARRY_SR,
        "player_b_canonical_id": h.STEARNS_CANONICAL,
        "player_b_sportradar_id": h.STEARNS_SR,
        "provider_batch_record_sha256": h.PROVIDER_BATCH_SHA,
        "provider_anchor_comment_id": h.PROVIDER_ANCHOR_COMMENT_ID,
    }
    Path("forward-003-target-resolution.json").write_text(
        json.dumps(resolved, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    module.main()


if __name__ == "__main__":
    main()
