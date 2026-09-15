from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import re
import time
import unicodedata
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path

from tennis_genome.calculator.contract import load_validated_matchup_calculator
from tennis_genome.calculator.io import load_matchup_input
from tennis_genome.data.canonical import HistoricalMatch, MatchOutcome, MatchStats, PreMatchState
from tennis_genome.data.parquet import load_canonical_parquet
from tennis_genome.features.foundational import walk_forward_foundational_features
from tennis_genome.prospective.pilot import ProspectivePilotStore, commit_prediction
from tennis_genome.prospective.provider_batch import ProviderBatchStore
from tennis_genome.prospective.settlement_identity import build_identity_binding, identity_as_dict
from tennis_genome.ratings.serve_return import walk_forward_serve_return

REPO = "AidanDCM/Tennis-Genome-"
TARGET_EVENT_ID = "sr:sport_event:74574094"
TARGET_SEASON_ID = "sr:season:136184"
TARGET_COMPETITION_ID = "sr:competition:33586"
TARGET_MATCH_ID = TARGET_EVENT_ID
TARGET_TOURNEY_DATE = date(2026, 9, 12)
SCHEDULED_START = "2026-09-15T23:00:00+00:00"
PARRY_SR = "sr:competitor:318195"
STEARNS_SR = "sr:competitor:360038"
PARRY_CANONICAL = "220348"
STEARNS_CANONICAL = "220548"
PROVIDER_BATCH_SHA = "5f23498164f45f03c2d79133e4e28d59d3ff51dd0ef105d70cd760bc3458ad10"
PROVIDER_ANCHOR_COMMENT_ID = 5684381781
ALLOWED_LEVELS = {"grand_slam", "wta_1000", "wta_500", "wta_250", "wta_championships"}
LEVEL_MAP = {
    "grand_slam": "G",
    "wta_1000": "PM",
    "wta_500": "P",
    "wta_250": "I",
    "wta_championships": "F",
}
SURFACE_MAP = {
    "hardcourt_outdoor": "Hard",
    "hardcourt_indoor": "Hard",
    "hard_court": "Hard",
    "hardcourt": "Hard",
    "hard": "Hard",
    "red_clay": "Clay",
    "green_clay": "Clay",
    "clay": "Clay",
    "grass": "Grass",
    "carpet_indoor": "Carpet",
    "carpet": "Carpet",
    "unknown": "Unknown",
}
ROUND_MAP = {
    "round_of_256": "R256",
    "round_of_128": "R128",
    "round_of_64": "R64",
    "round_of_32": "R32",
    "round_of_16": "R16",
    "quarterfinal": "QF",
    "semifinal": "SF",
    "final": "F",
    "qualification": "Q",
    "qualification_final": "QFNL",
    "qualification_round_1": "Q1",
    "qualification_round_2": "Q2",
    "round_1": "R1",
    "round_2": "R2",
    "round_3": "R3",
    "round_robin": "RR",
}


def canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def pretty(value: object) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"


def sha_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.lower().replace("ß", "ss")
    return re.sub(r"[^a-z0-9]+", "", value)


def provider_full_name(name: str) -> str:
    if "," in name:
        last, first = name.split(",", 1)
        return f"{first.strip()} {last.strip()}"
    return name.strip()


