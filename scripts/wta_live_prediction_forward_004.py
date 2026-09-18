from __future__ import annotations

import copy
import hashlib
import json
import types
from datetime import UTC, datetime, timedelta
from pathlib import Path

from tennis_genome.data.canonical import PreMatchState
from tennis_genome.prospective.match_lifecycle import MatchLifecycleLedger

FORWARD_PROTOCOL = "FULL-STACK-FORWARD-004"
MIN_CAPTURE_LEAD = timedelta(minutes=90)


class _CachedHttpJson:
    """Memoize authenticated provider JSON so each unique endpoint is fetched once."""

    def __init__(self, provider_get):
        self._provider_get = provider_get
        self._cache: dict[str, dict[str, object]] = {}
        self.provider_request_count = 0

    @property
    def cached_path_count(self) -> int:
        return len(self._cache)

    @property
    def cached_paths(self) -> tuple[str, ...]:
        return tuple(sorted(self._cache))

    def __call__(self, path: str) -> dict[str, object]:
        if path not in self._cache:
            value = self._provider_get(path)
            if not isinstance(value, dict):
                raise RuntimeError("cached Sportradar provider response must be an object")
            self._cache[path] = copy.deepcopy(value)
            self.provider_request_count += 1
        return copy.deepcopy(self._cache[path])


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_event_stem(event_id: str) -> str:
    stem = event_id.replace(":", "-").replace("/", "-")
    if not stem or stem in {".", ".."}:
        raise ValueError("provider event ID cannot form an artifact path")
    return stem


def _configure_target(
    h,
    *,
    resolved: dict[str, str],
    provider_batch_record_sha256: str,
    provider_anchor_comment_id: int,
) -> None:
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
    h.PROVIDER_BATCH_SHA = provider_batch_record_sha256
    h.PROVIDER_ANCHOR_COMMENT_ID = provider_anchor_comment_id


def _assert_target_prestart(
    target_summary: dict[str, object],
    *,
    scheduled_start: str,
    now: datetime,
) -> None:
    status = target_summary.get("sport_event_status")
    if not isinstance(status, dict) or str(status.get("status", "")).lower() not in {
        "not_started",
        "scheduled",
    }:
        raise RuntimeError("selected Forward-004 target ceased to be pre-match")
    scheduled = datetime.fromisoformat(scheduled_start)
    if scheduled.tzinfo is None or scheduled.utcoffset() is None:
        raise RuntimeError("selected Forward-004 scheduled start must be timezone-aware")
    if now >= scheduled:
        raise RuntimeError("selected Forward-004 target is no longer pre-start")


