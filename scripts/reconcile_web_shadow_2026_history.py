from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import pandas as pd

from tennis_genome.data.sackmann import load_sackmann_csv


def _sha256_ids(values: list[str]) -> str:
    payload = "\n".join(sorted(values)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _duplicate_ids(values: list[str]) -> list[str]:
    counts = Counter(values)
    return sorted(value for value, count in counts.items() if count > 1)


def reconcile_2026_sources(
    *,
    primary_path: Path,
    secondary_path: Path,
    output_path: Path,
    receipt_path: Path,
) -> dict[str, object]:
    primary_matches = load_sackmann_csv(primary_path, tour="WTA")
    secondary_frame = pd.read_csv(secondary_path, low_memory=False)
    secondary_matches = load_sackmann_csv(secondary_path, tour="WTA")

    primary_ids = [match.pre_match.match_id for match in primary_matches]
    secondary_ids = [match.pre_match.match_id for match in secondary_matches]
    if duplicates := _duplicate_ids(primary_ids):
        raise ValueError(
            "primary 2026 source contains duplicate canonical match IDs: "
            + ", ".join(duplicates[:10])
        )
    if duplicates := _duplicate_ids(secondary_ids):
        raise ValueError(
            "secondary 2026 source contains duplicate canonical match IDs: "
            + ", ".join(duplicates[:10])
        )

    primary_set = set(primary_ids)
    removed_ids: list[str] = []
    working = secondary_frame.copy()

    for _ in range(4):
        temp_path = output_path.with_suffix(".working.csv")
        temp_path.parent.mkdir(parents=True, exist_ok=True)
        working.to_csv(temp_path, index=False)
        working_matches = load_sackmann_csv(temp_path, tour="WTA")
        working_ids = [match.pre_match.match_id for match in working_matches]
        overlap = primary_set.intersection(working_ids)
        if not overlap:
            temp_path.unlink(missing_ok=True)
            break
        keep = []
        for match in working_matches:
            match_id = match.pre_match.match_id
            should_keep = match_id not in overlap
            keep.append(should_keep)
            if not should_keep:
                removed_ids.append(match_id)
        working = working.loc[keep].reset_index(drop=True)
        temp_path.unlink(missing_ok=True)
    else:
        raise RuntimeError("2026 source reconciliation did not converge")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    working.to_csv(output_path, index=False)
    final_matches = load_sackmann_csv(output_path, tour="WTA")
    final_ids = [match.pre_match.match_id for match in final_matches]

    if overlap := primary_set.intersection(final_ids):
        raise RuntimeError(
            "reconciled 2026 source still overlaps primary IDs: "
            + ", ".join(sorted(overlap)[:10])
        )
    if duplicates := _duplicate_ids(final_ids):
        raise RuntimeError(
            "reconciled 2026 source contains internal duplicate IDs: "
            + ", ".join(duplicates[:10])
        )

    unique_removed = sorted(set(removed_ids))
    receipt: dict[str, object] = {
        "schema_version": "tennis-genome-web-shadow-2026-source-reconciliation-v1",
        "primary_source": primary_path.as_posix(),
        "secondary_source": secondary_path.as_posix(),
        "reconciled_secondary": output_path.as_posix(),
        "primary_match_count": len(primary_ids),
        "secondary_original_match_count": len(secondary_ids),
        "secondary_reconciled_match_count": len(final_ids),
        "removed_overlap_count": len(secondary_ids) - len(final_ids),
        "removed_overlap_unique_id_count": len(unique_removed),
        "removed_overlap_ids_sha256": _sha256_ids(unique_removed),
        "removed_overlap_ids": unique_removed,
    }
    if receipt["removed_overlap_count"] <= 0:
        raise RuntimeError("expected overlapping 2026 public sources but removed none")
    if (
        int(receipt["secondary_original_match_count"])
        - int(receipt["removed_overlap_count"])
        != int(receipt["secondary_reconciled_match_count"])
    ):
        raise RuntimeError("2026 reconciliation count accounting failed")

    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return receipt


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Remove canonical match-ID overlap from pinned 2026 WTA sources"
    )
    parser.add_argument("--primary", required=True, type=Path)
    parser.add_argument("--secondary", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    receipt = reconcile_2026_sources(
        primary_path=args.primary,
        secondary_path=args.secondary,
        output_path=args.output,
        receipt_path=args.receipt,
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
