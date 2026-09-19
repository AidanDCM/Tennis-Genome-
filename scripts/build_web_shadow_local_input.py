from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from tennis_genome.data.canonical import HistoricalMatch, MatchOutcome, PreMatchState
from tennis_genome.data.parquet import load_canonical_parquet
from tennis_genome.evaluation.walkforward import walk_forward_elo
from tennis_genome.features.foundational import (
    FoundationalSnapshot,
    walk_forward_foundational_features,
)
from tennis_genome.prospective.web_shadow import WebShadowFixture
from tennis_genome.ratings.serve_return import (
    ServeReturnSnapshot,
    walk_forward_serve_return,
)


@dataclass(frozen=True)
class WebShadowHistoryPreparation:
    base_history: tuple[HistoricalMatch, ...]
    max_history_date: date
    player_match_counts: dict[str, int]
    history_source_hashes: tuple[str, ...]
    history_mode: str


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


def load_web_shadow_fixture(path: Path) -> WebShadowFixture:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("fixture JSON must contain an object")
    fixture = WebShadowFixture(**raw)
    fixture.validate()
    return fixture


def _load_fixture(path: Path) -> WebShadowFixture:
    return load_web_shadow_fixture(path)


def load_web_shadow_target_state(
    path: Path,
    fixture: WebShadowFixture,
) -> PreMatchState:
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
    target_names = {target.player_a_name, target.player_b_name}
    fixture_names = {fixture.player_a, fixture.player_b}
    if target_names != fixture_names:
        raise ValueError("target-state player names differ from frozen web fixture")
    scheduled = datetime.fromisoformat(fixture.scheduled_start)
    if target.event_date != scheduled.date():
        raise ValueError("target-state event date differs from fixture scheduled date")
    if target.best_of != 3:
        raise ValueError("WTA web-shadow target must be best-of-3")
    if target.player_a_id >= target.player_b_id:
        raise ValueError("target-state player IDs must use canonical ascending order")
    return target


def _load_target_state(path: Path, fixture: WebShadowFixture) -> PreMatchState:
    return load_web_shadow_target_state(path, fixture)


def prepare_web_shadow_history(
    *,
    base_dir: Path,
    history_mode: str = "FROZEN_LOCAL_HISTORY_ONLY",
    expected_history_max_date: date | None = None,
) -> WebShadowHistoryPreparation:
    pre_match_path = base_dir / "wta_pre_match.parquet"
    outcome_path = base_dir / "wta_outcomes.parquet"
    stats_path = base_dir / "wta_stats.parquet"
    history_paths = (pre_match_path, outcome_path, stats_path)
    for path in history_paths:
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
    if (
        expected_history_max_date is not None
        and max_history_date != expected_history_max_date
    ):
        raise RuntimeError(
            "web-shadow history maximum date differs from pinned expectation: "
            f"{max_history_date.isoformat()} != "
            f"{expected_history_max_date.isoformat()}"
        )

    player_match_counts: Counter[str] = Counter()
    for match in base_history:
        player_match_counts[match.pre_match.player_a_id] += 1
        player_match_counts[match.pre_match.player_b_id] += 1

    return WebShadowHistoryPreparation(
        base_history=base_history,
        max_history_date=max_history_date,
        player_match_counts=dict(player_match_counts),
        history_source_hashes=tuple(_sha256_file(path) for path in history_paths),
        history_mode=history_mode,
    )


def target_history_counts(
    prepared: WebShadowHistoryPreparation,
    target: PreMatchState,
) -> dict[str, int]:
    if prepared.max_history_date >= target.event_date:
        raise RuntimeError("local base history reaches target date and violates chronology")
    counts = {
        target.player_a_id: prepared.player_match_counts.get(target.player_a_id, 0),
        target.player_b_id: prepared.player_match_counts.get(target.player_b_id, 0),
    }
    missing_history = [
        player_id
        for player_id, count in counts.items()
        if count <= 0
    ]
    if missing_history:
        raise RuntimeError(
            "web-shadow target identity has no frozen historical matches: "
            + ", ".join(missing_history)
        )
    return counts