def optional_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def http_json(path: str) -> dict[str, object]:
    key = os.environ["SPORTRADAR_API_KEY"].strip()
    access = os.environ.get("SPORTRADAR_ACCESS_LEVEL", "trial").strip()
    if not key:
        raise RuntimeError("SPORTRADAR_API_KEY missing")
    url = f"https://api.sportradar.com/tennis/{access}/v3/en/{path.lstrip('/')}"
    for attempt in range(8):
        req = urllib.request.Request(
            url,
            headers={
                "x-api-key": key,
                "Accept": "application/json",
                "User-Agent": "tennis-genome-wta-live-prediction-001",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=45) as response:
                raw = response.read()
            value = json.loads(raw)
            if not isinstance(value, dict):
                raise RuntimeError("Sportradar response not object")
            time.sleep(0.85)
            return value
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt < 7:
                retry = exc.headers.get("Retry-After")
                delay = max(float(retry) if retry else 2.0 + attempt, 2.0)
                time.sleep(delay)
                continue
            raise
    raise RuntimeError("Sportradar retry budget exhausted")


def player_index(path: Path):
    by_name: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    by_id: dict[str, dict[str, str]] = {}
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 7:
                continue
            pid, first, last, hand, dob, country, height = [x.strip() for x in row[:7]]
            if not pid:
                continue
            item = {
                "id": pid,
                "first": first,
                "last": last,
                "hand": hand,
                "dob": dob,
                "country": country,
                "height": height,
            }
            by_id[pid] = item
            by_name[normalize_text(f"{first} {last}")].append(item)
    return by_name, by_id


def resolve_competitor(comp: dict[str, object], by_name, explicit: dict[str, str]) -> str | None:
    sr_id = str(comp.get("id", "")).strip()
    if sr_id in explicit:
        return explicit[sr_id]
    name = provider_full_name(str(comp.get("name", "")))
    candidates = list(by_name.get(normalize_text(name), []))
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]["id"]
    country = str(comp.get("country_code", "")).strip().upper()
    if country:
        country_candidates = [item for item in candidates if item["country"].upper() == country]
        if len(country_candidates) == 1:
            return country_candidates[0]["id"]
    return None


def qualified_competitors(event: dict[str, object]) -> tuple[dict[str, object], dict[str, object]]:
    comps = event.get("competitors")
    if not isinstance(comps, list):
        raise ValueError("competitors missing")
    home = next((c for c in comps if isinstance(c, dict) and str(c.get("qualifier", "")).lower() == "home"), None)
    away = next((c for c in comps if isinstance(c, dict) and str(c.get("qualifier", "")).lower() == "away"), None)
    if not isinstance(home, dict) or not isinstance(away, dict):
        raise ValueError("home/away missing")
    return home, away


def stats_side(summary: dict[str, object], qualifier: str, expected_id: str) -> dict[str, object] | None:
    statistics = summary.get("statistics")
    if not isinstance(statistics, dict):
        return None
    totals = statistics.get("totals")
    if not isinstance(totals, dict):
        return None
    comps = totals.get("competitors")
    if not isinstance(comps, list):
        return None
    for row in comps:
        if not isinstance(row, dict):
            continue
        if str(row.get("qualifier", "")).lower() == qualifier and str(row.get("id", "")) == expected_id:
            s = row.get("statistics")
            return s if isinstance(s, dict) else None
    return None


def make_stats(summary: dict[str, object], match_id: str, *, home_sr: str, away_sr: str, a_is_home: bool) -> MatchStats | None:
    hs = stats_side(summary, "home", home_sr)
    aws = stats_side(summary, "away", away_sr)
    if hs is None or aws is None:
        return None

    def val(row: dict[str, object], key: str) -> int | None:
        return optional_int(row.get(key))

    def service_points(row: dict[str, object]) -> int | None:
        won = val(row, "service_points_won")
        lost = val(row, "service_points_lost")
        if won is not None and lost is not None:
            return won + lost
        first_in = val(row, "first_serve_successful")
        second_attempted = val(row, "second_serve_attempted")
        if first_in is not None and second_attempted is not None:
            return first_in + second_attempted
        return None

    arow, brow = (hs, aws) if a_is_home else (aws, hs)
    return MatchStats(
        match_id=match_id,
        aces_a=val(arow, "aces"),
        aces_b=val(brow, "aces"),
        double_faults_a=val(arow, "double_faults"),
        double_faults_b=val(brow, "double_faults"),
        service_points_a=service_points(arow),
        service_points_b=service_points(brow),
        first_serves_in_a=val(arow, "first_serve_successful"),
        first_serves_in_b=val(brow, "first_serve_successful"),
        first_serve_points_won_a=val(arow, "first_serve_points_won"),
        first_serve_points_won_b=val(brow, "first_serve_points_won"),
        second_serve_points_won_a=val(arow, "second_serve_points_won"),
        second_serve_points_won_b=val(brow, "second_serve_points_won"),
        service_games_a=val(arow, "service_games_won"),
        service_games_b=val(brow, "service_games_won"),
        break_points_saved_a=val(arow, "break_points_saved"),
        break_points_saved_b=val(brow, "break_points_saved"),
        break_points_faced_a=val(arow, "break_points_faced"),
        break_points_faced_b=val(brow, "break_points_faced"),
        duration_minutes=None,
    )


