from __future__ import annotations

import importlib.util
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path

from tennis_genome.calculator.contract import load_validated_matchup_calculator
from tennis_genome.calculator.io import load_matchup_input
from tennis_genome.data.canonical import HistoricalMatch, MatchOutcome
from tennis_genome.data.parquet import load_canonical_parquet
from tennis_genome.features.foundational import walk_forward_foundational_features
from tennis_genome.prospective.pilot import ProspectivePilotStore, commit_prediction
from tennis_genome.prospective.provider_batch import ProviderBatchStore
from tennis_genome.prospective.settlement_identity import build_identity_binding, identity_as_dict
from tennis_genome.ratings.serve_return import walk_forward_serve_return

_HELPER_PATH = Path(__file__).with_name("wta_live_prediction_001.py")
_spec = importlib.util.spec_from_file_location("wta_live_prediction_001_helpers", _HELPER_PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError("unable to load WTA prediction helpers")
h = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(h)

LEGITIMATE_TARGET_EXCLUSIONS = {
    "NOT_COMPLETED",
    "RETIREMENT",
    "WALKOVER",
    "DEFAULTED",
    "AFTER_CUTOFF",
}


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

    by_name, by_id = h.player_index(Path("data/wta_players.csv"))
    explicit = {h.PARRY_SR: h.PARRY_CANONICAL, h.STEARNS_SR: h.STEARNS_CANONICAL}

    competitions = h.http_json("competitions.json")
    seasons = h.http_json("seasons.json")
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
        if level in h.ALLOWED_LEVELS:
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
        if date(2026, 1, 1) <= start < h.TARGET_TOURNEY_DATE:
            selected.append((start, str(season["id"]), cid))
    selected.sort()

    raw_source = {"seasons": [], "summaries": []}
    extension: list[HistoricalMatch] = []
    exclusion_counts = Counter()
    unresolved_events: list[str] = []
    sr_to_canonical: dict[str, str] = dict(explicit)
    target_player_seen = Counter()
    target_player_accepted = Counter()
    target_player_exclusions: defaultdict[str, Counter] = defaultdict(Counter)
    source_order = 0

    for start, season_id, cid in selected:
        info = h.http_json(f"seasons/{season_id}/info.json")
        offset = 0
        while True:
            page = h.http_json(f"seasons/{season_id}/summaries.json?start={offset}&limit=200")
            rows = page.get("summaries")
            if not isinstance(rows, list):
                raise RuntimeError("season summaries missing array")
            raw_source["summaries"].append({"season_id": season_id, "start": offset, "payload": page})
            for summary in rows:
                if not isinstance(summary, dict):
                    continue
                involved_targets: set[str] = set()
                event = summary.get("sport_event")
                if isinstance(event, dict):
                    try:
                        home, away = h.qualified_competitors(event)
                        for comp in (home, away):
                            sr = str(comp.get("id", ""))
                            mapped = h.resolve_competitor(comp, by_name, explicit)
                            if mapped:
                                prior = sr_to_canonical.get(sr)
                                if prior is not None and prior != mapped:
                                    raise RuntimeError(f"conflicting crosswalk for {sr}")
                                sr_to_canonical[sr] = mapped
                            if sr in {h.PARRY_SR, h.STEARNS_SR}:
                                involved_targets.add(sr)
                                target_player_seen[sr] += 1
                    except ValueError:
                        pass
                match, reason, pair = h.parse_prior_summary(
                    summary,
                    season_info=info,
                    by_name=by_name,
                    explicit=explicit,
                    source_order=source_order,
                )
                source_order += 1
                if match is None:
                    reason = reason or "UNKNOWN"
                    exclusion_counts[reason] += 1
                    for sr in involved_targets:
                        target_player_exclusions[sr][reason] += 1
                    if reason == "UNRESOLVED_CANONICAL_ID":
                        unresolved_events.append(str((summary.get("sport_event") or {}).get("id", "UNKNOWN")))
                    continue
                extension.append(match)
                if pair:
                    for sr in pair:
                        if sr in {h.PARRY_SR, h.STEARNS_SR}:
                            target_player_accepted[sr] += 1
            if len(rows) < 200:
                break
            offset += 200
            if offset > 2000:
                raise RuntimeError("unexpected WTA season pagination depth")
        raw_source["seasons"].append({"season_id": season_id, "competition_id": cid, "start_date": start.isoformat(), "info": info})

    if not extension:
        raise RuntimeError("no authenticated 2026 WTA extension matches")
    if max(m.pre_match.event_date for m in extension) >= h.TARGET_TOURNEY_DATE:
        raise RuntimeError("live extension leaks target tournament date or later")

    for sr_id, label in ((h.PARRY_SR, "Parry"), (h.STEARNS_SR, "Stearns")):
        exclusions = target_player_exclusions[sr_id]
        disallowed = {reason: count for reason, count in exclusions.items() if reason not in LEGITIMATE_TARGET_EXCLUSIONS}
        if disallowed:
            raise RuntimeError(f"{label} has non-legitimate provider-history exclusions: {disallowed}")
        accounted = target_player_accepted[sr_id] + sum(exclusions.values())
        if accounted != target_player_seen[sr_id]:
            raise RuntimeError(f"{label} provider-history accounting mismatch: accepted={target_player_accepted[sr_id]} exclusions={dict(exclusions)} seen={target_player_seen[sr_id]}")

    current_target_summary = h.http_json(f"sport_events/{h.TARGET_EVENT_ID}/summary.json")
    current_target_info = h.http_json(f"seasons/{h.TARGET_SEASON_ID}/info.json")
    status = current_target_summary.get("sport_event_status") or {}
    if not isinstance(status, dict) or str(status.get("status", "")).lower() not in {"not_started", "scheduled"}:
        raise RuntimeError(f"target is no longer pre-match: {status}")
    target_event = current_target_summary.get("sport_event")
    if not isinstance(target_event, dict):
        raise RuntimeError("target sport_event missing")
    if str(target_event.get("start_time", "")) != h.SCHEDULED_START:
        raise RuntimeError("target scheduled start changed")

    target_state = h.target_state_from_provider(current_target_summary, current_target_info, by_id)
    target_sentinel = HistoricalMatch(
        target_state,
        MatchOutcome(h.TARGET_MATCH_ID, False, None, False, False),
        None,
    )
    combined = base_history + extension + [target_sentinel]
    foundational = next(s for s in walk_forward_foundational_features(combined, exclude_retirements=False) if s.match_id == h.TARGET_MATCH_ID)
    serve_return = next(s for s in walk_forward_serve_return(combined, exclude_retirements=False) if s.match_id == h.TARGET_MATCH_ID)

    provider_store = ProviderBatchStore(Path("trusted-provider-artifact/trusted-provider-capture/provider-batch-store"))
    identity = build_identity_binding(
        batch_store=provider_store,
        batch_record_sha256=h.PROVIDER_BATCH_SHA,
        provider_anchor_comment_id=h.PROVIDER_ANCHOR_COMMENT_ID,
        match_id=h.TARGET_MATCH_ID,
        player_a_canonical_id=h.PARRY_CANONICAL,
        player_b_canonical_id=h.STEARNS_CANONICAL,
        sportradar_event_id=h.TARGET_EVENT_ID,
        player_a_sportradar_id=h.PARRY_SR,
        player_b_sportradar_id=h.STEARNS_SR,
    )
    identity_path = root / "sportradar-identity-binding.json"
    identity_path.write_text(h.pretty(identity_as_dict(identity)), encoding="utf-8")

    state_manifest = {
        "schema_version": "wta-live-state-002",
        "cutoff_tournament_date_exclusive": h.TARGET_TOURNEY_DATE.isoformat(),
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
        "target_player_exclusions": {sr: dict(counts) for sr, counts in target_player_exclusions.items()},
        "raw_source_sha256": h.sha_bytes(h.canonical_json(raw_source)),
        "target_state": h.dataclass_payload(target_state),
    }
    state_path = root / "wta-live-state-manifest.json"
    state_path.write_text(h.pretty(state_manifest), encoding="utf-8")

    target_source = {
        "schema_version": "wta-live-target-source-001",
        "target_summary": current_target_summary,
        "target_season_info": current_target_info,
        "provider_batch_record_sha256": h.PROVIDER_BATCH_SHA,
        "provider_anchor_comment_id": h.PROVIDER_ANCHOR_COMMENT_ID,
    }
    target_source_path = root / "target-provider-source.json"
    target_source_path.write_text(h.pretty(target_source), encoding="utf-8")

    base_manifest_path = base_dir / "wta_manifest.json"
    source_paths = [base_manifest_path, state_path, target_source_path, identity_path]
    source_hashes = [h.sha_file(path) for path in source_paths]
    if len(set(source_hashes)) != len(source_hashes):
        raise RuntimeError("duplicate source evidence hashes")

    created_at = datetime.now(UTC)
    scheduled = datetime.fromisoformat(h.SCHEDULED_START)
    if created_at >= scheduled:
        raise RuntimeError("prediction creation is not pre-start")
    prediction_id = f"FULL-STACK-FORWARD-001-{h.TARGET_EVENT_ID.replace(':', '-')}-{created_at.strftime('%Y%m%dT%H%M%SZ')}"
    matchup_payload = {
        "prediction_id": prediction_id,
        "match_id": h.TARGET_MATCH_ID,
        "tour": "WTA",
        "player_a_id": h.PARRY_CANONICAL,
        "player_b_id": h.STEARNS_CANONICAL,
        "created_at": created_at.isoformat(),
        "prediction_cutoff_at": created_at.isoformat(),
        "foundational": h.dataclass_payload(foundational),
        "source_manifest_hashes": source_hashes,
        "best_of": 3,
        "profile_pair": None,
        "serve_return": h.dataclass_payload(serve_return),
    }
    input_path = root / "matchup-input.json"
    input_path.write_text(h.pretty(matchup_payload), encoding="utf-8")

    schedule_evidence = {
        "schema_version": "wta-live-schedule-evidence-001",
        "match_id": h.TARGET_MATCH_ID,
        "sportradar_event_id": h.TARGET_EVENT_ID,
        "scheduled_start": h.SCHEDULED_START,
        "source_generated_at": current_target_summary.get("generated_at"),
        "start_time_confirmed": bool(target_event.get("start_time_confirmed")),
        "status": status.get("status"),
    }
    schedule_path = root / "schedule-evidence.json"
    schedule_path.write_text(h.pretty(schedule_evidence), encoding="utf-8")

    bundle_path = Path("artifacts/tge_independent_v1_production/tge_independent_v1_production.json")
    calculator = load_validated_matchup_calculator(bundle_path)
    matchup = load_matchup_input(input_path)
    calculation = calculator.calculate(matchup)
    (root / "calculation.json").write_text(h.pretty(calculation.to_dict()), encoding="utf-8")

    pilot_store = ProspectivePilotStore(root / "prospective-pilot-store")
    prediction_record = commit_prediction(
        store=pilot_store,
        bundle_path=bundle_path,
        input_path=input_path,
        scheduled_start=h.SCHEDULED_START,
        source_evidence_paths=source_paths,
        schedule_evidence_path=schedule_path,
    )
    pilot_report = pilot_store.verify()
    if prediction_record["record_sha256"] != pilot_report["chain_head_sha256"]:
        raise RuntimeError("prediction is not immediate pilot chain head")

    dossier = {
        "schema_version": "wta-live-prediction-dossier-002",
        "target": {
            "event_id": h.TARGET_EVENT_ID,
            "scheduled_start": h.SCHEDULED_START,
            "tournament": target_state.tournament_name,
            "surface": target_state.surface,
            "round": target_state.round,
            "best_of": target_state.best_of,
            "player_a": {"id": h.PARRY_CANONICAL, "name": target_state.player_a_name, "seed": target_state.seed_a},
            "player_b": {"id": h.STEARNS_CANONICAL, "name": target_state.player_b_name, "seed": target_state.seed_b},
        },
        "calculation": calculation.to_dict(),
        "foundational": h.dataclass_payload(foundational),
        "serve_return": h.dataclass_payload(serve_return),
        "state_audit": state_manifest,
        "identity_binding_sha256": h.sha_file(identity_path),
        "prediction_record": prediction_record,
        "pilot_report": pilot_report,
        "recent_2026_main_tour": {
            "parry": h.recent_player_rows(extension, h.PARRY_CANONICAL),
            "stearns": h.recent_player_rows(extension, h.STEARNS_CANONICAL),
        },
    }
    (root / "prediction-dossier.json").write_text(h.pretty(dossier), encoding="utf-8")
    print(h.pretty({
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
        "target_player_exclusions": {sr: dict(counts) for sr, counts in target_player_exclusions.items()},
    }))


if __name__ == "__main__":
    main()
