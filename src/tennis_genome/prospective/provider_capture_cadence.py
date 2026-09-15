from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

from tennis_genome.prospective.provider_batch import BATCH_VERSION, ProviderBatchStore
from tennis_genome.prospective.provider_batch_pagination import (
    PAGINATION_SCHEMA,
    verify_paginated_provider_batches,
)

CADENCE_VERSION = "FULL-STACK-FORWARD-001-provider-capture-cadence-v2"
ANCHOR_SCHEMA = "full-stack-forward-provider-batch-github-anchor-v1"
_ANCHOR_REPOSITORY = "AidanDCM/Tennis-Genome-"
_ANCHOR_WORKFLOW_PATH = ".github/workflows/prospective_provider_batch_anchor.yml"
_ZERO_SHA256 = "0" * 64
_MAX_ANCHOR_LAG = timedelta(minutes=30)
_MAX_CADENCE_GAP = timedelta(hours=7)


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


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def _required_text(raw: dict[str, object], field: str) -> str:
    value = str(raw.get(field, "")).strip()
    if not value:
        raise ValueError(f"{field} must be non-empty")
    return value


def _json_object(path: Path, *, label: str) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} must be UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _record_sha256(record_without_sha: dict[str, object]) -> str:
    return _sha256_bytes(_canonical_json(record_without_sha))


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
    batch_record_sha256: str,
) -> dict[str, object]:
    matches = [
        record
        for record in batch_store.records()
        if str(record.get("record_sha256", "")) == batch_record_sha256
    ]
    if len(matches) != 1:
        raise ValueError(
            f"expected exactly one provider-batch record {batch_record_sha256}"
        )
    return matches[0]


def _provider_generation_bounds(batch_record: dict[str, object]) -> tuple[datetime, datetime]:
    if batch_record.get("pagination_schema") != PAGINATION_SCHEMA:
        raise ValueError(
            "provider-capture cadence requires complete Sportradar pagination-v2 evidence"
        )
    earliest = _parse_time(
        batch_record.get("provider_generated_at_min"),
        field="provider_batch.provider_generated_at_min",
    )
    latest = _parse_time(
        batch_record.get("provider_generated_at_max"),
        field="provider_batch.provider_generated_at_max",
    )
    if earliest > latest:
        raise ValueError("provider batch generated_at bounds are inverted")
    return earliest, latest


def _verify_anchor_payloads(
    *,
    batch_record: dict[str, object],
    receipt: dict[str, object],
    run: dict[str, object],
) -> datetime:
    if receipt.get("schema_version") != ANCHOR_SCHEMA:
        raise ValueError("provider-batch anchor receipt schema is not supported")
    if receipt.get("provider") != "GITHUB_ACTIONS":
        raise ValueError("provider-batch anchor provider is not GitHub Actions")
    if receipt.get("repository") != _ANCHOR_REPOSITORY:
        raise ValueError("provider-batch anchor repository differs from frozen repository")

    provider_min, provider_max = _provider_generation_bounds(batch_record)
    batch_sha = _required_text(batch_record, "record_sha256")
    if receipt.get("batch_record_sha256") != batch_sha:
        raise ValueError("provider-batch anchor record SHA does not match batch record")
    if receipt.get("batch_chain_head_sha256") != batch_sha:
        raise ValueError("provider-batch anchor must attest the batch as immediate chain head")
    for field in (
        "schedule_date",
        "raw_payload_sha256",
        "manifest_sha256",
        "observed_at",
    ):
        if receipt.get(field) != batch_record.get(field):
            raise ValueError(f"provider-batch anchor {field} differs from batch record")

    repository = run.get("repository")
    if not isinstance(repository, dict) or repository.get("full_name") != _ANCHOR_REPOSITORY:
        raise ValueError("GitHub run metadata repository does not match frozen repository")
    if int(run.get("id", -1)) != int(receipt.get("workflow_run_id", -2)):
        raise ValueError("provider-batch anchor run ID differs from GitHub run metadata")
    if run.get("event") != "workflow_dispatch":
        raise ValueError("provider-batch anchor was not triggered by workflow_dispatch")
    if run.get("status") != "completed" or run.get("conclusion") != "success":
        raise ValueError("provider-batch anchor workflow did not complete successfully")
    if run.get("path") != _ANCHOR_WORKFLOW_PATH:
        raise ValueError("GitHub run metadata is not the provider-batch anchor workflow")
    if run.get("head_sha") != receipt.get("workflow_source_sha"):
        raise ValueError("provider-batch anchor workflow source SHA differs from run metadata")

    anchor_created_at = _parse_time(
        _required_text(run, "created_at"),
        field="provider_batch_anchor.created_at",
    )
    observed_at = _parse_time(
        batch_record.get("observed_at"),
        field="provider_batch.observed_at",
    )
    runner_created_at = _parse_time(
        _required_text(receipt, "runner_receipt_created_at_utc"),
        field="provider_batch_anchor.runner_receipt_created_at_utc",
    )
    if anchor_created_at < provider_max:
        raise ValueError("provider-batch anchor predates newest retained provider generation")
    if anchor_created_at - provider_min > _MAX_ANCHOR_LAG:
        raise ValueError(
            "provider-batch anchor was created too long after earliest retained provider generation"
        )
    if anchor_created_at < observed_at:
        raise ValueError("provider-batch anchor predates the retained provider observation")
    if anchor_created_at - observed_at > _MAX_ANCHOR_LAG:
        raise ValueError("provider-batch anchor was created too long after provider observation")
    if runner_created_at < anchor_created_at:
        raise ValueError("provider-batch runner receipt predates GitHub workflow creation")

    schedule_date = str(batch_record.get("schedule_date"))
    if schedule_date != observed_at.date().isoformat():
        raise ValueError("cadence batch schedule_date must equal provider observation UTC date")
    if schedule_date != provider_min.date().isoformat() or schedule_date != provider_max.date().isoformat():
        raise ValueError("cadence batch schedule_date must equal provider generation UTC date")
    return anchor_created_at