def parse_prior_summary(
    summary: dict[str, object],
    *,
    season_info: dict[str, object],
    by_name,
    explicit: dict[str, str],
    source_order: int,
) -> tuple[HistoricalMatch | None, str | None, tuple[str, str] | None]:
    event = summary.get("sport_event")
    status = summary.get("sport_event_status")
    if not isinstance(event, dict) or not isinstance(status, dict):
        return None, "MALFORMED", None
    context = event.get("sport_event_context")
    if not isinstance(context, dict):
        return None, "MALFORMED_CONTEXT", None
    category = context.get("category") or {}
    competition = context.get("competition") or {}
    season = context.get("season") or {}
    if not isinstance(category, dict) or str(category.get("id")) != "sr:category:6":
        return None, "NOT_WTA", None
    if not isinstance(competition, dict) or str(competition.get("type", "")).lower() != "singles":
        return None, "NOT_SINGLES", None
    if str(status.get("status", "")).lower() not in {"ended", "closed"}:
        return None, "NOT_COMPLETED", None
    home, away = qualified_competitors(event)
    home_sr, away_sr = str(home.get("id", "")), str(away.get("id", ""))
    home_id = resolve_competitor(home, by_name, explicit)
    away_id = resolve_competitor(away, by_name, explicit)
    if not home_id or not away_id:
        return None, "UNRESOLVED_CANONICAL_ID", (home_sr, away_sr)
    if home_id == away_id:
        return None, "NONUNIQUE_CANONICAL_ID", (home_sr, away_sr)
    winner_sr = str(status.get("winner_id", ""))
    if winner_sr not in {home_sr, away_sr}:
        return None, "WINNER_ID_MISMATCH", (home_sr, away_sr)
    reason = normalize_text(str(status.get("winning_reason", "")))
    if reason in {"walkover", "retirement", "defaulted"}:
        return None, reason.upper(), (home_sr, away_sr)

    season_obj = season if isinstance(season, dict) else {}
    event_date = date.fromisoformat(str(season_obj.get("start_date")))
    if event_date >= TARGET_TOURNEY_DATE:
        return None, "AFTER_CUTOFF", (home_sr, away_sr)
    sinfo = season_info.get("season") if isinstance(season_info, dict) else None
    sinfo = sinfo if isinstance(sinfo, dict) else {}
    info = sinfo.get("info") if isinstance(sinfo.get("info"), dict) else {}
    raw_surface = str(info.get("surface", "")).strip().lower().replace("-", "_").replace(" ", "_")
    surface = SURFACE_MAP.get(raw_surface, "Unknown")
    level = LEVEL_MAP.get(str(competition.get("level", "")).lower())
    round_raw = context.get("round")
    round_name = None
    if isinstance(round_raw, dict):
        round_name = ROUND_MAP.get(str(round_raw.get("name", "")).lower())
    mode = context.get("mode")
    best_of = optional_int(mode.get("best_of")) if isinstance(mode, dict) else None

    a_id, b_id = sorted((home_id, away_id))
    a_is_home = a_id == home_id
    comp_a, comp_b = (home, away) if a_is_home else (away, home)
    a_won = (winner_sr == home_sr) if a_is_home else (winner_sr == away_sr)
    match_id = str(event.get("id", ""))
    pre = PreMatchState(
        match_id=match_id,
        tour="WTA",
        event_date=event_date,
        source_order=source_order,
        tournament_id=str(season_obj.get("id", "")),
        tournament_name=str(competition.get("name", "")),
        tournament_level=level,
        surface=surface,
        round=round_name,
        best_of=best_of,
        player_a_id=a_id,
        player_b_id=b_id,
        player_a_name=provider_full_name(str(comp_a.get("name", ""))),
        player_b_name=provider_full_name(str(comp_b.get("name", ""))),
        rank_a=None,
        rank_b=None,
        rank_points_a=None,
        rank_points_b=None,
        draw_size=optional_int(info.get("number_of_competitors")),
        seed_a=optional_int(comp_a.get("seed")),
        seed_b=optional_int(comp_b.get("seed")),
        entry_a=None,
        entry_b=None,
        hand_a=None,
        hand_b=None,
        height_cm_a=None,
        height_cm_b=None,
        age_years_a=None,
        age_years_b=None,
        ioc_a=str(comp_a.get("country_code", "")) or None,
        ioc_b=str(comp_b.get("country_code", "")) or None,
    )
    out = MatchOutcome(match_id=match_id, a_won=a_won, score=None, retirement=False, walkover=False)
    stats = make_stats(summary, match_id, home_sr=home_sr, away_sr=away_sr, a_is_home=a_is_home)
    return HistoricalMatch(pre, out, stats), None, (home_sr, away_sr)


