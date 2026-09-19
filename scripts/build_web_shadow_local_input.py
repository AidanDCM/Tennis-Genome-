from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

from tennis_genome.data.canonical import HistoricalMatch, MatchOutcome, PreMatchState
from tennis_genome.data.parquet import load_canonical_parquet
from tennis_genome.features.foundational import walk_forward_foundational_features
from tennis_genome.prospective.web_shadow import WebShadowFixture
from tennis_genome.ratings.serve_return import walk_forward_serve_return


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _jsonable(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _jsonable(nested) for key, nested in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(nested) for nested in value]
    return value


def _load_fixture(path: Path) -> WebShadowFixture:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("fixture JSON must contain an object")
    fixture = WebShadowFixture(**raw)
    fixture.validate()
    return fixture


def _load_target_state(path: Path, fixture: WebShadowFixture) -> PreMatchState:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("target-state JSON must contain an object")
    normalized = dict(raw)
    normalized["event_date"] = date.fromisoformat(str(normalized.get("event_date", "")))
    normalized["source_order"] = 10**9
    target = PreMatchState(**normalized)
    if target.tour != "WTA" or fixture.tour != "WTA":
        raise ValueError("local web-shadow input builder currently supports WTA only")
    if target.match_id != fixture.match_id:
        raise ValueError("target-state match_id differs from frozen web fixture")
    if target.player_a_name != fixture.player_a or target.player_b_name != fixture.player_b:
        raise ValueError("target-state player names differ from frozen web fixture order")
    scheduled = datetime.fromisoformat(fixture.scheduled_start)
    if target.event_date != scheduled.date():
        raise ValueError("target-state event date differs from fixture scheduled date")
    if target.best_of != 3:
        raise ValueError("WTA web-shadow target must be best-of-3")
    if target.player_a_id >= target.player_b_id:
        raise ValueError("target-state player IDs must use canonical ascending order")
    return target


def build_local_web_shadow_matchup(
    *,
    fixture_path: Path,
    target_state_path: Path,
    base_dir: Path,
    output_path: Path,
    manifest_path: Path,
) -> dict[str, object]:
    fixture = _load_fixture(fixture_path)
    target = _load_target_state(target_state_path, fixture)

    pre_match_path = base_dir / "wta_pre_match.parquet"
    outcome_path = base_dir / "wta_outcomes.parquet"
    stats_path = base_dir / "wta_stats.parquet"
    for path in (pre_match_path, outcome_path, stats_path):
        if not path.is_file():
            raise FileNotFoundError(f"required frozen WTA history is missing: {path}")

    history = load_canonical_parquet(
        pre_match_path=pre_match_path,
        outcome_path=outcome_path,
        stats_path=stats_path,
    )
    base_history = tuple(
        match
        for match in history
        if not match.outcome.walkover and not match.outcome.retirement
    )
    if not base_history:
        raise RuntimeError("frozen WTA base history is empty")
    max_history_date = max(match.pre_match.event_date for match in base_history)
    if max_history_date >= target.event_date:
        raise RuntimeError("local base history reaches target date and violates chronology")

    sentinel = HistoricalMatch(
        pre_match=target,
        outcome=MatchOutcome(
            match_id=target.match_id,
            a_won=False,
            score=None,
            retirement=False,
            walkover=False,
        ),
        stats=None,
    )
    combined = [*base_history, sentinel]
    foundational = next(
        snapshot
        for snapshot in walk_forward_foundational_features(
            combined,
            exclude_retirements=False,
        )
        if snapshot.match_id == target.match_id
    )
    serve_return = next(
        snapshot
        for snapshot in walk_forward_serve_return(
            combined,
            exclude_retirements=False,
        )
        if snapshot.match_id == target.match_id
    )

    cutoff = datetime.fromisoformat(fixture.source_observed_at)
    scheduled = datetime.fromisoformat(fixture.scheduled_start)
    if cutoff >= scheduled:
        raise ValueError("fixture source observation must precede scheduled start")

    source_hashes = [
        _sha256_file(pre_match_path),
        _sha256_file(outcome_path),
        _sha256_file(stats_path),
        _sha256_file(fixture_path),
        _sha256_file(target_state_path),
    ]
    payload: dict[str, object] = {
        "prediction_id": f"web-shadow:{target.match_id}:{int(cutoff.timestamp())}",
        "match_id": target.match_id,
        "tour": "WTA",
        "player_a_id": target.player_a_id,
        "player_b_id": target.player_b_id,
        "created_at": cutoff.isoformat(),
        "prediction_cutoff_at": cutoff.isoformat(),
        "foundational": _jsonable(asdict(foundational)),
        "source_manifest_hashes": source_hashes,
        "best_of": 3,
        "profile_pair": None,
        "serve_return": _jsonable(asdict(serve_return)),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )

    manifest: dict[str, object] = {
        "schema_version": "tennis-genome-web-shadow-local-input-v1",
        "history_mode": "FROZEN_LOCAL_HISTORY_ONLY",
        "production_eligible": False,
        "fixture_match_id": target.match_id,
        "base_history_match_count": len(base_history),
        "base_history_max_event_date": max_history_date.isoformat(),
        "target_event_date": target.event_date.isoformat(),
        "prediction_cutoff_at": cutoff.isoformat(),
        "known_limitation": (
            "This temporary lane omits post-freeze 2026 provider-history extensions; "
            "it is suitable for shadow experimentation, not production cutover evidence."
        ),
        "source_manifest_hashes": source_hashes,
        "matchup_input_sha256": _sha256_file(output_path),
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return manifest


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a provider-free WTA matchup input for Web Shadow"
    )
    parser.add_argument("--fixture", required=True, type=Path)
    parser.add_argument("--target-state", required=True, type=Path)
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=Path("data/wta-live-base"),
    )
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    manifest = build_local_web_shadow_matchup(
        fixture_path=args.fixture,
        target_state_path=args.target_state,
        base_dir=args.base_dir,
        output_path=args.output,
        manifest_path=args.manifest,
    )
    print(json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
