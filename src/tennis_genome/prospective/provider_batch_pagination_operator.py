from __future__ import annotations

import argparse
import json
from datetime import UTC, date, datetime
from pathlib import Path

from tennis_genome.prospective.provider_batch import ProviderBatchStore
from tennis_genome.prospective.provider_batch_operator import build_anchor_dispatch_packet
from tennis_genome.prospective.provider_batch_pagination import (
    capture_paginated_provider_batch,
    verify_paginated_provider_batches,
)


def _parse_time(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("observed_at must be timezone-aware")
    return parsed.astimezone(UTC)


def capture_pages_and_build_anchor_packet(
    *,
    store: ProviderBatchStore,
    page_pairs: list[tuple[Path, Path]],
    schedule_date: date,
    observed_at: datetime,
) -> dict[str, object]:
    if schedule_date != observed_at.astimezone(UTC).date():
        raise ValueError("schedule_date must equal observed_at UTC date")
    record = capture_paginated_provider_batch(
        store=store,
        page_pairs=page_pairs,
        schedule_date=schedule_date,
        observed_at=observed_at,
    )
    pagination = verify_paginated_provider_batches(store)
    packet = build_anchor_dispatch_packet(
        store=store,
        record_sha256=str(record["record_sha256"]),
    )
    return {
        "provider_batch_record_sha256": record["record_sha256"],
        "pagination": pagination,
        "anchor_packet": packet,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture a complete paginated Sportradar Daily Summaries batch"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    capture = subparsers.add_parser(
        "capture",
        help="verify all retained pages, capture one daily batch, emit anchor packet",
    )
    capture.add_argument("--store", required=True, type=Path)
    capture.add_argument("--schedule-date", required=True)
    capture.add_argument("--observed-at", required=True)
    capture.add_argument(
        "--page",
        action="append",
        nargs=2,
        metavar=("PAYLOAD_JSON", "HEADERS_TXT"),
        required=True,
        help="repeat once per Sportradar page in any order",
    )
    capture.add_argument("--output", type=Path)

    verify = subparsers.add_parser(
        "verify",
        help="verify base provider ledger plus retained pagination evidence",
    )
    verify.add_argument("--store", required=True, type=Path)
    return parser.parse_args()


def _emit(payload: dict[str, object], output: Path | None) -> None:
    rendered = json.dumps(
        payload,
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
    ) + "\n"
    if output is None:
        print(rendered, end="")
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")


def main() -> None:
    args = _parse_args()
    store = ProviderBatchStore(args.store)
    if args.command == "capture":
        page_pairs = [(Path(raw), Path(headers)) for raw, headers in args.page]
        result = capture_pages_and_build_anchor_packet(
            store=store,
            page_pairs=page_pairs,
            schedule_date=date.fromisoformat(args.schedule_date),
            observed_at=_parse_time(args.observed_at),
        )
        _emit(result, args.output)
        return
    if args.command == "verify":
        _emit(verify_paginated_provider_batches(store), None)
        return
    raise AssertionError(f"unsupported command: {args.command}")


if __name__ == "__main__":
    main()