class ProviderCaptureCadenceStore:
    """Append-only GitHub attestations for retained provider-batch captures."""

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
                "provider-capture cadence store is locked; confirm no writer is active"
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
        records: list[dict[str, object]] = []
        for path in self._record_paths():
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError(f"cadence record is not an object: {path.name}")
            records.append(payload)
        return records

    def _store_evidence(self, payload: bytes) -> str:
        digest = _sha256_bytes(payload)
        target = self.evidence_dir / digest
        if target.exists():
            if target.read_bytes() != payload:
                raise RuntimeError(f"cadence evidence hash collision: {digest}")
            return digest
        _atomic_write(target, payload)
        return digest

    def _append_record(self, payload: dict[str, object]) -> dict[str, object]:
        records = self.records()
        previous = _ZERO_SHA256 if not records else str(records[-1]["record_sha256"])
        unsigned = dict(payload)
        unsigned["cadence_version"] = CADENCE_VERSION
        unsigned["sequence"] = len(records) + 1
        unsigned["previous_record_sha256"] = previous
        digest = _record_sha256(unsigned)
        record = dict(unsigned)
        record["record_sha256"] = digest
        name = f"{len(records) + 1:08d}-{digest}.json"
        _atomic_write(self.records_dir / name, _pretty_json(record))
        return record

    def verify(self, *, batch_store: ProviderBatchStore) -> dict[str, object]:
        batch_store.verify()
        verify_paginated_provider_batches(batch_store)
        paths = self._record_paths()
        records = self.records()
        previous = _ZERO_SHA256
        batch_shas: set[str] = set()
        workflow_run_ids: set[int] = set()
        anchor_times: list[datetime] = []

        for sequence, record in enumerate(records, start=1):
            if record.get("cadence_version") != CADENCE_VERSION:
                raise ValueError(f"unexpected cadence version at sequence {sequence}")
            if record.get("record_type") != "PROVIDER_BATCH_ATTESTATION":
                raise ValueError(f"unexpected cadence record type at sequence {sequence}")
            if int(record.get("sequence", -1)) != sequence:
                raise ValueError(f"provider-capture cadence sequence gap at {sequence}")
            observed_sha = str(record.get("record_sha256", ""))
            unsigned = dict(record)
            unsigned.pop("record_sha256", None)
            if _record_sha256(unsigned) != observed_sha:
                raise ValueError(f"cadence record digest mismatch at sequence {sequence}")
            if record.get("previous_record_sha256") != previous:
                raise ValueError(f"cadence hash chain mismatch at sequence {sequence}")
            if paths[sequence - 1].name != f"{sequence:08d}-{observed_sha}.json":
                raise ValueError(f"cadence filename mismatch at sequence {sequence}")

            receipt_sha = _required_text(record, "anchor_receipt_sha256")
            run_sha = _required_text(record, "workflow_run_metadata_sha256")
            if record.get("evidence_sha256") != [receipt_sha, run_sha]:
                raise ValueError("cadence evidence manifest mismatch")
            for digest in (receipt_sha, run_sha):
                evidence_path = self.evidence_dir / digest
                if len(digest) != 64 or not evidence_path.is_file():
                    raise ValueError(f"missing cadence evidence {digest}")
                if _sha256_file(evidence_path) != digest:
                    raise ValueError(f"cadence evidence digest mismatch: {digest}")

            receipt = _json_object(
                self.evidence_dir / receipt_sha,
                label="provider-batch anchor receipt",
            )
            run = _json_object(
                self.evidence_dir / run_sha,
                label="provider-batch anchor workflow metadata",
            )
            batch_sha = _required_text(record, "batch_record_sha256")
            batch_record = _find_batch_record(batch_store, batch_sha)
            provider_min, provider_max = _provider_generation_bounds(batch_record)
            anchor_created_at = _verify_anchor_payloads(
                batch_record=batch_record,
                receipt=receipt,
                run=run,
            )
            if record.get("batch_version") != BATCH_VERSION:
                raise ValueError("cadence record batch version mismatch")
            if record.get("pagination_schema") != PAGINATION_SCHEMA:
                raise ValueError("cadence record pagination schema mismatch")
            if record.get("schedule_date") != batch_record.get("schedule_date"):
                raise ValueError("cadence schedule_date does not reproduce from batch")
            if record.get("batch_observed_at") != batch_record.get("observed_at"):
                raise ValueError("cadence observed_at does not reproduce from batch")
            if record.get("provider_generated_at_min") != provider_min.isoformat():
                raise ValueError("cadence provider min generated_at does not reproduce from batch")
            if record.get("provider_generated_at_max") != provider_max.isoformat():
                raise ValueError("cadence provider max generated_at does not reproduce from batch")
            if record.get("anchor_created_at") != anchor_created_at.isoformat():
                raise ValueError(
                    "cadence anchor_created_at does not reproduce from GitHub evidence"
                )

            if batch_sha in batch_shas:
                raise ValueError("provider batch has more than one cadence attestation")
            batch_shas.add(batch_sha)
            run_id = int(receipt["workflow_run_id"])
            if run_id in workflow_run_ids:
                raise ValueError("GitHub workflow run is reused across cadence attestations")
            workflow_run_ids.add(run_id)
            anchor_times.append(anchor_created_at)
            previous = observed_sha

        return {
            "cadence_version": CADENCE_VERSION,
            "record_count": len(records),
            "attested_batch_count": len(batch_shas),
            "first_anchor_created_at": (
                min(anchor_times).isoformat() if anchor_times else None
            ),
            "last_anchor_created_at": (
                max(anchor_times).isoformat() if anchor_times else None
            ),
            "chain_head_sha256": previous,
            "status": "VERIFIED",
        }


