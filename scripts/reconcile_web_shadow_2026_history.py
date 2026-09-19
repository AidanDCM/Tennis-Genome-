from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

from tennis_genome.data.sackmann import load_sackmann_csv


def _sha256_ids(values: list[str]) -> str:
    payload = "\n".join(sorted(values)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _duplicate_ids(values: list[str]) -> list[str]:
    counts = Counter(values)
    return sorted(value for value, count in counts.items() if count > 1)


def _normalized_row(row: pd.Series) -> tuple[str, ...]:
    return tuple("" if pd.isna(value) else str(value) for value in row.tolist())


def reconcile_2026_sources(
    *,
    primary_path: Path,
    secondary_path: Path,
    output_path: Path,
    receipt_path: Path,
    expected_exact_duplicate_rows: int | None = None,
    expected_cross_source_overlap_rows: int | None = None,
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

    secondary_indices_by_id: dict[str, list[int]] = defaultdict(list)
    for index, match_id in enumerate(secondary_ids):
        secondary_indices_by_id[match_id].append(index)

    internal_duplicate_ids = sorted(
        match_id
        for match_id, indices in secondary_indices_by_id.items()
        if len(indices) > 1
    )
    for match_id in internal_duplicate_ids:
        indices = secondary_indices_by_id[match_id]
        rows = {
            _normalized_row(secondary_frame.iloc[index])
            for index in indices
        }
        if len(rows) != 1:
            raise ValueError(
                "secondary 2026 source contains conflicting rows for canonical "
                f"match ID {match_id}"
            )

    exact_duplicate_mask = secondary_frame.duplicated(keep="first")
    exact_duplicate_rows_removed = int(exact_duplicate_mask.sum())
    if expected_exact_duplicate_rows is not None:
        if exact_duplicate_rows_removed != expected_exact_duplicate_rows:
            raise RuntimeError(
                "secondary exact-duplicate row count differs from pinned expectation: "
                f"{exact_duplicate_rows_removed} != {expected_exact_duplicate_rows}"
            )
    if exact_duplicate_rows_removed != sum(
        len(secondary_indices_by_id[match_id]) - 1
        for match_id in internal_duplicate_ids
    ):
        raise RuntimeError(
            "secondary canonical duplicate IDs are not explained entirely by exact rows"
        )

    working = secondary_frame.loc[~exact_duplicate_mask].reset_index(drop=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_suffix(".working.csv")
    working.to_csv(temp_path, index=False)
    deduped_matches = load_sackmann_csv(temp_path, tour="WTA")
    deduped_ids = [match.pre_match.match_id for match in deduped_matches]
    if duplicates := _duplicate_ids(deduped_ids):
        temp_path.unlink(missing_ok=True)
        raise RuntimeError(
            "secondary 2026 source still contains canonical duplicates after exact "
            "row collapse: "
            + ", ".join(duplicates[:10])
        )

    primary_set = set(primary_ids)
    cross_source_removed_ids: list[str] = []
    cross_source_rows_removed = 0

    for _ in range(4):
        working.to_csv(temp_path, index=False)
        working_matches = load_sackmann_csv(temp_path, tour="WTA")
        working_ids = [match.pre_match.match_id for match in working_matches]
        overlap = primary_set.intersection(working_ids)
        if not overlap:
            temp_path.unlink(missing_ok=True)
            break

        keep: list[bool] = []
        for match in working_matches:
            match_id = match.pre_match.match_id
            should_keep = match_id not in overlap
            keep.append(should_keep)
            if not should_keep:
                cross_source_removed_ids.append(match_id)
                cross_source_rows_removed += 1
        working = working.loc[keep].reset_index(drop=True)
    else:
        temp_path.unlink(missing_ok=True)
        raise RuntimeError("2026 source reconciliation did not converge")

    if expected_cross_source_overlap_rows is not None:
        if cross_source_rows_removed != expected_cross_source_overlap_rows:
            raise RuntimeError(
                "cross-source overlap row count differs from pinned expectation: "
                f"{cross_source_rows_removed} != "
                f"{expected_cross_source_overlap_rows}"
            )

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

    unique_cross_source_ids = sorted(set(cross_source_removed_ids))
    receipt: dict[str, object] = {
        "schema_version": "tennis-genome-web-shadow-2026-source-reconciliation-v2",
        "primary_source": primary_path.as_posix(),
        "secondary_source": secondary_path.as_posix(),
        "reconciled_secondary": output_path.as_posix(),
        "primary_match_count": len(primary_ids),
        "secondary_original_match_count": len(secondary_ids),
        "secondary_internal_exact_duplicate_id_count": len(internal_duplicate_ids),
        "secondary_internal_exact_duplicate_rows_removed": (
            exact_duplicate_rows_removed
        ),
        "secondary_internal_exact_duplicate_ids_sha256": _sha256_ids(
            internal_duplicate_ids
        ),
        "secondary_internal_conflicting_id_count": 0,
        "cross_source_overlap_rows_removed": cross_source_rows_removed,
        "cross_source_overlap_unique_id_count": len(unique_cross_source_ids),
        "cross_source_overlap_ids_sha256": _sha256_ids(unique_cross_source_ids),
        "secondary_reconciled_match_count": len(final_ids),
    }
    if (
        len(secondary_ids)
        - exact_duplicate_rows_removed
        - cross_source_rows_removed
        != len(final_ids)
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
        description="Reconcile pinned 2026 WTA public-history source duplicates"
    )
    parser.add_argument("--primary", required=True, type=Path)
    parser.add_argument("--secondary", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--expected-exact-duplicate-rows", type=int)
    parser.add_argument("--expected-cross-source-overlap-rows", type=int)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    receipt = reconcile_2026_sources(
        primary_path=args.primary,
        secondary_path=args.secondary,
        output_path=args.output,
        receipt_path=args.receipt,
        expected_exact_duplicate_rows=args.expected_exact_duplicate_rows,
        expected_cross_source_overlap_rows=args.expected_cross_source_overlap_rows,
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
