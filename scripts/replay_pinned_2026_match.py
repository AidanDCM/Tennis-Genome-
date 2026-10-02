"""Offline engineering replay of one archived 2026 match per tour.

The archive was captured after these matches. Outputs are retrospective
mechanical checks and must never enter a prospective evaluation ledger.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from datetime import UTC, date, datetime
from pathlib import Path

from tennis_genome.calculator.engine import MatchupCalculator
from tennis_genome.calculator.types import MatchupInput
from tennis_genome.data.canonical import HistoricalMatch, MatchOutcome
from tennis_genome.data.parquet import load_canonical_parquet
from tennis_genome.data.sackmann import load_sackmann_csvs
from tennis_genome.features.foundational import walk_forward_foundational_features
from tennis_genome.independent.production import PINNED_SOURCE_COMMIT
from tennis_genome.profiles.state import walk_forward_player_profiles
from tennis_genome.ratings.serve_return import walk_forward_serve_return


def replay(*, archive: Path, history_root: Path, bundle: Path, tour: str) -> dict[str, object]:
    lower = tour.lower()
    directory = history_root / lower
    base = load_canonical_parquet(
        pre_match_path=directory / f"{lower}_pre_match.parquet",
        outcome_path=directory / f"{lower}_outcomes.parquet",
        stats_path=directory / f"{lower}_stats.parquet",
    )
    member = (
        f"tennis-sackmann-archive-{PINNED_SOURCE_COMMIT}/"
        f"{lower}/{lower}_matches_2026.csv"
    )
    with zipfile.ZipFile(archive) as source:
        partial = source.read(member)
    raw_path = directory / f"{lower}_matches_2026.csv"
    if raw_path.exists() and raw_path.read_bytes() != partial:
        raise ValueError("existing 2026 file differs from pinned archive")
    if not raw_path.exists():
        raw_path.write_bytes(partial)
    extension = load_sackmann_csvs([raw_path], tour=tour)
    candidates = [
        match
        for match in extension
        if match.pre_match.event_date >= date(2026, 4, 1)
        and not match.outcome.walkover
        and not match.outcome.retirement
    ]
    if not candidates:
        raise ValueError(f"no usable 2026 {tour} engineering target")
    candidates.sort(key=lambda item: (item.pre_match.event_date, item.match_id))
    target = candidates[0]
    cutoff_date = target.pre_match.event_date
    history = [
        row
        for row in [*base, *extension]
        if row.pre_match.event_date < cutoff_date
        and not row.outcome.walkover
        and not row.outcome.retirement
    ]
    sentinel = HistoricalMatch(
        pre_match=target.pre_match,
        outcome=MatchOutcome(
            match_id=target.match_id,
            a_won=False,
            score=None,
            retirement=False,
            walkover=False,
        ),
        stats=None,
    )
    replay_rows = [*history, sentinel]
    foundational = next(
        row
        for row in walk_forward_foundational_features(replay_rows, exclude_retirements=False)
        if row.match_id == target.match_id
    )
    profile = None
    serve = None
    if tour == "ATP":
        profile = next(
            row
            for row in walk_forward_player_profiles(replay_rows, exclude_retirements=False)
            if row.match_id == target.match_id
        )
    else:
        serve = next(
            row
            for row in walk_forward_serve_return(replay_rows, exclude_retirements=False)
            if row.match_id == target.match_id
        )
    now = datetime.now(UTC)
    inputs = MatchupInput(
        prediction_id=f"ENGINEERING-REPLAY-{tour}-{target.match_id}",
        match_id=target.match_id,
        tour=tour,
        player_a_id=target.pre_match.player_a_id,
        player_b_id=target.pre_match.player_b_id,
        created_at=now,
        prediction_cutoff_at=now,
        foundational=foundational,
        profile_pair=profile,
        serve_return=serve,
        source_manifest_hashes=(
            hashlib.sha256((directory / f"{lower}_manifest.json").read_bytes()).hexdigest(),
            hashlib.sha256(partial).hexdigest(),
        ),
        best_of=target.pre_match.best_of,
    )
    calculation = MatchupCalculator.from_bundle_path(bundle).calculate(inputs)
    return {
        "label": "RETROSPECTIVE_ENGINEERING_REPLAY_NOT_PROSPECTIVE",
        "tour": tour,
        "event_date": cutoff_date.isoformat(),
        "match_id": target.match_id,
        "player_a": target.pre_match.player_a_name,
        "player_b": target.pre_match.player_b_name,
        "prior_history_rows": len(history),
        "production_bundle_sha256": calculation.production_bundle_sha256,
        "probability_a": calculation.prediction.p_player_a,
        "probability_b": calculation.prediction.p_player_b,
        "known_outcome_a": target.outcome.a_won,
        "source_available_after_match": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument(
        "--history-root", type=Path, default=Path("data/independent_freeze_processed")
    )
    parser.add_argument(
        "--bundle",
        type=Path,
        default=Path("artifacts/tge_independent_v1_production/")
        / "tge_independent_v1_production.json",
    )
    parser.add_argument("--tour", choices=("ATP", "WTA"), required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            replay(
                archive=args.archive,
                history_root=args.history_root,
                bundle=args.bundle,
                tour=args.tour,
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
