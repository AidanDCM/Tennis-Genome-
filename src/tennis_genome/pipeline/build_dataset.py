from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import cast

import pandas as pd

from tennis_genome.data.canonical import HistoricalMatch, Tour
from tennis_genome.data.quality import audit_historical_matches, raise_for_quality_errors
from tennis_genome.data.sackmann import load_sackmann_csv

SCHEMA_VERSION = "canonical-v1"


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _pre_match_frame(matches: list[HistoricalMatch]) -> pd.DataFrame:
    return pd.DataFrame([asdict(match.pre_match) for match in matches])


def _outcome_frame(matches: list[HistoricalMatch]) -> pd.DataFrame:
    return pd.DataFrame([asdict(match.outcome) for match in matches])


def build_canonical_dataset(
    *,
    source_csv: Path,
    tour: Tour,
    output_dir: Path,
) -> dict[str, object]:
    """Build versioned Parquet tables plus an auditable provenance manifest."""
    source_csv = source_csv.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    matches = load_sackmann_csv(source_csv, tour=tour)
    if not matches:
        raise ValueError("source CSV contains no matches")

    issues = audit_historical_matches(matches)
    raise_for_quality_errors(issues)

    pre_match_path = output_dir / f"{tour.lower()}_pre_match.parquet"
    outcome_path = output_dir / f"{tour.lower()}_outcomes.parquet"
    manifest_path = output_dir / f"{tour.lower()}_manifest.json"

    pre_match = _pre_match_frame(matches)
    outcomes = _outcome_frame(matches)
    pre_match.to_parquet(pre_match_path, index=False)
    outcomes.to_parquet(outcome_path, index=False)

    warning_counts: dict[str, int] = {}
    for issue in issues:
        if issue.severity != "warning":
            continue
        warning_counts[issue.code] = warning_counts.get(issue.code, 0) + 1

    dates = [match.pre_match.event_date for match in matches]
    manifest: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "source_format": "sackmann_style_csv",
        "source_filename": source_csv.name,
        "source_sha256": _sha256_file(source_csv),
        "tour": tour,
        "row_count": len(matches),
        "date_min": min(dates).isoformat(),
        "date_max": max(dates).isoformat(),
        "pre_match_filename": pre_match_path.name,
        "pre_match_sha256": _sha256_file(pre_match_path),
        "outcome_filename": outcome_path.name,
        "outcome_sha256": _sha256_file(outcome_path),
        "quality_warning_counts": warning_counts,
        "built_at_utc": datetime.now(UTC).isoformat(),
        "notes": [
            "pre-match and outcome tables are intentionally separated",
            "field timestamp semantics still require source-specific audit before final claims",
            "same-day exact start times are not inferred by this builder",
        ],
    }
    manifest_text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    manifest_path.write_text(manifest_text, encoding="utf-8")
    return manifest


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build canonical Tennis Genome historical data")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--tour", required=True, choices=("ATP", "WTA"))
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    manifest = build_canonical_dataset(
        source_csv=args.input,
        tour=cast(Tour, args.tour),
        output_dir=args.output_dir,
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