def age_years(dob: str, when: date) -> float | None:
    if not dob or len(dob) != 8 or not dob.isdigit():
        return None
    born = date(int(dob[:4]), int(dob[4:6]), int(dob[6:8]))
    return (when - born).days / 365.25


def dataclass_payload(value: object) -> dict[str, object]:
    payload = asdict(value)
    if "event_date" in payload and isinstance(payload["event_date"], date):
        payload["event_date"] = payload["event_date"].isoformat()
    return payload


def target_state_from_provider(target_summary: dict[str, object], target_info: dict[str, object], by_id) -> PreMatchState:
    event = target_summary["sport_event"]
    context = event["sport_event_context"]
    home, away = qualified_competitors(event)
    explicit = {PARRY_SR: PARRY_CANONICAL, STEARNS_SR: STEARNS_CANONICAL}
    home_id = explicit[str(home["id"])]
    away_id = explicit[str(away["id"])]
    a_id, b_id = sorted((home_id, away_id))
    a_comp, b_comp = (home, away) if a_id == home_id else (away, home)
    a_row, b_row = by_id[a_id], by_id[b_id]
    sinfo = target_info["season"]
    info = sinfo.get("info") or {}
    round_obj = context.get("round") or {}
    mode = context.get("mode") or {}
    return PreMatchState(
        match_id=TARGET_MATCH_ID,
        tour="WTA",
        event_date=TARGET_TOURNEY_DATE,
        source_order=10**9,
        tournament_id=TARGET_SEASON_ID,
        tournament_name=str(context["competition"]["name"]),
        tournament_level="P",
        surface="Hard",
        round=ROUND_MAP.get(str(round_obj.get("name", "")).lower()),
        best_of=int(mode.get("best_of", 3)),
        player_a_id=a_id,
        player_b_id=b_id,
        player_a_name=provider_full_name(str(a_comp["name"])),
        player_b_name=provider_full_name(str(b_comp["name"])),
        rank_a=None,
        rank_b=None,
        rank_points_a=None,
        rank_points_b=None,
        draw_size=optional_int(info.get("number_of_competitors")),
        seed_a=optional_int(a_comp.get("seed")),
        seed_b=optional_int(b_comp.get("seed")),
        entry_a=None,
        entry_b=None,
        hand_a=a_row["hand"] or None,
        hand_b=b_row["hand"] or None,
        height_cm_a=optional_int(a_row["height"]),
        height_cm_b=optional_int(b_row["height"]),
        age_years_a=age_years(a_row["dob"], TARGET_TOURNEY_DATE),
        age_years_b=age_years(b_row["dob"], TARGET_TOURNEY_DATE),
        ioc_a=a_row["country"] or None,
        ioc_b=b_row["country"] or None,
    )


def recent_player_rows(history: list[HistoricalMatch], player_id: str, limit: int = 10) -> list[dict[str, object]]:
    rows = []
    for match in history:
        s = match.pre_match
        if player_id not in {s.player_a_id, s.player_b_id}:
            continue
        is_a = player_id == s.player_a_id
        won = match.outcome.a_won if is_a else not match.outcome.a_won
        opponent = s.player_b_name if is_a else s.player_a_name
        rows.append({
            "event_date": s.event_date.isoformat(),
            "tournament": s.tournament_name,
            "surface": s.surface,
            "round": s.round,
            "opponent": opponent,
            "won": won,
            "stats_available": match.stats is not None,
        })
    rows.sort(key=lambda r: (r["event_date"], r["tournament"]), reverse=True)
    return rows[:limit]


