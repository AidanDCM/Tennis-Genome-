from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path

from tennis_genome.prospective.provider_batch import (
    ProviderBatchStore,
    capture_provider_batch,
)

ANCHOR_PACKET_SCHEMA = "full-stack-forward-provider-batch-anchor-packet-v1"
ANCHOR_REPOSITORY = "AidanDCM/Tennis-Genome-"
ANCHOR_WORKFLOW_PATH = ".github/workflows/prospective_provider_batch_anchor.yml"
ANCHOR_WORKFLOW_NAME = "Prospective Provider Batch Anchor"
ANCHOR_INPUT_FIELDS = (
    "batch_record_sha256",
    "batch_chain_head_sha256",
    "schedule_date",
    "raw_payload_sha256",
    "manifest_sha256",
    "observed_at",
)


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _pretty_json(value: object) -> str:
    return (
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    )


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise ValueError("schedule_date must be YYYY-MM-DD") from exc


def _parse_time(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError("observed_at must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("observed_at must be timezone-aware")
    return parsed.astimezone(UTC)


def _record_by_sha(
    store: ProviderBatchStore,
    record_sha256: str | None,
) -> dict[str, object]:
    records = store.records()
    if not records:
        raise ValueError("provider-batch store has no retained batch records")
    if record_sha256 is None:
        return records[-1]
    matches = [
        record
        for record in records
        if str(record.get("record_sha256", "")) == record_sha256
    ]
    if len(matches) != 1:
        raise ValueError("requested provider-batch record SHA was not found exactly once")
    return matches[0]


def build_anchor_dispatch_packet(
    *,
    store: ProviderBatchStore,
    record_sha256: str | None = None,
) -> dict[str, object]:
    """Build exact workflow inputs only for the current verified provider-batch head."""

    report = store.verify()
    record = _record_by_sha(store, record_sha256)
    record_sha = str(record.get("record_sha256", ""))
    chain_head = str(report.get("chain_head_sha256", ""))
    if record_sha != chain_head:
        raise ValueError(
            "provider-batch anchor packet may only attest the current chain-head record"
        )
    if record.get("record_type") != "PROVIDER_BATCH":
        raise ValueError("anchor packet requires a PROVIDER_BATCH record")
    if record.get("provider") != "SPORTRADAR":
        raise ValueError("anchor packet requires a Sportradar provider batch")

    schedule_date = _parse_date(str(record.get("schedule_date", "")))
    observed_at = _parse_time(str(record.get("observed_at", "")))
    if schedule_date != observed_at.date():
        raise ValueError("provider-batch schedule date must equal observed_at UTC date")

    inputs = {
        "batch_record_sha256": record_sha,
        "batch_chain_head_sha256": chain_head,
        "schedule_date": schedule_date.isoformat(),
        "raw_payload_sha256": str(record.get("raw_payload_sha256", "")),
        "manifest_sha256": str(record.get("manifest_sha256", "")),
        "observed_at": observed_at.isoformat(),
    }
    if tuple(inputs) != ANCHOR_INPUT_FIELDS:
        raise AssertionError("provider-batch anchor input contract drifted")
    for field in (
        "batch_record_sha256",
        "batch_chain_head_sha256",
        "raw_payload_sha256",
        "manifest_sha256",
    ):
        value = inputs[field]
        if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
            raise ValueError(f"{field} must be lowercase SHA-256")

    packet_core = {
        "schema_version": ANCHOR_PACKET_SCHEMA,
        "repository": ANCHOR_REPOSITORY,
        "workflow_name": ANCHOR_WORKFLOW_NAME,
        "workflow_path": ANCHOR_WORKFLOW_PATH,
        "record_sequence": int(record["sequence"]),
        "inputs": inputs,
    }
    return {
        **packet_core,
        "packet_sha256": hashlib.sha256(_canonical_json(packet_core)).hexdigest(),
    }


def capture_batch_and_build_anchor_packet(
    *,
    store: ProviderBatchStore,
    raw_payload_path: Path,
    schedule_date: date,
    observed_at: datetime,
) -> tuple[dict[str, object], dict[str, object]]:
    """Capture one raw provider response and return its exact dispatch packet."""

    normalized_observed_at = observed_at.astimezone(UTC)
    if schedule_date != normalized_observed_at.date():
        raise ValueError("schedule_date must equal observed_at UTC date")
    record = capture_provider_batch(
        store=store,
        raw_payload_path=raw_payload_path,
        schedule_date=schedule_date,
        observed_at=normalized_observed_at,
    )
    packet = build_anchor_dispatch_packet(
        store=store,
        record_sha256=str(record["record_sha256"]),
    )
    return record, packet


def _write_or_print(payload: dict[str, object], output: Path | None) -> None:
    rendered = _pretty_json(payload)
    if output is None:
        print(rendered, end="")
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture and package FULL-STACK-FORWARD-001 provider batches"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    capture = subparsers.add_parser(
        "capture",
        help="retain one raw Sportradar batch and emit exact GitHub anchor inputs",
    )
    capture.add_argument("--store", required=True, type=Path)
    capture.add_argument("--raw-payload", required=True, type=Path)
    capture.add_argument("--schedule-date", required=True)
    capture.add_argument("--observed-at", required=True)
    capture.add_argument("--packet", type=Path)

    packet = subparsers.add_parser(
        "packet",
        help="rebuild anchor inputs for the current verified chain head",
    )
    packet.add_argument("--store", required=True, type=Path)
    packet.add_argument("--record-sha256")
    packet.add_argument("--output", type=Path)

    verify = subparsers.add_parser("verify", help="verify the provider-batch ledger")
    verify.add_argument("--store", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    store = ProviderBatchStore(args.store)
    if args.command == "capture":
        _, packet = capture_batch_and_build_anchor_packet(
            store=store,
            raw_payload_path=args.raw_payload,
            schedule_date=_parse_date(args.schedule_date),
            observed_at=_parse_time(args.observed_at),
        )
        _write_or_print(packet, args.packet)
        return
    if args.command == "packet":
        packet = build_anchor_dispatch_packet(
            store=store,
            record_sha256=args.record_sha256,
        )
        _write_or_print(packet, args.output)
        return
    if args.command == "verify":
        _write_or_print(store.verify(), None)
        return
    raise AssertionError(f"unsupported command: {args.command}")


if __name__ == "__main__":
    main()
