from __future__ import annotations

import json
import types
from datetime import UTC, datetime, timedelta
from pathlib import Path

from tennis_genome.data.canonical import PreMatchState

FORWARD_PROTOCOL = "FULL-STACK-FORWARD-004"
MIN_CAPTURE_LEAD = timedelta(minutes=90)


def _load_forward_module():
    source_path = Path(__file__).with_name("wta_live_prediction_002.py")
    source = source_path.read_text(encoding="utf-8")
    source = source.replace("FULL-STACK-FORWARD-001-", f"{FORWARD_PROTOCOL}-")
    module = types.ModuleType("wta_live_prediction_002_forward_004")
    module.__file__ = str(source_path)
    exec(compile(source, str(source_path), "exec"), module.__dict__)
    return module


def _load_provider_summaries(pages_dir: Path) -> list[dict[str, object]]:
    summaries: list[dict[str, object]] = []
    for path in sorted(pages_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload.get("summaries")
        if not isinstance(rows, list):
            raise RuntimeError(f"{path} does not contain a summaries array")
        for row in rows:
            if not isinstance(row, dict):
                raise RuntimeError(f"{path} contains a non-object summary")
            summaries.append(row)
    if not summaries:
        raise RuntimeError("trusted provider capture contains no summaries")
    return summaries


def _capture_observed_at(receipt_path: Path) -> datetime:
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    value = datetime.fromisoformat(str(receipt.get("observed_at", "")))
    if value.tzinfo is None or value.utcoffset() is None:
        raise RuntimeError("trusted provider observed_at must be timezone-aware")
    return value


def _eligible_target(
    h,
    summary: dict[str, object],
    *,
    by_name,
    earliest_start: datetime,
) -> tuple[datetime, str, str, str, str, str] | None:
    event = summary.get("sport_event")
    status = summary.get("sport_event_status")
    if not isinstance(event, dict) or not isinstance(status, dict):
        return None
    context = event.get("sport_event_context")
    if not isinstance(context, dict):
        return None
    category = context.get("category")
    competition = context.get("competition")
    season = context.get("season")
    if (
        not isinstance(category, dict)
        or str(category.get("id", "")) != "sr:category:6"
        or not isinstance(competition, dict)
        or str(competition.get("type", "")).lower() != "singles"
        or str(competition.get("level", "")).lower() not in h.ALLOWED_LEVELS
        or not isinstance(season, dict)
    ):
        return None
    if str(status.get("status", "")).lower() not in {"not_started", "scheduled"}:
        return None
    if event.get("start_time_confirmed") is not True:
        return None

    event_id = str(event.get("id", ""))
    season_id = str(season.get("id", ""))
    competition_id = str(competition.get("id", ""))
    if not event_id or not season_id or not competition_id:
        return None
    try:
        scheduled = datetime.fromisoformat(str(event.get("start_time", "")))
    except ValueError:
        return None
    if scheduled.tzinfo is None or scheduled.utcoffset() is None:
        return None
    if scheduled < earliest_start:
        return None

    try:
        home, away = h.qualified_competitors(event)
    except ValueError:
        return None
    home_sr = str(home.get("id", ""))
    away_sr = str(away.get("id", ""))
    home_id = h.resolve_competitor(home, by_name, {})
    away_id = h.resolve_competitor(away, by_name, {})
    if not home_sr or not away_sr or not home_id or not away_id or home_id == away_id:
        return None

    ordered = sorted(((home_id, home_sr), (away_id, away_sr)), key=lambda item: item[0])
    (player_a_id, player_a_sr), (player_b_id, player_b_sr) = ordered
    return scheduled, event_id, player_a_id, player_a_sr, player_b_id, player_b_sr


def select_forward_004_target(
    h,
    *,
    summaries: list[dict[str, object]],
    by_name,
    capture_observed_at: datetime,
) -> tuple[dict[str, object], dict[str, str]]:
    if capture_observed_at.tzinfo is None or capture_observed_at.utcoffset() is None:
        raise ValueError("capture_observed_at must be timezone-aware")
    earliest_start = capture_observed_at + MIN_CAPTURE_LEAD
    candidates: list[
        tuple[datetime, str, dict[str, object], str, str, str, str]
    ] = []
    for summary in summaries:
        eligibility = _eligible_target(
            h,
            summary,
            by_name=by_name,
            earliest_start=earliest_start,
        )
        if eligibility is None:
            continue
        (
            scheduled,
            event_id,
            player_a_id,
            player_a_sr,
            player_b_id,
            player_b_sr,
        ) = eligibility
        candidates.append(
            (
                scheduled,
                event_id,
                summary,
                player_a_id,
                player_a_sr,
                player_b_id,
                player_b_sr,
            )
        )
    if not candidates:
        raise RuntimeError(
            "trusted capture has no resolvable pre-match WTA main-tour singles target "
            f"with at least {int(MIN_CAPTURE_LEAD.total_seconds() // 60)} minutes lead"
        )

    selected = min(candidates, key=lambda item: (item[0], item[1]))
    scheduled, event_id, summary, player_a_id, player_a_sr, player_b_id, player_b_sr = (
        selected
    )
    event = summary["sport_event"]
    context = event["sport_event_context"]
    season = context["season"]
    competition = context["competition"]
    resolution = {
        "schema_version": "wta-forward-004-target-resolution-v1",
        "forward_protocol": FORWARD_PROTOCOL,
        "selection_rule": "earliest_confirmed_resolvable_wta_main_tour_singles",
        "minimum_capture_lead_minutes": str(
            int(MIN_CAPTURE_LEAD.total_seconds() // 60)
        ),
        "capture_observed_at": capture_observed_at.isoformat(),
        "event_id": event_id,
        "season_id": str(season["id"]),
        "competition_id": str(competition["id"]),
        "tournament_start_date": str(season["start_date"]),
        "scheduled_start": scheduled.isoformat(),
        "player_a_canonical_id": player_a_id,
        "player_a_sportradar_id": player_a_sr,
        "player_b_canonical_id": player_b_id,
        "player_b_sportradar_id": player_b_sr,
    }
    return summary, resolution


def _generic_target_state(h, target_summary, target_info, by_id) -> PreMatchState:
    event = target_summary["sport_event"]
    context = event["sport_event_context"]
    home, away = h.qualified_competitors(event)
    explicit = {h.PARRY_SR: h.PARRY_CANONICAL, h.STEARNS_SR: h.STEARNS_CANONICAL}
    home_id = explicit[str(home["id"])]
    away_id = explicit[str(away["id"])]
    a_id, b_id = sorted((home_id, away_id))
    a_comp, b_comp = (home, away) if a_id == home_id else (away, home)
    a_row, b_row = by_id[a_id], by_id[b_id]

    competition = context.get("competition") or {}
    level = h.LEVEL_MAP.get(str(competition.get("level", "")).lower())
    if level is None:
        raise RuntimeError("target competition level is outside the frozen WTA map")

    season_info = target_info.get("season")
    if not isinstance(season_info, dict):
        raise RuntimeError("target season info missing")
    info = season_info.get("info")
    if not isinstance(info, dict):
        info = {}
    surface_key = (
        str(info.get("surface", ""))
        .strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )
    surface = h.SURFACE_MAP.get(surface_key)
    if surface is None:
        raise RuntimeError(f"target surface is unsupported: {surface_key!r}")

    round_obj = context.get("round")
    round_name = None
    if isinstance(round_obj, dict):
        round_name = h.ROUND_MAP.get(str(round_obj.get("name", "")).lower())
    mode = context.get("mode")
    best_of = h.optional_int(mode.get("best_of")) if isinstance(mode, dict) else None
    if best_of != 3:
        raise RuntimeError("Forward-004 WTA target must be best-of-3")

    return PreMatchState(
        match_id=h.TARGET_MATCH_ID,
        tour="WTA",
        event_date=h.TARGET_TOURNEY_DATE,
        source_order=10**9,
        tournament_id=h.TARGET_SEASON_ID,
        tournament_name=str(competition.get("name", "")),
        tournament_level=level,
        surface=surface,
        round=round_name,
        best_of=best_of,
        player_a_id=a_id,
        player_b_id=b_id,
        player_a_name=h.provider_full_name(str(a_comp["name"])),
        player_b_name=h.provider_full_name(str(b_comp["name"])),
        rank_a=None,
        rank_b=None,
        rank_points_a=None,
        rank_points_b=None,
        draw_size=h.optional_int(info.get("number_of_competitors")),
        seed_a=h.optional_int(a_comp.get("seed")),
        seed_b=h.optional_int(b_comp.get("seed")),
        entry_a=None,
        entry_b=None,
        hand_a=a_row["hand"] or None,
        hand_b=b_row["hand"] or None,
        height_cm_a=h.optional_int(a_row["height"]),
        height_cm_b=h.optional_int(b_row["height"]),
        age_years_a=h.age_years(a_row["dob"], h.TARGET_TOURNEY_DATE),
        age_years_b=h.age_years(b_row["dob"], h.TARGET_TOURNEY_DATE),
        ioc_a=a_row["country"] or None,
        ioc_b=b_row["country"] or None,
    )


def main() -> None:
    module = _load_forward_module()
    h = module.h
    by_name, _ = h.player_index(Path("data/wta_players.csv"))

    trusted_root = Path("trusted-provider-artifact")
    summaries = _load_provider_summaries(
        trusted_root / "trusted-provider-capture" / "pages"
    )
    observed_at = _capture_observed_at(
        trusted_root / "provider_batch_anchor_receipt.json"
    )
    target_summary, resolved = select_forward_004_target(
        h,
        summaries=summaries,
        by_name=by_name,
        capture_observed_at=observed_at,
    )

    receipt = json.loads(
        (trusted_root / "provider_batch_anchor_receipt.json").read_text(
            encoding="utf-8"
        )
    )
    anchor_comment_id = int(
        (trusted_root / "provider_batch_anchor_comment_id.txt")
        .read_text(encoding="utf-8")
        .strip()
    )
    resolved["provider_batch_record_sha256"] = str(receipt["batch_record_sha256"])
    resolved["provider_anchor_comment_id"] = str(anchor_comment_id)

    event = target_summary["sport_event"]
    h.TARGET_EVENT_ID = resolved["event_id"]
    h.TARGET_MATCH_ID = resolved["event_id"]
    h.TARGET_SEASON_ID = resolved["season_id"]
    h.TARGET_COMPETITION_ID = resolved["competition_id"]
    h.TARGET_TOURNEY_DATE = datetime.fromisoformat(
        resolved["tournament_start_date"]
    ).date()
    h.SCHEDULED_START = resolved["scheduled_start"]
    h.PARRY_CANONICAL = resolved["player_a_canonical_id"]
    h.STEARNS_CANONICAL = resolved["player_b_canonical_id"]
    h.PARRY_SR = resolved["player_a_sportradar_id"]
    h.STEARNS_SR = resolved["player_b_sportradar_id"]
    h.PROVIDER_BATCH_SHA = str(receipt["batch_record_sha256"])
    h.PROVIDER_ANCHOR_COMMENT_ID = anchor_comment_id

    original_http_json = h.http_json

    def trusted_target_http_json(path: str) -> dict[str, object]:
        if path == f"sport_events/{h.TARGET_EVENT_ID}/summary.json":
            return target_summary
        return original_http_json(path)

    h.http_json = trusted_target_http_json
    h.target_state_from_provider = (
        lambda summary, info, by_id: _generic_target_state(h, summary, info, by_id)
    )

    Path("forward-004-target-resolution.json").write_text(
        json.dumps(resolved, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    status = target_summary.get("sport_event_status")
    if not isinstance(status, dict) or str(status.get("status", "")).lower() not in {
        "not_started",
        "scheduled",
    }:
        raise RuntimeError("selected Forward-004 target ceased to be pre-match")
    if datetime.now(UTC) >= datetime.fromisoformat(h.SCHEDULED_START):
        raise RuntimeError("selected Forward-004 target is no longer pre-start")

    module.main()


if __name__ == "__main__":
    main()