def run_forward_004_slate(
    *,
    module,
    slate: tuple[tuple[dict[str, object], dict[str, str]], ...],
    provider_batch_record_sha256: str,
    provider_anchor_comment_id: int,
    output_root: Path,
    now: datetime | None = None,
) -> dict[str, object]:
    """Run the unchanged live predictor for every eligible target with one provider cache."""

    if not slate:
        raise ValueError("Forward-004 slate cannot be empty")
    if len(provider_batch_record_sha256) != 64:
        raise ValueError("provider batch record SHA-256 is invalid")
    current_time = now or datetime.now(UTC)
    if current_time.tzinfo is None or current_time.utcoffset() is None:
        raise ValueError("slate execution clock must be timezone-aware")

    output_root.mkdir(parents=True, exist_ok=False)
    h = module.h
    original_http_json = h.http_json
    original_target_state_from_provider = getattr(h, "target_state_from_provider", None)
    provider_cache = _CachedHttpJson(original_http_json)
    trusted_summaries = {
        resolution["event_id"]: summary for summary, resolution in slate
    }
    if len(trusted_summaries) != len(slate):
        raise RuntimeError("Forward-004 slate contains duplicate event identities")

    def slate_http_json(path: str) -> dict[str, object]:
        prefix = "sport_events/"
        suffix = "/summary.json"
        if path.startswith(prefix) and path.endswith(suffix):
            event_id = path[len(prefix) : -len(suffix)]
            trusted = trusted_summaries.get(event_id)
            if trusted is not None:
                return copy.deepcopy(trusted)
        return provider_cache(path)

    h.http_json = slate_http_json
    h.target_state_from_provider = (
        lambda summary, info, by_id: _generic_target_state(h, summary, info, by_id)
    )
    lifecycle = MatchLifecycleLedger(output_root / "match-lifecycle-ledger")
    results: list[dict[str, object]] = []

    try:
        for index, (target_summary, raw_resolution) in enumerate(slate, start=1):
            resolved = dict(raw_resolution)
            resolved["provider_batch_record_sha256"] = provider_batch_record_sha256
            resolved["provider_anchor_comment_id"] = str(provider_anchor_comment_id)
            event_id = resolved["event_id"]
            lifecycle_id = f"{FORWARD_PROTOCOL}-{event_id}"
            match_root = output_root / "matches" / _safe_event_stem(event_id)
            match_root.mkdir(parents=True, exist_ok=False)
            target_path = match_root / "forward-004-target-resolution.json"
            target_path.write_text(
                json.dumps(resolved, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

            lifecycle.discover(
                lifecycle_id=lifecycle_id,
                match_id=event_id,
                provider_event_id=event_id,
                evidence_sha256=(provider_batch_record_sha256,),
                details={
                    "slate_index": index,
                    "scheduled_start": resolved["scheduled_start"],
                },
            )
            lifecycle.advance(
                lifecycle_id=lifecycle_id,
                state="SNAPSHOT_CAPTURED",
                evidence_sha256=(_sha256_file(target_path),),
                details={"target_resolution_path": str(target_path.relative_to(output_root))},
            )

            _assert_target_prestart(
                target_summary,
                scheduled_start=resolved["scheduled_start"],
                now=current_time,
            )
            _configure_target(
                h,
                resolved=resolved,
                provider_batch_record_sha256=provider_batch_record_sha256,
                provider_anchor_comment_id=provider_anchor_comment_id,
            )
            prediction_root = match_root / "prediction-work"
            prediction_summary = module.run_prediction(root=prediction_root)
            prediction_sha = str(prediction_summary["prediction_record_sha256"])
            lifecycle.advance(
                lifecycle_id=lifecycle_id,
                state="CHAMPION_PREDICTED",
                evidence_sha256=(prediction_sha, _sha256_file(prediction_root / "matchup-input.json")),
                details={
                    "prediction_root": str(prediction_root.relative_to(output_root)),
                    "prediction_id": str(prediction_summary["prediction_id"]),
                },
            )
            results.append(
                {
                    "slate_index": index,
                    "event_id": event_id,
                    "scheduled_start": resolved["scheduled_start"],
                    "target_resolution_path": str(target_path.relative_to(output_root)),
                    "prediction_root": str(prediction_root.relative_to(output_root)),
                    "prediction_record_sha256": prediction_sha,
                    "chain_head_sha256": str(prediction_summary["chain_head_sha256"]),
                    "p_player_a": prediction_summary["p_player_a"],
                    "p_player_b": prediction_summary["p_player_b"],
                }
            )
    finally:
        h.http_json = original_http_json
        if original_target_state_from_provider is not None:
            h.target_state_from_provider = original_target_state_from_provider

    lifecycle_audit = lifecycle.verify()
    manifest = {
        "schema_version": "wta-forward-004-slate-execution-v1",
        "forward_protocol": FORWARD_PROTOCOL,
        "target_count": len(results),
        "provider_batch_record_sha256": provider_batch_record_sha256,
        "provider_anchor_comment_id": provider_anchor_comment_id,
        "provider_unique_request_count": provider_cache.provider_request_count,
        "provider_cached_path_count": provider_cache.cached_path_count,
        "provider_cached_paths": list(provider_cache.cached_paths),
        "lifecycle_chain_head_sha256": lifecycle_audit.chain_head_sha256,
        "lifecycle_event_count": lifecycle_audit.event_count,
        "lifecycle_count": lifecycle_audit.lifecycle_count,
        "results": results,
    }
    (output_root / "slate-execution-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


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


def _target_resolution(
    *,
    summary: dict[str, object],
    scheduled: datetime,
    event_id: str,
    player_a_id: str,
    player_a_sr: str,
    player_b_id: str,
    player_b_sr: str,
    capture_observed_at: datetime,
    selection_rule: str,
) -> dict[str, str]:
    event = summary["sport_event"]
    if not isinstance(event, dict):
        raise RuntimeError("eligible target sport_event is malformed")
    context = event["sport_event_context"]
    if not isinstance(context, dict):
        raise RuntimeError("eligible target context is malformed")
    season = context["season"]
    competition = context["competition"]
    if not isinstance(season, dict) or not isinstance(competition, dict):
        raise RuntimeError("eligible target season/competition is malformed")
    return {
        "schema_version": "wta-forward-004-target-resolution-v1",
        "forward_protocol": FORWARD_PROTOCOL,
        "selection_rule": selection_rule,
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


def select_forward_004_targets(
    h,
    *,
    summaries: list[dict[str, object]],
    by_name,
    capture_observed_at: datetime,
) -> tuple[tuple[dict[str, object], dict[str, str]], ...]:
    """Return the complete deterministic eligible WTA slate from one trusted capture."""

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

    candidates.sort(key=lambda item: (item[0], item[1]))
    event_ids = [item[1] for item in candidates]
    if len(event_ids) != len(set(event_ids)):
        raise RuntimeError("trusted capture produced duplicate eligible WTA event IDs")

    selection_rule = (
        "all_confirmed_resolvable_wta_main_tour_singles_sorted_by_start_then_event_id"
    )
    return tuple(
        (
            summary,
            _target_resolution(
                summary=summary,
                scheduled=scheduled,
                event_id=event_id,
                player_a_id=player_a_id,
                player_a_sr=player_a_sr,
                player_b_id=player_b_id,
                player_b_sr=player_b_sr,
                capture_observed_at=capture_observed_at,
                selection_rule=selection_rule,
            ),
        )
        for (
            scheduled,
            event_id,
            summary,
            player_a_id,
            player_a_sr,
            player_b_id,
            player_b_sr,
        ) in candidates
    )


def select_forward_004_target(
    h,
    *,
    summaries: list[dict[str, object]],
    by_name,
    capture_observed_at: datetime,
) -> tuple[dict[str, object], dict[str, str]]:
    """Compatibility selector retaining the original earliest-target Forward-004 rule."""

    selected = select_forward_004_targets(
        h,
        summaries=summaries,
        by_name=by_name,
        capture_observed_at=capture_observed_at,
    )[0]
    summary, resolution = selected
    resolution = dict(resolution)
    resolution["selection_rule"] = "earliest_confirmed_resolvable_wta_main_tour_singles"
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
    slate = select_forward_004_targets(
        h,
        summaries=summaries,
        by_name=by_name,
        capture_observed_at=observed_at,
    )
    target_summary, resolved = slate[0]
    resolved = dict(resolved)
    resolved["selection_rule"] = "earliest_confirmed_resolvable_wta_main_tour_singles"

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
    provider_batch_record_sha256 = str(receipt["batch_record_sha256"])
    provider_anchor_comment_id = str(anchor_comment_id)
    resolved["provider_batch_record_sha256"] = provider_batch_record_sha256
    resolved["provider_anchor_comment_id"] = provider_anchor_comment_id

    slate_targets: list[dict[str, str]] = []
    for _, item in slate:
        target = dict(item)
        target["provider_batch_record_sha256"] = provider_batch_record_sha256
        target["provider_anchor_comment_id"] = provider_anchor_comment_id
        slate_targets.append(target)
    slate_manifest = {
        "schema_version": "wta-forward-004-slate-resolution-v1",
        "forward_protocol": FORWARD_PROTOCOL,
        "selection_rule": (
            "all_confirmed_resolvable_wta_main_tour_singles_sorted_by_start_then_event_id"
        ),
        "minimum_capture_lead_minutes": int(
            MIN_CAPTURE_LEAD.total_seconds() // 60
        ),
        "capture_observed_at": observed_at.isoformat(),
        "eligible_target_count": len(slate_targets),
        "provider_batch_record_sha256": provider_batch_record_sha256,
        "provider_anchor_comment_id": anchor_comment_id,
        "targets": slate_targets,
    }
    Path("forward-004-slate-resolution.json").write_text(
        json.dumps(slate_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

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
