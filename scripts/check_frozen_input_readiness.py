"""Offline inventory for inputs needed to run the sealed ATP/WTA calculator.

This command never opens a network connection. Presence of a history file is
reported separately from proof that its data is current or legally available.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import fields
from pathlib import Path

from tennis_genome.calculator.engine import MatchupCalculator
from tennis_genome.features.foundational import FoundationalSnapshot
from tennis_genome.models.core_v1_spec import strict_a_features
from tennis_genome.profiles.state import PlayerProfileSnapshot
from tennis_genome.ratings.serve_return import ServeReturnSnapshot


def inspect_readiness(*, bundle_path: Path, history_root: Path) -> dict[str, object]:
    """Verify sealed model files and inventory candidate source-state files."""

    calculator = MatchupCalculator.from_bundle_path(bundle_path)
    field_names = {item.name for item in fields(FoundationalSnapshot)}
    inputs: dict[str, object] = {}
    for tour in ("ATP", "WTA"):
        core = list(strict_a_features(tour))
        missing_schema = sorted(set(core) - field_names)
        if missing_schema:
            raise ValueError(f"{tour} frozen Core has unknown fields: {missing_schema}")
        directory = history_root / tour.lower()
        paths = {
            label: directory / f"{tour.lower()}_{stem}.parquet"
            for label, stem in (
                ("pre_match", "pre_match"),
                ("outcomes", "outcomes"),
                ("stats", "stats"),
            )
        }
        present = {label: path.is_file() for label, path in paths.items()}
        inputs[tour] = {
            "core_feature_names": core,
            "core_feature_count": len(core),
            "extra_calculator_state": (
                "MatchProfilePair" if tour == "ATP" else "ServeReturnSnapshot"
            ),
            "history_files": {label: str(path) for label, path in paths.items()},
            "history_files_present": present,
            "history_candidate_complete": all(present.values()),
            "state_semantics_verified": False,
            "prestart_source_evidence_verified": False,
            "prediction_ready": False,
        }

    return {
        "schema": "tennis-genome-offline-input-readiness-v1",
        "network_requests": 0,
        "production_bundle_sha256": calculator.bundle.artifact_sha256,
        "production_bundle_verified": True,
        "foundational_fields": [item.name for item in fields(FoundationalSnapshot)],
        "atp_profile_fields": [item.name for item in fields(PlayerProfileSnapshot)],
        "wta_serve_return_fields": [item.name for item in fields(ServeReturnSnapshot)],
        "tours": inputs,
        "note": (
            "File presence alone cannot establish identity, cutoff, current state, "
            "source rights or pre-start prediction eligibility."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bundle",
        type=Path,
        default=Path("artifacts/tge_independent_v1_production/")
        / "tge_independent_v1_production.json",
    )
    parser.add_argument(
        "--history-root", type=Path, default=Path("data/independent_freeze_processed")
    )
    args = parser.parse_args()
    print(
        json.dumps(
            inspect_readiness(bundle_path=args.bundle, history_root=args.history_root),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