def attest_provider_batch(
    *,
    batch_store: ProviderBatchStore,
    cadence_store: ProviderCaptureCadenceStore,
    anchor_receipt_path: Path,
    workflow_run_metadata_path: Path,
) -> dict[str, object]:
    with cadence_store.write_lock():
        cadence_store.verify(batch_store=batch_store)
        receipt_bytes = anchor_receipt_path.read_bytes()
        run_bytes = workflow_run_metadata_path.read_bytes()
        receipt = _json_object(anchor_receipt_path, label="provider-batch anchor receipt")
        run = _json_object(
            workflow_run_metadata_path,
            label="provider-batch anchor workflow metadata",
        )
        batch_sha = _required_text(receipt, "batch_record_sha256")
        batch_record = _find_batch_record(batch_store, batch_sha)
        provider_min, provider_max = _provider_generation_bounds(batch_record)
        anchor_created_at = _verify_anchor_payloads(
            batch_record=batch_record,
            receipt=receipt,
            run=run,
        )
        receipt_sha = cadence_store._store_evidence(receipt_bytes)
        run_sha = cadence_store._store_evidence(run_bytes)
        return cadence_store._append_record(
            {
                "record_type": "PROVIDER_BATCH_ATTESTATION",
                "batch_version": BATCH_VERSION,
                "pagination_schema": PAGINATION_SCHEMA,
                "batch_record_sha256": batch_sha,
                "schedule_date": batch_record["schedule_date"],
                "batch_observed_at": batch_record["observed_at"],
                "provider_generated_at_min": provider_min.isoformat(),
                "provider_generated_at_max": provider_max.isoformat(),
                "anchor_created_at": anchor_created_at.isoformat(),
                "anchor_receipt_sha256": receipt_sha,
                "workflow_run_metadata_sha256": run_sha,
                "evidence_sha256": [receipt_sha, run_sha],
            }
        )