def prepare_web_shadow_snapshots(
    *,
    prepared: WebShadowHistoryPreparation,
    targets: list[PreMatchState],
) -> tuple[
    dict[str, FoundationalSnapshot],
    dict[str, ServeReturnSnapshot],
    int,
]:
    if not targets:
        return {}, {}, 0

    by_date: defaultdict[date, list[PreMatchState]] = defaultdict(list)
    seen_match_ids: set[str] = set()
    for target in targets:
        if target.match_id in seen_match_ids:
            raise ValueError(f"duplicate Web Shadow target match_id: {target.match_id}")
        seen_match_ids.add(target.match_id)
        target_history_counts(prepared, target)
        by_date[target.event_date].append(target)

    foundational_by_id: dict[str, FoundationalSnapshot] = {}
    serve_return_by_id: dict[str, ServeReturnSnapshot] = {}

    for event_date in sorted(by_date):
        date_targets = by_date[event_date]
        sentinels = [
            HistoricalMatch(
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
            for target in date_targets
        ]
        target_ids = {target.match_id for target in date_targets}
        combined = [*prepared.base_history, *sentinels]

        elo_predictions = walk_forward_elo(
            combined,
            exclude_retirements=False,
        )
        serve_snapshots = walk_forward_serve_return(
            combined,
            exclude_retirements=False,
        )
        for snapshot in walk_forward_foundational_features(
            combined,
            exclude_retirements=False,
            precomputed_elo=elo_predictions,
            precomputed_serve_return=serve_snapshots,
        ):
            if snapshot.match_id in target_ids:
                foundational_by_id[snapshot.match_id] = snapshot

        for snapshot in serve_snapshots:
            if snapshot.match_id in target_ids:
                serve_return_by_id[snapshot.match_id] = snapshot

        missing_foundational = target_ids - foundational_by_id.keys()
        missing_serve_return = target_ids - serve_return_by_id.keys()
        if missing_foundational or missing_serve_return:
            raise RuntimeError(
                "shared Web Shadow feature preparation missed target snapshots: "
                f"foundational={sorted(missing_foundational)} "
                f"serve_return={sorted(missing_serve_return)}"
            )

    return foundational_by_id, serve_return_by_id, len(by_date)


def build_local_web_shadow_matchup(
    *,
    fixture_path: Path,
    target_state_path: Path,
    base_dir: Path,
    output_path: Path,
    manifest_path: Path,
    history_mode: str = "FROZEN_LOCAL_HISTORY_ONLY",
    expected_history_max_date: date | None = None,
    prepared_history: WebShadowHistoryPreparation | None = None,
    foundational_snapshot: FoundationalSnapshot | None = None,
    serve_return_snapshot: ServeReturnSnapshot | None = None,
) -> dict[str, object]:
    fixture = load_web_shadow_fixture(fixture_path)
    target = load_web_shadow_target_state(target_state_path, fixture)

    prepared = prepared_history or prepare_web_shadow_history(
        base_dir=base_dir,
        history_mode=history_mode,
        expected_history_max_date=expected_history_max_date,
    )
    if prepared.history_mode != history_mode:
        raise ValueError("prepared Web Shadow history mode differs from requested mode")
    if (
        expected_history_max_date is not None
        and prepared.max_history_date != expected_history_max_date
    ):
        raise RuntimeError(
            "prepared Web Shadow history maximum date differs from pinned expectation"
        )

    history_counts = target_history_counts(prepared, target)

    if (foundational_snapshot is None) != (serve_return_snapshot is None):
        raise ValueError("shared Web Shadow feature snapshots must be supplied together")
    if foundational_snapshot is None or serve_return_snapshot is None:
        foundational_by_id, serve_return_by_id, _ = prepare_web_shadow_snapshots(
            prepared=prepared,
            targets=[target],
        )
        foundational = foundational_by_id[target.match_id]
        serve_return = serve_return_by_id[target.match_id]
    else:
        foundational = foundational_snapshot
        serve_return = serve_return_snapshot
        if foundational.match_id != target.match_id:
            raise ValueError("shared foundational snapshot match_id differs from target")
        if serve_return.match_id != target.match_id:
            raise ValueError("shared serve/return snapshot match_id differs from target")

    minimum_point_exposure = min(
        serve_return.prior_serve_points_a,
        serve_return.prior_serve_points_b,
        serve_return.prior_return_points_a,
        serve_return.prior_return_points_b,
    )
    if minimum_point_exposure <= 0:
        raise RuntimeError(
            "web-shadow target lacks nonzero frozen historical point exposure"
        )

    cutoff = datetime.fromisoformat(fixture.source_observed_at)
    scheduled = datetime.fromisoformat(fixture.scheduled_start)
    if cutoff >= scheduled:
        raise ValueError("fixture source observation must precede scheduled start")

    source_hashes = [
        *prepared.history_source_hashes,
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
        "history_mode": history_mode,
        "production_eligible": False,
        "fixture_match_id": target.match_id,
        "base_history_match_count": len(prepared.base_history),
        "base_history_max_event_date": prepared.max_history_date.isoformat(),
        "target_history_match_counts": history_counts,
        "minimum_point_exposure": minimum_point_exposure,
        "target_event_date": target.event_date.isoformat(),
        "prediction_cutoff_at": cutoff.isoformat(),
        "known_limitation": (
            f"Pinned public history ends at {prepared.max_history_date.isoformat()}; "
            "later results are omitted. This lane is suitable for shadow "
            "experimentation, not production cutover evidence."
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
    parser.add_argument(
        "--history-mode",
        default="FROZEN_LOCAL_HISTORY_ONLY",
    )
    parser.add_argument("--expected-history-max-date")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    manifest = build_local_web_shadow_matchup(
        fixture_path=args.fixture,
        target_state_path=args.target_state,
        base_dir=args.base_dir,
        output_path=args.output,
        manifest_path=args.manifest,
        history_mode=args.history_mode,
        expected_history_max_date=(
            None
            if args.expected_history_max_date is None
            else date.fromisoformat(args.expected_history_max_date)
        ),
    )
    print(json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
