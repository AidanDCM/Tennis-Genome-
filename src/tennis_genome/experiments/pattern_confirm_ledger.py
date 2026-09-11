from __future__ import annotations

import argparse
import json
from pathlib import Path

from tennis_genome.experiments.pattern_confirm import (
    FrozenMarketCoreFit,
    ProspectiveRecord,
    _load_jsonl,
    _parse_aware_datetime,
    _write_jsonl,
    log_prospective_rows,
    prospective_record_as_dict,
    verify_fit_payload,
    verify_prospective_record,
)


def append_prospective_rows(
    existing_rows: list[dict[str, object]],
    new_raw_rows: list[dict[str, object]],
    *,
    fit: FrozenMarketCoreFit,
) -> list[ProspectiveRecord]:
    """Verify an existing ledger and add a new outcome-free pre-match batch.

    Existing rows are never trusted merely because they came from an earlier
    file: every row digest is re-verified, the frozen fit hash must agree, and
    duplicate canonical match IDs across old/new batches fail closed.
    """
    existing = [verify_prospective_record(row) for row in existing_rows]
    if any(row.market_core_fit_sha256 != fit.artifact_sha256 for row in existing):
        raise ValueError("existing prospective ledger uses a different frozen fit")

    existing_ids = [row.match_id for row in existing]
    if len(existing_ids) != len(set(existing_ids)):
        raise ValueError("existing prospective ledger contains duplicate match_id values")

    new = log_prospective_rows(new_raw_rows, fit=fit)
    new_ids = {row.match_id for row in new}
    overlap = sorted(set(existing_ids).intersection(new_ids))
    if overlap:
        raise ValueError(
            "prospective append would duplicate match_id values: " + ", ".join(overlap[:10])
        )

    combined = [*existing, *new]
    return sorted(
        combined,
        key=lambda row: (_parse_aware_datetime(row.scheduled_start), row.match_id),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Append an outcome-free batch to the PATTERN-CONFIRM-001 ledger"
    )
    parser.add_argument("--fit", required=True, type=Path)
    parser.add_argument("--existing", required=True, type=Path)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    fit_payload = json.loads(args.fit.read_text())
    if not isinstance(fit_payload, dict):
        raise ValueError("frozen fit must be a JSON object")
    fit = verify_fit_payload(fit_payload)

    existing_rows = _load_jsonl(args.existing) if args.existing.exists() else []
    new_raw_rows = _load_jsonl(args.input)
    combined = append_prospective_rows(existing_rows, new_raw_rows, fit=fit)
    _write_jsonl(
        args.output,
        [prospective_record_as_dict(record) for record in combined],
    )


if __name__ == "__main__":
    main()