def verify_capture_cadence(
    *,
    batch_store: ProviderBatchStore,
    cadence_store: ProviderCaptureCadenceStore,
    complete_through: datetime,
) -> dict[str, object]:
    if complete_through.tzinfo is None or complete_through.utcoffset() is None:
        raise ValueError("complete_through must be timezone-aware")
    cutoff = complete_through.astimezone(UTC)
    batch_store.verify()
    verify_paginated_provider_batches(batch_store)
    cadence_store.verify(batch_store=batch_store)

    attestations = cadence_store.records()
    due_attestations = [
        record
        for record in attestations
        if _parse_time(record["anchor_created_at"], field="anchor_created_at") <= cutoff
    ]
    if not due_attestations:
        raise ValueError("capture cadence has no externally attested provider batch by cutoff")

    due_attestations.sort(
        key=lambda record: _parse_time(record["anchor_created_at"], field="anchor_created_at")
    )
    anchor_times = [
        _parse_time(record["anchor_created_at"], field="anchor_created_at")
        for record in due_attestations
    ]
    gaps = [
        later - earlier
        for earlier, later in zip(anchor_times, anchor_times[1:], strict=False)
    ]
    if any(gap > _MAX_CADENCE_GAP for gap in gaps):
        raise ValueError("provider capture cadence gap exceeds seven hours")
    if cutoff - anchor_times[-1] > _MAX_CADENCE_GAP:
        raise ValueError("provider capture cadence is stale at completeness cutoff")

    attested_batch_shas = {str(record["batch_record_sha256"]) for record in due_attestations}
    unanchored_due: list[str] = []
    for batch in batch_store.records():
        provider_generated_at = _parse_time(
            batch.get("provider_generated_at_max"),
            field="provider_batch.provider_generated_at_max",
        )
        if (
            provider_generated_at <= cutoff
            and str(batch["record_sha256"]) not in attested_batch_shas
        ):
            unanchored_due.append(str(batch["record_sha256"]))
    if unanchored_due:
        raise ValueError(
            "provider batches due by cutoff lack external cadence attestation: "
            + ", ".join(sorted(unanchored_due))
        )

    schedule_dates = {str(record["schedule_date"]) for record in due_attestations}
    first_anchor = anchor_times[0]
    current_date = first_anchor.date()
    required_dates: set[str] = set()
    while current_date <= cutoff.date():
        required_dates.add(current_date.isoformat())
        current_date += timedelta(days=1)
    missing_dates = sorted(required_dates - schedule_dates)
    if missing_dates:
        raise ValueError(
            "provider capture cadence is missing UTC schedule dates: "
            + ", ".join(missing_dates)
        )

    max_gap_seconds = max((gap.total_seconds() for gap in gaps), default=0.0)
    return {
        "cadence_version": CADENCE_VERSION,
        "complete_through": cutoff.isoformat(),
        "first_anchor_created_at": first_anchor.isoformat(),
        "last_anchor_created_at": anchor_times[-1].isoformat(),
        "attested_batch_count": len(due_attestations),
        "covered_schedule_date_count": len(schedule_dates),
        "maximum_observed_anchor_gap_seconds": max_gap_seconds,
        "maximum_allowed_anchor_gap_seconds": _MAX_CADENCE_GAP.total_seconds(),
        "status": "CADENCE_VERIFIED",
    }