def main() -> None:
    root = Path("prediction-work")
    root.mkdir(exist_ok=True)
    base_dir = Path("data/wta-live-base")
    history = load_canonical_parquet(
        pre_match_path=base_dir / "wta_pre_match.parquet",
        outcome_path=base_dir / "wta_outcomes.parquet",
        stats_path=base_dir / "wta_stats.parquet",
    )
    base_history = [m for m in history if not m.outcome.walkover and not m.outcome.retirement]

    by_name, by_id = player_index(Path("data/wta_players.csv"))
    explicit = {PARRY_SR: PARRY_CANONICAL, STEARNS_SR: STEARNS_CANONICAL}

    competitions = http_json("competitions.json")
    seasons = http_json("seasons.json")
    wta_comps = {}
    for comp in competitions.get("competitions", []):
        if not isinstance(comp, dict):
            continue
        category = comp.get("category") or {}
        if not isinstance(category, dict) or category.get("id") != "sr:category:6":
            continue
        if str(comp.get("type", "")).lower() != "singles":
            continue
        level = str(comp.get("level", "")).lower()
        if level in ALLOWED_LEVELS:
            wta_comps[str(comp["id"])] = comp

    selected = []
    for season in seasons.get("seasons", []):
        if not isinstance(season, dict) or season.get("disabled") is True:
            continue
        cid = str(season.get("competition_id", ""))
        if cid not in wta_comps:
            continue
        try:
            start = date.fromisoformat(str(season.get("start_date", "")))
        except ValueError:
            continue
        if date(2026, 1, 1) <= start < TARGET_TOURNEY_DATE:
            selected.append((start, str(season["id"]), cid))
    selected.sort()

    raw_source = {"seasons": [], "summaries": []}
    extension: list[HistoricalMatch] = []
    exclusion_counts = Counter()
    unresolved_events = []
    sr_to_canonical: dict[str, str] = dict(explicit)
    target_player_seen = Counter()
    target_player_accepted = Counter()
    source_order = 0

    for start, season_id, cid in selected:
        info = http_json(f"seasons/{season_id}/info.json")
        offset = 0
        while True:
            page = http_json(f"seasons/{season_id}/summaries.json?start={offset}&limit=200")
            rows = page.get("summaries")
            if not isinstance(rows, list):
                raise RuntimeError("season summaries missing array")
            raw_source["summaries"].append({"season_id": season_id, "start": offset, "payload": page})
            for summary in rows:
                if not isinstance(summary, dict):
                    continue
                event = summary.get("sport_event")
                if isinstance(event, dict):
                    try:
                        home, away = qualified_competitors(event)
                        for comp in (home, away):
                            sr = str(comp.get("id", ""))
                            mapped = resolve_competitor(comp, by_name, explicit)
                            if mapped:
                                prior = sr_to_canonical.get(sr)
                                if prior is not None and prior != mapped:
                                    raise RuntimeError(f"conflicting crosswalk for {sr}")
                                sr_to_canonical[sr] = mapped
                            if sr in {PARRY_SR, STEARNS_SR}:
                                target_player_seen[sr] += 1
                    except ValueError:
                        pass
                match, reason, pair = parse_prior_summary(
                    summary,
                    season_info=info,
                    by_name=by_name,
                    explicit=explicit,
                    source_order=source_order,
                )
                source_order += 1
                if match is None:
                    exclusion_counts[reason or "UNKNOWN"] += 1
                    if reason == "UNRESOLVED_CANONICAL_ID":
                        unresolved_events.append(str((summary.get("sport_event") or {}).get("id", "UNKNOWN")))
                    continue
                extension.append(match)
                if pair:
                    for sr in pair:
                        if sr in {PARRY_SR, STEARNS_SR}:
                            target_player_accepted[sr] += 1
            if len(rows) < 200:
                break
            offset += 200
            if offset > 2000:
                raise RuntimeError("unexpected WTA season pagination depth")
        raw_source["seasons"].append({"season_id": season_id, "competition_id": cid, "start_date": start.isoformat(), "info": info})

    if not extension:
        raise RuntimeError("no authenticated 2026 WTA extension matches")
    if max(m.pre_match.event_date for m in extension) >= TARGET_TOURNEY_DATE:
        raise RuntimeError("live extension leaks target tournament date or later")
    if target_player_seen[PARRY_SR] != target_player_accepted[PARRY_SR]:
        raise RuntimeError(f"Parry provider history mapping incomplete: {target_player_accepted[PARRY_SR]}/{target_player_seen[PARRY_SR]}")
    if target_player_seen[STEARNS_SR] != target_player_accepted[STEARNS_SR]:
        raise RuntimeError(f"Stearns provider history mapping incomplete: {target_player_accepted[STEARNS_SR]}/{target_player_seen[STEARNS_SR]}")

    current_target_summary = http_json(f"sport_events/{TARGET_EVENT_ID}/summary.json")
    current_target_info = http_json(f"seasons/{TARGET_SEASON_ID}/info.json")
    status = current_target_summary.get("sport_event_status") or {}
    if not isinstance(status, dict) or str(status.get("status", "")).lower() not in {"not_started", "scheduled"}:
        raise RuntimeError(f"target is no longer pre-match: {status}")
    target_event = current_target_summary.get("sport_event")
    if not isinstance(target_event, dict):
        raise RuntimeError("target sport_event missing")
    if str(target_event.get("start_time", "")) != SCHEDULED_START:
        raise RuntimeError("target scheduled start changed")

    target_state = target_state_from_provider(current_target_summary, current_target_info, by_id)
    target_sentinel = HistoricalMatch(
        target_state,
        MatchOutcome(TARGET_MATCH_ID, False, None, False, False),
        None,
    )
    combined = base_history + extension + [target_sentinel]
    foundational = next(s for s in walk_forward_foundational_features(combined, exclude_retirements=False) if s.match_id == TARGET_MATCH_ID)
    serve_return = next(s for s in walk_forward_serve_return(combined, exclude_retirements=False) if s.match_id == TARGET_MATCH_ID)

    provider_store = ProviderBatchStore(Path("trusted-provider-artifact/trusted-provider-capture/provider-batch-store"))
    identity = build_identity_binding(
        batch_store=provider_store,
        batch_record_sha256=PROVIDER_BATCH_SHA,
        provider_anchor_comment_id=PROVIDER_ANCHOR_COMMENT_ID,
        match_id=TARGET_MATCH_ID,
        player_a_canonical_id=PARRY_CANONICAL,
        player_b_canonical_id=STEARNS_CANONICAL,
        sportradar_event_id=TARGET_EVENT_ID,
        player_a_sportradar_id=PARRY_SR,
        player_b_sportradar_id=STEARNS_SR,
    )
    identity_path = root / "sportradar-identity-binding.json"
    identity_path.write_text(pretty(identity_as_dict(identity)), encoding="utf-8")

    state_manifest = {
        "schema_version": "wta-live-state-001",
        "cutoff_tournament_date_exclusive": TARGET_TOURNEY_DATE.isoformat(),
        "base_years": [2000, 2025],
        "base_match_count": len(base_history),
        "authenticated_2026_match_count": len(extension),
        "authenticated_prior_season_count": len(selected),
        "authenticated_state_max_tournament_date": max(m.pre_match.event_date for m in extension).isoformat(),
        "crosswalk_size": len(sr_to_canonical),
        "unresolved_event_count": len(unresolved_events),
        "exclusion_counts": dict(sorted(exclusion_counts.items())),
        "target_player_provider_matches_seen": dict(target_player_seen),
        "target_player_provider_matches_accepted": dict(target_player_accepted),
        "raw_source_sha256": sha_bytes(canonical_json(raw_source)),
        "target_state": dataclass_payload(target_state),
    }
    state_path = root / "wta-live-state-manifest.json"
    state_path.write_text(pretty(state_manifest), encoding="utf-8")

    target_source = {
        "schema_version": "wta-live-target-source-001",
        "target_summary": current_target_summary,
        "target_season_info": current_target_info,
        "provider_batch_record_sha256": PROVIDER_BATCH_SHA,
        "provider_anchor_comment_id": PROVIDER_ANCHOR_COMMENT_ID,
    }
    target_source_path = root / "target-provider-source.json"
    target_source_path.write_text(pretty(target_source), encoding="utf-8")

    base_manifest_path = base_dir / "wta_manifest.json"
    source_paths = [base_manifest_path, state_path, target_source_path, identity_path]
    source_hashes = [sha_file(path) for path in source_paths]
    if len(set(source_hashes)) != len(source_hashes):
        raise RuntimeError("duplicate source evidence hashes")

    created_at = datetime.now(UTC)
    scheduled = datetime.fromisoformat(SCHEDULED_START)
    if created_at >= scheduled:
        raise RuntimeError("prediction creation is not pre-start")
    prediction_id = f"FULL-STACK-FORWARD-001-{TARGET_EVENT_ID.replace(':', '-')}-{created_at.strftime('%Y%m%dT%H%M%SZ')}"
    matchup_payload = {
        "prediction_id": prediction_id,
        "match_id": TARGET_MATCH_ID,
        "tour": "WTA",
        "player_a_id": PARRY_CANONICAL,
        "player_b_id": STEARNS_CANONICAL,
        "created_at": created_at.isoformat(),
        "prediction_cutoff_at": created_at.isoformat(),
        "foundational": dataclass_payload(foundational),
        "source_manifest_hashes": source_hashes,
        "best_of": 3,
        "profile_pair": None,
        "serve_return": dataclass_payload(serve_return),
    }
    input_path = root / "matchup-input.json"
    input_path.write_text(pretty(matchup_payload), encoding="utf-8")

    schedule_evidence = {
        "schema_version": "wta-live-schedule-evidence-001",
        "match_id": TARGET_MATCH_ID,
        "sportradar_event_id": TARGET_EVENT_ID,
        "scheduled_start": SCHEDULED_START,
        "source_generated_at": current_target_summary.get("generated_at"),
        "start_time_confirmed": bool(target_event.get("start_time_confirmed")),
        "status": status.get("status"),
    }
    schedule_path = root / "schedule-evidence.json"
    schedule_path.write_text(pretty(schedule_evidence), encoding="utf-8")

    bundle_path = Path("artifacts/tge_independent_v1_production/tge_independent_v1_production.json")
    calculator = load_validated_matchup_calculator(bundle_path)
    matchup = load_matchup_input(input_path)
    calculation = calculator.calculate(matchup)
    calculation_path = root / "calculation.json"
    calculation_path.write_text(pretty(calculation.to_dict()), encoding="utf-8")

    pilot_store = ProspectivePilotStore(root / "prospective-pilot-store")
    prediction_record = commit_prediction(
        store=pilot_store,
        bundle_path=bundle_path,
        input_path=input_path,
        scheduled_start=SCHEDULED_START,
        source_evidence_paths=source_paths,
        schedule_evidence_path=schedule_path,
    )
    pilot_report = pilot_store.verify()
    if prediction_record["record_sha256"] != pilot_report["chain_head_sha256"]:
        raise RuntimeError("prediction is not immediate pilot chain head")

    parry_recent = recent_player_rows(extension, PARRY_CANONICAL)
    stearns_recent = recent_player_rows(extension, STEARNS_CANONICAL)
    dossier = {
        "schema_version": "wta-live-prediction-dossier-001",
        "target": {
            "event_id": TARGET_EVENT_ID,
            "scheduled_start": SCHEDULED_START,
            "tournament": target_state.tournament_name,
            "surface": target_state.surface,
            "round": target_state.round,
            "best_of": target_state.best_of,
            "player_a": {"id": PARRY_CANONICAL, "name": target_state.player_a_name, "seed": target_state.seed_a},
            "player_b": {"id": STEARNS_CANONICAL, "name": target_state.player_b_name, "seed": target_state.seed_b},
        },
        "calculation": calculation.to_dict(),
        "foundational": dataclass_payload(foundational),
        "serve_return": dataclass_payload(serve_return),
        "state_audit": state_manifest,
        "identity_binding_sha256": sha_file(identity_path),
        "prediction_record": prediction_record,
        "pilot_report": pilot_report,
        "recent_2026_main_tour": {
            "parry": parry_recent,
            "stearns": stearns_recent,
        },
    }
    dossier_path = root / "prediction-dossier.json"
    dossier_path.write_text(pretty(dossier), encoding="utf-8")
    print(pretty({
        "prediction_id": prediction_id,
        "prediction_record_sha256": prediction_record["record_sha256"],
        "chain_head_sha256": pilot_report["chain_head_sha256"],
        "p_player_a": calculation.prediction.p_player_a,
        "p_player_b": calculation.prediction.p_player_b,
        "fair_decimal_odds": asdict(calculation.fair_decimal_odds),
        "assessment_status": calculation.assessment_status,
        "authenticated_2026_match_count": len(extension),
        "crosswalk_size": len(sr_to_canonical),
        "unresolved_event_count": len(unresolved_events),
        "target_player_seen": dict(target_player_seen),
        "target_player_accepted": dict(target_player_accepted),
    }))


if __name__ == "__main__":
    main()
