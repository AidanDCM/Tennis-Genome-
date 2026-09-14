from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from tennis_genome.prospective.census import EventCensusStore
from tennis_genome.prospective.provider_batch import (
    ProviderBatchStore,
    reconcile_batches_with_census,
)

ANCHOR_LEDGER_VERSION = "FULL-STACK-FORWARD-001-provider-batch-anchor-v1"
ANCHOR_SCHEMA = "full-stack-forward-provider-batch-github-anchor-v1"
CADENCE_VERSION = "FULL-STACK-FORWARD-001-provider-cadence-v1"
ANCHOR_REPOSITORY = "AidanDCM/Tennis-Genome-"
ANCHOR_WORKFLOW_PATH = ".github/workflows/provider_batch_anchor.yml"
CAPTURE_SLOT_HOURS_UTC = (0, 6, 12, 18)
CAPTURE_WINDOW = timedelta(hours=1)
CLOCK_SKEW_TOLERANCE = timedelta(minutes=5)
_ZERO_SHA256 = "0" * 64
_PROVIDER = "SPORTRADAR"
_CENSUS_REQUIRED = "CENSUS_REQUIRED"


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _pretty_json(value: object) -> bytes:
    return (
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _record_sha256(record_without_sha: dict[str, object]) -> str:
    return _sha256_bytes(_canonical_json(record_without_sha))


def _parse_time(value: object, *, field: str) -> datetime:
    text = str(value).strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO-8601 datetime") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return parsed.astimezone(UTC)


def _json_object_bytes(payload: bytes, *, label: str) -> dict[str, object]:
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} must be UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _required_text(raw: dict[str, object], field: str) -> str:
    value = str(raw.get(field, "")).strip()
    if not value:
        raise ValueError(f"{field} must be non-empty")
    return value


def _fsync_directory(path: Path) -> None:
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temp.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)
    _fsync_directory(path.parent)


def _find_batch_record(
    batch_store: ProviderBatchStore,
    record_sha256: str,
) -> dict[str, object]:
    matches = [
        record
        for record in batch_store.records()
        if str(record.get("record_sha256", "")) == record_sha256
    ]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one provider-batch record {record_sha256}")
    return matches[0]


def _verify_anchor_payloads(
    batch_record: dict[str, object],
    receipt: dict[str, object],
    run: dict[str, object],
) -> datetime:
    if receipt.get("schema_version") != ANCHOR_SCHEMA:
        raise ValueError("provider-batch anchor receipt schema is not supported")
    if receipt.get("provider") != "GITHUB_ACTIONS":
        raise ValueError("provider-batch anchor receipt provider is not GitHub Actions")
    if receipt.get("repository") != ANCHOR_REPOSITORY:
        raise ValueError("provider-batch anchor repository differs from frozen repository")

    batch_sha = str(batch_record["record_sha256"])
    expected_receipt = {
        "batch_record_sha256": batch_sha,
        "batch_chain_head_sha256": batch_sha,
        "schedule_date": batch_record["schedule_date"],
        "observed_at": batch_record["observed_at"],
        "raw_payload_sha256": batch_record["raw_payload_sha256"],
        "manifest_sha256": batch_record["manifest_sha256"],
    }
    for field, expected in expected_receipt.items():
        if receipt.get(field) != expected:
            raise ValueError(f"provider-batch anchor receipt {field} mismatch")

    repository = run.get("repository")
    if not isinstance(repository, dict) or repository.get("full_name") != ANCHOR_REPOSITORY:
        raise ValueError("GitHub run metadata repository does not match frozen repository")
    if int(run.get("id", -1)) != int(receipt.get("workflow_run_id", -2)):
        raise ValueError("provider-batch anchor receipt run ID differs from GitHub metadata")
    if run.get("event") != "workflow_dispatch":
        raise ValueError("provider-batch anchor run was not workflow_dispatch")
    if run.get("status") != "completed" or run.get("conclusion") != "success":
        raise ValueError("provider-batch anchor workflow did not complete successfully")
    if run.get("path") != ANCHOR_WORKFLOW_PATH:
        raise ValueError("GitHub run metadata is not the provider-batch anchor workflow")
    if run.get("head_branch") != "main":
        raise ValueError("provider-batch anchor workflow must run from main")
    if run.get("head_sha") != receipt.get("workflow_source_sha"):
        raise ValueError("provider-batch anchor workflow source SHA mismatch")

    anchor_created = _parse_time(run.get("created_at"), field="anchor.created_at")
    observed_at = _parse_time(batch_record.get("observed_at"), field="batch.observed_at")
    _parse_time(
        receipt.get("runner_receipt_created_at_utc"),
        field="anchor.runner_receipt_created_at_utc",
    )
    if anchor_created < observed_at - CLOCK_SKEW_TOLERANCE:
        raise ValueError("provider-batch anchor materially predates local observation time")
    if anchor_created > observed_at + CAPTURE_WINDOW:
        raise ValueError("provider-batch anchor was created more than one hour after observation")
    return anchor_created


