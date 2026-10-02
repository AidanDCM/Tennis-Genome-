"""Restore the accepted research history from a local pinned-source ZIP.

Download the archive separately from the exact commit recorded by the frozen
bundle. This script makes no network calls and never changes that bundle.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

from tennis_genome.data.provenance import SourceMetadata
from tennis_genome.independent.production import (
    PINNED_SOURCE_COMMIT,
    verify_accepted_canonical_content,
)
from tennis_genome.pipeline.build_dataset import build_canonical_dataset_from_files


def restore(archive: Path, *, raw_root: Path, output_root: Path) -> dict[str, object]:
    prefix = f"tennis-sackmann-archive-{PINNED_SOURCE_COMMIT}/"
    results: dict[str, object] = {}
    with zipfile.ZipFile(archive) as source:
        members = source.namelist()
        if len(members) != len(set(members)):
            raise ValueError("pinned archive contains duplicate members")
        for tour in ("ATP", "WTA"):
            lower = tour.lower()
            raw_dir = raw_root / lower
            raw_dir.mkdir(parents=True, exist_ok=True)
            inputs: list[Path] = []
            for year in range(2000, 2026):
                filename = f"{lower}_matches_{year}.csv"
                member = f"{prefix}{lower}/{filename}"
                if member not in members:
                    raise ValueError(f"pinned archive lacks {member}")
                payload = source.read(member)
                target = raw_dir / filename
                if target.exists():
                    if hashlib.sha256(target.read_bytes()).digest() != hashlib.sha256(
                        payload
                    ).digest():
                        raise ValueError(f"existing source differs from pinned archive: {target}")
                else:
                    target.write_bytes(payload)
                inputs.append(target)
            metadata = SourceMetadata(
                source_id=f"sackmann-archive-{PINNED_SOURCE_COMMIT}-{lower}-2000-2025",
                provider="Jeff Sackmann / Tennis Abstract via Aneeshers archival mirror",
                source_version=PINNED_SOURCE_COMMIT,
                license_name="CC BY-NC-SA 4.0",
                license_url="https://creativecommons.org/licenses/by-nc-sa/4.0/",
                allowed_use_status="research_allowed",
            )
            manifest = build_canonical_dataset_from_files(
                source_csvs=inputs,
                tour=tour,
                output_dir=output_root / lower,
                source_metadata=metadata,
            )
            content_hash = verify_accepted_canonical_content(tour, manifest)
            results[tour] = {
                "source_file_count": len(inputs),
                "row_count": manifest["row_count"],
                "accepted_content_sha256": content_hash,
                "allowed_use_status": metadata.allowed_use_status,
            }
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--raw-root", type=Path, default=Path("data/independent_freeze_raw"))
    parser.add_argument(
        "--output-root", type=Path, default=Path("data/independent_freeze_processed")
    )
    args = parser.parse_args()
    print(
        json.dumps(
            restore(args.archive, raw_root=args.raw_root, output_root=args.output_root),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
