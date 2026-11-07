"""Freeze research-only logistic challenger weights from retained historical CSVs."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from tennis_genome.data.sackmann import load_sackmann_csvs
from tennis_genome.features.foundational import (
    FoundationalSnapshot,
    walk_forward_foundational_features,
)
from tennis_genome.research_workbench.simple_logit_challenger import (
    ChallengerExample,
    FrozenSimpleLogitChallenger,
    SimpleLogitChallenger,
)

_PINNED_UPSTREAM_COMMIT = "83733587353df8a41f2fd4f516147d5aa83f5a8d"


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _write_once(path: Path, value: object) -> None:
    data = json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != data:
            raise ValueError(f"existing frozen artifact differs: {path}")
        return
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(data, encoding="utf-8", newline="\n")
    temporary.replace(path)


def freeze_tour(data_dir: Path, output_dir: Path, *, tour: str) -> list[Path]:
    paths = [data_dir / f"{tour.lower()}_matches_{year}.csv" for year in range(2010, 2026)]
    source = {
        "tour": tour,
        "upstream_commit": _PINNED_UPSTREAM_COMMIT,
        "research_only": True,
        "source_files_sha256": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths
        },
    }
    source_digest = _sha256(source)
    matches = load_sackmann_csvs(paths, tour=tour)
    matches = [
        match
        for match in matches
        if match.outcome.score and not match.outcome.retirement and not match.outcome.walkover
    ]
    by_id = {match.match_id: match for match in matches}
    if len(by_id) != len(matches):
        raise ValueError("duplicate canonical match identity in training source")
    snapshots = walk_forward_foundational_features(matches)
    training = [snapshot for snapshot in snapshots if snapshot.event_date.year <= 2025]
    if not training or max(snapshot.event_date.year for snapshot in training) != 2025:
        raise ValueError("training history does not reach 2025")

    def _rank_complete(snapshot: FoundationalSnapshot) -> bool:
        state = by_id[snapshot.match_id].pre_match
        return all(
            value is not None and value > 0
            for value in (state.rank_a, state.rank_b, state.rank_points_a, state.rank_points_b)
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_once(output_dir / f"{tour.lower()}-source-manifest.json", source)
    written = []
    for include_rank, arm in ((False, "base"), (True, "rank")):
        selected = [
            snapshot for snapshot in training if not include_rank or _rank_complete(snapshot)
        ]
        examples = [
            ChallengerExample(
                snapshot=snapshot,
                state=by_id[snapshot.match_id].pre_match,
                outcome_a=by_id[snapshot.match_id].outcome.a_won,
            )
            for snapshot in selected
        ]
        population_digest = _sha256(
            [(example.snapshot.match_id, example.outcome_a) for example in examples]
        )
        fitted = SimpleLogitChallenger(include_rank=include_rank).fit(examples)
        frozen = fitted.freeze(
            tour=tour,
            training_population_sha256=population_digest,
            source_manifest_sha256=source_digest,
        )
        record = frozen.sealed_record()
        restored = FrozenSimpleLogitChallenger.from_sealed_record(record)
        if restored != frozen:
            raise AssertionError("frozen artifact failed round-trip verification")
        filename = f"{tour.lower()}-{arm}-{record['semantic_sha256']}.json"
        target = output_dir / filename
        _write_once(target, record)
        written.append(target)
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    for tour in ("ATP", "WTA"):
        for path in freeze_tour(args.data_dir, args.output_dir, tour=tour):
            print(path)


if __name__ == "__main__":
    main()