class ProviderBatchAnchorStore:
    """Append-only local attestations of externally timestamped provider-batch anchors."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.records_dir = root / "records"
        self.evidence_dir = root / "evidence"
        self.lock_path = root / ".write.lock"
        self.records_dir.mkdir(parents=True, exist_ok=True)
        self.evidence_dir.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def write_lock(self) -> Iterator[None]:
        self.root.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise RuntimeError(
                "provider-batch anchor store is locked; confirm no writer is active"
            ) from exc
        try:
            os.write(fd, f"{os.getpid()}\n".encode("ascii"))
            os.fsync(fd)
            yield
        finally:
            os.close(fd)
            self.lock_path.unlink(missing_ok=True)
            _fsync_directory(self.root)

    def _record_paths(self) -> list[Path]:
        return sorted(self.records_dir.glob("*.json"))

    def records(self) -> list[dict[str, object]]:
        result: list[dict[str, object]] = []
        for path in self._record_paths():
            value = _json_object_bytes(path.read_bytes(), label="provider-batch anchor record")
            result.append(value)
        return result

    def _store_evidence_bytes(self, payload: bytes) -> str:
        digest = _sha256_bytes(payload)
        path = self.evidence_dir / digest
        if path.exists():
            if path.read_bytes() != payload:
                raise RuntimeError(f"provider-batch anchor evidence collision: {digest}")
            return digest
        _atomic_write(path, payload)
        return digest

    def _append_record(self, payload: dict[str, object]) -> dict[str, object]:
        records = self.records()
        sequence = len(records) + 1
        previous = _ZERO_SHA256 if not records else str(records[-1]["record_sha256"])
        unsigned = dict(payload)
        forbidden = {"sequence", "previous_record_sha256", "record_sha256"}.intersection(
            unsigned
        )
        if forbidden:
            raise ValueError(f"anchor record payload contains reserved fields: {sorted(forbidden)}")
        unsigned["anchor_ledger_version"] = ANCHOR_LEDGER_VERSION
        unsigned["sequence"] = sequence
        unsigned["previous_record_sha256"] = previous
        digest = _record_sha256(unsigned)
        record = dict(unsigned)
        record["record_sha256"] = digest
        filename = f"{sequence:08d}-{digest}.json"
        _atomic_write(self.records_dir / filename, _pretty_json(record))
        return record

    def verify(self, *, batch_store: ProviderBatchStore) -> dict[str, object]:
        batch_store.verify()
        paths = self._record_paths()
        records = self.records()
        previous = _ZERO_SHA256
        anchored_batches: set[str] = set()

        for sequence, record in enumerate(records, start=1):
            if record.get("anchor_ledger_version") != ANCHOR_LEDGER_VERSION:
                raise ValueError(f"unexpected anchor-ledger version at sequence {sequence}")
            if record.get("record_type") != "BATCH_ANCHOR_ATTESTATION":
                raise ValueError(f"unexpected anchor record type at sequence {sequence}")
            if int(record.get("sequence", -1)) != sequence:
                raise ValueError(f"provider-batch anchor sequence gap at {sequence}")
            observed_sha = str(record.get("record_sha256", ""))
            unsigned = dict(record)
            unsigned.pop("record_sha256", None)
            if _record_sha256(unsigned) != observed_sha:
                raise ValueError(f"provider-batch anchor digest mismatch at sequence {sequence}")
            if record.get("previous_record_sha256") != previous:
                raise ValueError(f"provider-batch anchor chain mismatch at sequence {sequence}")
            expected_name = f"{sequence:08d}-{observed_sha}.json"
            if paths[sequence - 1].name != expected_name:
                raise ValueError(f"provider-batch anchor filename mismatch at sequence {sequence}")

            batch_sha = _required_text(record, "batch_record_sha256")
            if batch_sha in anchored_batches:
                raise ValueError(f"provider batch anchored more than once: {batch_sha}")
            batch_record = _find_batch_record(batch_store, batch_sha)

            evidence = record.get("evidence_sha256")
            receipt_sha = _required_text(record, "anchor_receipt_sha256")
            run_sha = _required_text(record, "github_run_metadata_sha256")
            if evidence != [receipt_sha, run_sha]:
                raise ValueError("provider-batch anchor evidence manifest mismatch")
            for digest in (receipt_sha, run_sha):
                path = self.evidence_dir / digest
                if len(digest) != 64 or not path.is_file():
                    raise ValueError(f"missing provider-batch anchor evidence {digest}")
                if _sha256_file(path) != digest:
                    raise ValueError(f"provider-batch anchor evidence digest mismatch: {digest}")

            receipt = _json_object_bytes(
                (self.evidence_dir / receipt_sha).read_bytes(),
                label="provider-batch anchor receipt",
            )
            run = _json_object_bytes(
                (self.evidence_dir / run_sha).read_bytes(),
                label="provider-batch GitHub run metadata",
            )
            created_at = _verify_anchor_payloads(batch_record, receipt, run)
            if record.get("anchor_created_at") != created_at.isoformat():
                raise ValueError("provider-batch anchor created_at does not reproduce")
            if int(record.get("workflow_run_id", -1)) != int(run["id"]):
                raise ValueError("provider-batch workflow run ID does not reproduce")
            if record.get("schedule_date") != batch_record.get("schedule_date"):
                raise ValueError("provider-batch anchor schedule_date does not reproduce")
            anchored_batches.add(batch_sha)
            previous = observed_sha

        return {
            "anchor_ledger_version": ANCHOR_LEDGER_VERSION,
            "record_count": len(records),
            "anchor_count": len(anchored_batches),
            "chain_head_sha256": previous,
            "status": "VERIFIED",
        }


def attest_batch_anchor(
    *,
    store: ProviderBatchAnchorStore,
    batch_store: ProviderBatchStore,
    batch_record_sha256: str,
    anchor_receipt_path: Path,
    github_run_metadata_path: Path,
) -> dict[str, object]:
    with store.write_lock():
        store.verify(batch_store=batch_store)
        batch_record = _find_batch_record(batch_store, batch_record_sha256)
        if any(
            record.get("batch_record_sha256") == batch_record_sha256
            for record in store.records()
        ):
            raise ValueError("provider batch already has an anchor attestation")

        receipt_payload = anchor_receipt_path.read_bytes()
        run_payload = github_run_metadata_path.read_bytes()
        receipt = _json_object_bytes(receipt_payload, label="provider-batch anchor receipt")
        run = _json_object_bytes(run_payload, label="provider-batch GitHub run metadata")
        created_at = _verify_anchor_payloads(batch_record, receipt, run)
        receipt_sha = store._store_evidence_bytes(receipt_payload)
        run_sha = store._store_evidence_bytes(run_payload)
        return store._append_record(
            {
                "record_type": "BATCH_ANCHOR_ATTESTATION",
                "batch_record_sha256": batch_record_sha256,
                "schedule_date": batch_record["schedule_date"],
                "anchor_created_at": created_at.isoformat(),
                "workflow_run_id": int(run["id"]),
                "anchor_receipt_sha256": receipt_sha,
                "github_run_metadata_sha256": run_sha,
                "evidence_sha256": [receipt_sha, run_sha],
            }
        )


def _coverage_start_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("coverage_start must be timezone-aware")
    value = value.astimezone(UTC)
    if (
        value.hour not in CAPTURE_SLOT_HOURS_UTC
        or value.minute != 0
        or value.second != 0
        or value.microsecond != 0
    ):
        raise ValueError("coverage_start must be exactly 00:00, 06:00, 12:00, or 18:00 UTC")
    return value


def _complete_through_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("complete_through must be timezone-aware")
    return value.astimezone(UTC)


def _due_slots(coverage_start: datetime, complete_through: datetime) -> list[datetime]:
    start = _coverage_start_utc(coverage_start)
    end = _complete_through_utc(complete_through)
    if end < start:
        raise ValueError("complete_through cannot precede coverage_start")
    slots: list[datetime] = []
    current = start
    while current + CAPTURE_WINDOW <= end:
        slots.append(current)
        current += timedelta(hours=6)
    return slots


def _anchor_by_batch(
    *,
    anchor_store: ProviderBatchAnchorStore,
    batch_store: ProviderBatchStore,
) -> dict[str, dict[str, object]]:
    anchor_store.verify(batch_store=batch_store)
    return {
        str(record["batch_record_sha256"]): record
        for record in anchor_store.records()
    }


def verify_capture_cadence(
    *,
    batch_store: ProviderBatchStore,
    anchor_store: ProviderBatchAnchorStore,
    coverage_start: datetime,
    complete_through: datetime,
) -> dict[str, object]:
    batch_store.verify()
    anchor_report = anchor_store.verify(batch_store=batch_store)
    anchors = _anchor_by_batch(anchor_store=anchor_store, batch_store=batch_store)
    slots = _due_slots(coverage_start, complete_through)
    batch_records = batch_store.records()
    missing: list[str] = []
    covered: list[str] = []

    for slot in slots:
        window_end = slot + CAPTURE_WINDOW
        required_dates = (slot.date(), slot.date() + timedelta(days=1))
        for schedule_date in required_dates:
            matches: list[str] = []
            for batch in batch_records:
                if batch.get("schedule_date") != schedule_date.isoformat():
                    continue
                batch_sha = str(batch["record_sha256"])
                anchor = anchors.get(batch_sha)
                if anchor is None:
                    continue
                observed = _parse_time(batch["observed_at"], field="batch.observed_at")
                anchor_created = _parse_time(
                    anchor["anchor_created_at"],
                    field="anchor.anchor_created_at",
                )
                if slot <= observed <= window_end and slot <= anchor_created <= window_end:
                    matches.append(batch_sha)
            key = f"{slot.isoformat()}::{schedule_date.isoformat()}"
            if not matches:
                missing.append(key)
            else:
                covered.append(key)

    if missing:
        raise ValueError(
            "provider capture cadence has missing anchored slot/date coverage: "
            + ", ".join(missing)
        )

    return {
        "cadence_version": CADENCE_VERSION,
        "coverage_start": _coverage_start_utc(coverage_start).isoformat(),
        "complete_through": _complete_through_utc(complete_through).isoformat(),
        "slot_hours_utc": list(CAPTURE_SLOT_HOURS_UTC),
        "capture_window_minutes": int(CAPTURE_WINDOW.total_seconds() // 60),
        "due_slot_count": len(slots),
        "required_slot_date_count": len(slots) * 2,
        "covered_slot_date_count": len(covered),
        "anchor_count": anchor_report["anchor_count"],
        "status": "CADENCE_COMPLETE",
    }


def _manifest_events(
    *,
    batch_store: ProviderBatchStore,
    batch_record: dict[str, object],
) -> list[dict[str, object]]:
    manifest_sha = _required_text(batch_record, "manifest_sha256")
    manifest = _json_object_bytes(
        (batch_store.evidence_dir / manifest_sha).read_bytes(),
        label="provider batch manifest",
    )
    raw_events = manifest.get("events")
    if not isinstance(raw_events, list):
        raise ValueError("provider batch manifest events must be an array")
    events: list[dict[str, object]] = []
    for raw in raw_events:
        if not isinstance(raw, dict):
            raise ValueError("provider batch manifest contains a non-object event")
        events.append(raw)
    return events


def reconcile_anchored_batches_with_census(
    *,
    batch_store: ProviderBatchStore,
    anchor_store: ProviderBatchAnchorStore,
    census_store: EventCensusStore,
    coverage_start: datetime,
    complete_through: datetime,
) -> dict[str, object]:
    cadence = verify_capture_cadence(
        batch_store=batch_store,
        anchor_store=anchor_store,
        coverage_start=coverage_start,
        complete_through=complete_through,
    )
    base = reconcile_batches_with_census(
        batch_store=batch_store,
        census_store=census_store,
        complete_through=complete_through,
    )
    cutoff = _complete_through_utc(complete_through)
    anchors = _anchor_by_batch(anchor_store=anchor_store, batch_store=batch_store)
    required_due: dict[str, list[bool]] = {}

    for batch in batch_store.records():
        batch_sha = str(batch["record_sha256"])
        anchor = anchors.get(batch_sha)
        anchor_created = (
            None
            if anchor is None
            else _parse_time(anchor["anchor_created_at"], field="anchor.anchor_created_at")
        )
        for event in _manifest_events(batch_store=batch_store, batch_record=batch):
            if event.get("classification") != _CENSUS_REQUIRED:
                continue
            start = _parse_time(event.get("scheduled_start"), field="event.scheduled_start")
            if start > cutoff:
                continue
            event_key = f"{_PROVIDER}:{_required_text(event, 'provider_event_id')}"
            externally_prestart = anchor_created is not None and anchor_created < start
            required_due.setdefault(event_key, []).append(externally_prestart)

    untrusted = sorted(
        event_key for event_key, statuses in required_due.items() if not any(statuses)
    )
    if untrusted:
        raise ValueError(
            "due provider events lack an externally timestamped pre-start batch: "
            + ", ".join(untrusted)
        )

    return {
        "cadence_version": CADENCE_VERSION,
        "batch_chain_head_sha256": base["batch_chain_head_sha256"],
        "census_chain_head_sha256": base["census_chain_head_sha256"],
        "anchor_chain_head_sha256": anchor_store.verify(batch_store=batch_store)[
            "chain_head_sha256"
        ],
        "required_event_count": base["required_event_count"],
        "reconciled_event_count": base["reconciled_event_count"],
        "due_slot_count": cadence["due_slot_count"],
        "covered_slot_date_count": cadence["covered_slot_date_count"],
        "status": "ANCHORED_RECONCILED",
    }
