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
from tennis_genome.data.manifest import sha256_file
from tennis_genome.data.provenance import AllowedUseStatus, SourceMetadata
from tennis_genome.data.quality import audit_historical_matches, raise_for_quality_errors
from tennis_genome.data.sackmann import load_sackmann_csvs

SCHEMA_VERSION = "canonical-v2"


def _pre_match_frame(matches: list[HistoricalMatch]) -> pd.DataFrame:
    return pd.DataFrame([asdict(match.pre_match) for match in matches])


def _outcome_frame(matches: list[HistoricalMatch]) -> pd.DataFrame:
    return pd.DataFrame([asdict(match.outcome) for match in matches])


def _stats_frame(matches: list[HistoricalMatch]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            asdict(match.stats)
            if match.stats is not None
            else {"match_id": match.match_id}
            for match in matches
        ]
    )


def _source_file_records(paths: list[Path]) -> list[dict[str, str]]:
    return [{"filename": path.name, "sha256": sha256_file(path)} for path in paths]


def _source_bundle_sha256(records: list[dict[str, str]]) -> str:
    payload = json.dumps(records, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(payload).hexdigest()


def build_canonical_dataset_from_files(
    *,
    source_csvs: list[Path],
    tour: Tour,
    output_dir: Path,
    source_metadata: SourceMetadata | None = None,
) -> dict[str, object]:
    """Build canonical Parquet tables from one or more auditable source CSVs."""
    paths = sorted((path.resolve() for path in source_csvs), key=str)
    if not paths:
        raise ValueError("at least one source CSV is required")

    output_dir.mkdir(parents=True, exist_ok=True)
    source_metadata = source_metadata or SourceMetadata(
        source_id=paths[0].name if len(paths) == 1 else "multi_file_bundle",
        provider="unspecified",
    )

    matches = load_sackmann_csvs(paths, tour=tour)
    if not matches:
        raise ValueError("source CSV bundle contains no matches")

    issues = audit_historical_matches(matches)
    raise_for_quality_errors(issues)

    pre_match_path = output_dir / f"{tour.lower()}_pre_match.parquet"
    outcome_path = output_dir / f"{tour.lower()}_outcomes.parquet"
    stats_path = output_dir / f"{tour.lower()}_stats.parquet"
    manifest_path = output_dir / f"{tour.lower()}_manifest.json"

    _pre_match_frame(matches).to_parquet(pre_match_path, index=False)
    _outcome_frame(matches).to_parquet(outcome_path, index=False)
    _stats_frame(matches).to_parquet(stats_path, index=False)

    warning_counts: dict[str, int] = {}
    for issue in issues:
        if issue.severity == "warning":
            warning_counts[issue.code] = warning_counts.get(issue.code, 0) + 1

    source_files = _source_file_records(paths)
    source_bundle_hash = _source_bundle_sha256(source_files)
    is_single_file = len(paths) == 1
    dates = [match.pre_match.event_date for match in matches]
    manifest: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "source_format": (
            "sackmann_style_csv" if is_single_file else "sackmann_style_csv_bundle"
        ),
        "source_filename": paths[0].name if is_single_file else "multi_file_bundle",
        "source_sha256": (
            source_files[0]["sha256"] if is_single_file else source_bundle_hash
        ),
        "source_files": source_files,
        "source_file_count": len(paths),
        "source_bundle_sha256": source_bundle_hash,
        "source_metadata": source_metadata.to_manifest(),
        "tour": tour,
        "row_count": len(matches),
        "date_min": min(dates).isoformat(),
        "date_max": max(dates).isoformat(),
        "pre_match_filename": pre_match_path.name,
        "pre_match_sha256": sha256_file(pre_match_path),
        "outcome_filename": outcome_path.name,
        "outcome_sha256": sha256_file(outcome_path),
        "stats_filename": stats_path.name,
        "stats_sha256": sha256_file(stats_path),
        "quality_warning_counts": warning_counts,
        "built_at_utc": datetime.now(UTC).isoformat(),
        "notes": [
            "pre-match, outcome, and post-match stats tables are intentionally separated",
            "target-match stats are never legal pre-match features",
            "field timestamp semantics still require source-specific audit before final claims",
            "same-day exact start times are not inferred by this builder",
            "multi-file bundles are sorted by resolved path before ingestion",
        ],
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def build_canonical_dataset(
    *,
    source_csv: Path,
    tour: Tour,
    output_dir: Path,
    source_metadata: SourceMetadata | None = None,
) -> dict[str, object]:
    return build_canonical_dataset_from_files(
        source_csvs=[source_csv],
        tour=tour,
        output_dir=output_dir,
        source_metadata=source_metadata,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build canonical Tennis Genome historical data"
    )
    parser.add_argument("--input", required=True, type=Path, action="append")
    parser.add_argument("--tour", required=True, choices=("ATP", "WTA"))
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--source-id")
    parser.add_argument("--provider", default="unspecified")
    parser.add_argument("--source-version")
    parser.add_argument("--license-name")
    parser.add_argument("--license-url")
    parser.add_argument(
        "--allowed-use-status",
        choices=(
            "research_allowed",
            "production_allowed",
            "permission_required",
            "unknown_do_not_use",
        ),
        default="unknown_do_not_use",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    inputs: list[Path] = args.input
    source_metadata = SourceMetadata(
        source_id=(
            args.source_id
            or (inputs[0].name if len(inputs) == 1 else "multi_file_bundle")
        ),
        provider=args.provider,
        source_version=args.source_version,
        license_name=args.license_name,
        license_url=args.license_url,
        allowed_use_status=cast(AllowedUseStatus, args.allowed_use_status),
    )
    manifest = build_canonical_dataset_from_files(
        source_csvs=inputs,
        tour=cast(Tour, args.tour),
        output_dir=args.output_dir,
        source_metadata=source_metadata,
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
