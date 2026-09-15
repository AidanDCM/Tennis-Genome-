from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

from tennis_genome.prospective.provider_batch import BATCH_VERSION, ProviderBatchStore
from tennis_genome.prospective.provider_batch_github_anchor import (
    GitHubGetBytes,
    LiveProviderBatchAnchorEvidence,
    fetch_live_anchor_evidence,
    verify_live_anchor_against_batch,
)
from tennis_genome.prospective.provider_batch_pagination import (
    PAGINATION_SCHEMA,
    verify_paginated_provider_batches,
)

LIVE_CADENCE_VERSION = "FULL-STACK-FORWARD-001-provider-capture-cadence-v3"
LIVE_EVIDENCE_MODE = "LIVE_GITHUB_LEDGER_V1"
_ZERO_SHA256 = "0" * 64
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


def _record_sha256(record_without_sha: dict[str, object]) -> str:
    return _sha256_bytes(_canonical_json(record_without_sha))


def _parse_time(value: object, *, field: str) -> datetime:
    text = str(value if value is not None else "").strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return parsed.astimezone(UTC)


def _required_text(raw: dict[str, object], field: str) -> str:
    value = str(raw.get(field, "")).strip()
    if not value:
        raise ValueError(f"{field} must be non-empty")
    return value


def _require_sha256(value: object, *, field: str) -> str:
    text = str(value if value is not None else "").strip()
    if len(text) != 64 or any(char not in "0123456789abcdef" for char in text):
        raise ValueError(f"{field} must be lowercase SHA-256")
    return text


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
        raise ValueError("live cadence requires complete Sportradar pagination-v2 evidence")
    earliest = _parse_time(
        batch_record.get("provider_generated_at_min"),
        field="provider_batch.provider_generated_at_min",
    )
    latest = _parse_time(
        batch_record.get("provider_generated_at_max"),
        field="provider_batch.provider_generated_at_max",
    )
    if earliest > latest:
        raise ValueError("provider generation bounds are inverted")
    return earliest, latest


def _stored_evidence_getter(
    *,
    comment_id: int,
    workflow_run_id: int,
    comment_bytes: bytes,
    run_bytes: bytes,
) -> GitHubGetBytes:
    comment_suffix = f"/issues/comments/{comment_id}"
    run_suffix = f"/actions/runs/{workflow_run_id}"

    def get_bytes(url: str) -> bytes:
        if url.endswith(comment_suffix):
            return comment_bytes
        if url.endswith(run_suffix):
            return run_bytes
        raise ValueError(f"unexpected retained GitHub evidence URL: {url}")

    return get_bytes


def _same_anchor_commitment(
    first: LiveProviderBatchAnchorEvidence,
    second: LiveProviderBatchAnchorEvidence,
) -> bool:
    return (
        first.comment_id == second.comment_id
        and first.workflow_run_id == second.workflow_run_id
        and first.anchor_created_at == second.anchor_created_at
        and _canonical_json(first.receipt) == _canonical_json(second.receipt)
    )


class LiveProviderCaptureCadenceStore:
    """Append-only cadence ledger authenticated from live GitHub server evidence."""

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
                "live provider-capture cadence store is locked; confirm no writer is active"
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
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError(f"live cadence record is not valid JSON: {path.name}") from exc
            if not isinstance(payload, dict):
                raise ValueError(f"live cadence record is not an object: {path.name}")
            records.append(payload)
        return records

    def _store_evidence(self, payload: bytes) -> str:
        digest = _sha256_bytes(payload)
        target = self.evidence_dir / digest
        if target.exists():
            if target.read_bytes() != payload:
                raise RuntimeError(f"live cadence evidence hash collision: {digest}")
            return digest
        _atomic_write(target, payload)
        return digest

    def _append_record(self, payload: dict[str, object]) -> dict[str, object]:
        records = self.records()
        previous = _ZERO_SHA256 if not records else str(records[-1]["record_sha256"])
        unsigned = dict(payload)
        unsigned["live_cadence_version"] = LIVE_CADENCE_VERSION
        unsigned["sequence"] = len(records) + 1
        unsigned["previous_record_sha256"] = previous
        digest = _record_sha256(unsigned)
        record = dict(unsigned)
        record["record_sha256"] = digest
        name = f"{len(records) + 1:08d}-{digest}.json"
        _atomic_write(self.records_dir / name, _pretty_json(record))
        return record

    def verify(
        self,
        *,
        batch_store: ProviderBatchStore,
        github_get_bytes: GitHubGetBytes | None = None,
    ) -> dict[str, object]:
        batch_store.verify()
        verify_paginated_provider_batches(batch_store)
        paths = self._record_paths()
        records = self.records()
        previous = _ZERO_SHA256
        batch_shas: set[str] = set()
        comment_ids: set[int] = set()
        workflow_run_ids: set[int] = set()
        anchor_times: list[datetime] = []

        for sequence, record in enumerate(records, start=1):
            if record.get("live_cadence_version") != LIVE_CADENCE_VERSION:
                raise ValueError(f"unexpected live cadence version at sequence {sequence}")
            if record.get("record_type") != "PROVIDER_BATCH_ATTESTATION":
                raise ValueError(f"unexpected live cadence record type at sequence {sequence}")
            if record.get("anchor_evidence_mode") != LIVE_EVIDENCE_MODE:
                raise ValueError("live cadence record does not use authenticated GitHub ledger evidence")
            if int(record.get("sequence", -1)) != sequence:
                raise ValueError(f"live provider-capture cadence sequence gap at {sequence}")

            observed_sha = _require_sha256(
                record.get("record_sha256"),
                field=f"live_cadence[{sequence}].record_sha256",
            )
            unsigned = dict(record)
            unsigned.pop("record_sha256", None)
            if _record_sha256(unsigned) != observed_sha:
                raise ValueError(f"live cadence record digest mismatch at sequence {sequence}")
            if record.get("previous_record_sha256") != previous:
                raise ValueError(f"live cadence hash chain mismatch at sequence {sequence}")
            if paths[sequence - 1].name != f"{sequence:08d}-{observed_sha}.json":
                raise ValueError(f"live cadence filename mismatch at sequence {sequence}")

            comment_sha = _require_sha256(
                record.get("github_comment_response_sha256"),
                field="github_comment_response_sha256",
            )
            run_sha = _require_sha256(
                record.get("workflow_run_response_sha256"),
                field="workflow_run_response_sha256",
            )
            if record.get("evidence_sha256") != [comment_sha, run_sha]:
                raise ValueError("live cadence evidence manifest mismatch")
            for digest in (comment_sha, run_sha):
                evidence_path = self.evidence_dir / digest
                if not evidence_path.is_file():
                    raise ValueError(f"missing retained live cadence evidence {digest}")
                if _sha256_file(evidence_path) != digest:
                    raise ValueError(f"retained live cadence evidence digest mismatch: {digest}")

            batch_sha = _require_sha256(
                record.get("batch_record_sha256"),
                field="batch_record_sha256",
            )
            batch_record = _find_batch_record(batch_store, batch_sha)
            provider_min, provider_max = _provider_generation_bounds(batch_record)
            comment_id = int(record.get("github_comment_id", -1))
            workflow_run_id = int(record.get("workflow_run_id", -1))
            if comment_id <= 0 or workflow_run_id <= 0:
                raise ValueError("live cadence GitHub identities must be positive")

            comment_bytes = (self.evidence_dir / comment_sha).read_bytes()
            run_bytes = (self.evidence_dir / run_sha).read_bytes()
            retained = fetch_live_anchor_evidence(
                comment_id=comment_id,
                batch_record=batch_record,
                get_bytes=_stored_evidence_getter(
                    comment_id=comment_id,
                    workflow_run_id=workflow_run_id,
                    comment_bytes=comment_bytes,
                    run_bytes=run_bytes,
                ),
            )
            if retained.workflow_run_id != workflow_run_id:
                raise ValueError("retained live cadence workflow-run ID does not reproduce")
            if retained.comment_response_sha256 != comment_sha:
                raise ValueError("retained GitHub comment response SHA does not reproduce")
            if retained.workflow_run_response_sha256 != run_sha:
                raise ValueError("retained GitHub run response SHA does not reproduce")

            current = fetch_live_anchor_evidence(
                comment_id=comment_id,
                batch_record=batch_record,
                get_bytes=github_get_bytes,
            )
            if not _same_anchor_commitment(retained, current):
                raise ValueError("live GitHub anchor commitment differs from retained evidence")

            anchor_created_at = current.anchor_created_at
            if record.get("batch_version") != BATCH_VERSION:
                raise ValueError("live cadence batch version mismatch")
            if record.get("pagination_schema") != PAGINATION_SCHEMA:
                raise ValueError("live cadence pagination schema mismatch")
            if record.get("schedule_date") != batch_record.get("schedule_date"):
                raise ValueError("live cadence schedule date does not reproduce from batch")
            if record.get("batch_observed_at") != batch_record.get("observed_at"):
                raise ValueError("live cadence observation does not reproduce from batch")
            if record.get("provider_generated_at_min") != provider_min.isoformat():
                raise ValueError("live cadence provider min generated_at does not reproduce")
            if record.get("provider_generated_at_max") != provider_max.isoformat():
                raise ValueError("live cadence provider max generated_at does not reproduce")
            if record.get("anchor_created_at") != anchor_created_at.isoformat():
                raise ValueError("live cadence anchor time does not reproduce from GitHub")

            if batch_sha in batch_shas:
                raise ValueError("provider batch has more than one live cadence attestation")
            if comment_id in comment_ids:
                raise ValueError("GitHub ledger comment is reused across live attestations")
            if workflow_run_id in workflow_run_ids:
                raise ValueError("GitHub workflow run is reused across live attestations")
            batch_shas.add(batch_sha)
            comment_ids.add(comment_id)
            workflow_run_ids.add(workflow_run_id)
            anchor_times.append(anchor_created_at)
            previous = observed_sha

        return {
            "live_cadence_version": LIVE_CADENCE_VERSION,
            "record_count": len(records),
            "attested_batch_count": len(batch_shas),
            "first_anchor_created_at": min(anchor_times).isoformat() if anchor_times else None,
            "last_anchor_created_at": max(anchor_times).isoformat() if anchor_times else None,
            "chain_head_sha256": previous,
            "status": "LIVE_VERIFIED",
        }


def attest_live_provider_batch(
    *,
    batch_store: ProviderBatchStore,
    cadence_store: LiveProviderCaptureCadenceStore,
    github_comment_id: int,
    github_get_bytes: GitHubGetBytes | None = None,
) -> dict[str, object]:
    """Append one provider batch only after live GitHub ledger authentication."""

    with cadence_store.write_lock():
        cadence_store.verify(
            batch_store=batch_store,
            github_get_bytes=github_get_bytes,
        )
        evidence = fetch_live_anchor_evidence(
            comment_id=github_comment_id,
            get_bytes=github_get_bytes,
        )
        batch_sha = _require_sha256(
            evidence.receipt.get("batch_record_sha256"),
            field="receipt.batch_record_sha256",
        )
        batch_record = _find_batch_record(batch_store, batch_sha)
        report = batch_store.verify()
        if report.get("chain_head_sha256") != batch_sha:
            raise ValueError("live GitHub anchor may only admit the current provider-batch chain head")
        verify_live_anchor_against_batch(batch_record=batch_record, evidence=evidence)
        provider_min, provider_max = _provider_generation_bounds(batch_record)

        comment_sha = cadence_store._store_evidence(evidence.comment_response_bytes)
        run_sha = cadence_store._store_evidence(evidence.workflow_run_response_bytes)
        if comment_sha != evidence.comment_response_sha256:
            raise AssertionError("stored GitHub comment evidence hash drifted")
        if run_sha != evidence.workflow_run_response_sha256:
            raise AssertionError("stored GitHub workflow-run evidence hash drifted")

        return cadence_store._append_record(
            {
                "record_type": "PROVIDER_BATCH_ATTESTATION",
                "anchor_evidence_mode": LIVE_EVIDENCE_MODE,
                "batch_version": BATCH_VERSION,
                "pagination_schema": PAGINATION_SCHEMA,
                "batch_record_sha256": batch_sha,
                "schedule_date": batch_record["schedule_date"],
                "batch_observed_at": batch_record["observed_at"],
                "provider_generated_at_min": provider_min.isoformat(),
                "provider_generated_at_max": provider_max.isoformat(),
                "anchor_created_at": evidence.anchor_created_at.isoformat(),
                "github_comment_id": evidence.comment_id,
                "workflow_run_id": evidence.workflow_run_id,
                "github_comment_response_sha256": comment_sha,
                "workflow_run_response_sha256": run_sha,
                "evidence_sha256": [comment_sha, run_sha],
            }
        )


def verify_live_capture_cadence(
    *,
    batch_store: ProviderBatchStore,
    cadence_store: LiveProviderCaptureCadenceStore,
    complete_through: datetime,
    github_get_bytes: GitHubGetBytes | None = None,
) -> dict[str, object]:
    """Authoritative promotion gate; every attestation is re-fetched live from GitHub."""

    if complete_through.tzinfo is None or complete_through.utcoffset() is None:
        raise ValueError("complete_through must be timezone-aware")
    cutoff = complete_through.astimezone(UTC)
    cadence_store.verify(
        batch_store=batch_store,
        github_get_bytes=github_get_bytes,
    )

    attestations = cadence_store.records()
    due_attestations = [
        record
        for record in attestations
        if _parse_time(record["anchor_created_at"], field="anchor_created_at") <= cutoff
    ]
    if not due_attestations:
        raise ValueError("live capture cadence has no authenticated provider batch by cutoff")

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
        raise ValueError("live provider capture cadence gap exceeds seven hours")
    if cutoff - anchor_times[-1] > _MAX_CADENCE_GAP:
        raise ValueError("live provider capture cadence is stale at completeness cutoff")

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
            "provider batches due by cutoff lack live GitHub cadence attestation: "
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
            "live provider capture cadence is missing UTC schedule dates: "
            + ", ".join(missing_dates)
        )

    max_gap_seconds = max((gap.total_seconds() for gap in gaps), default=0.0)
    return {
        "live_cadence_version": LIVE_CADENCE_VERSION,
        "complete_through": cutoff.isoformat(),
        "first_anchor_created_at": first_anchor.isoformat(),
        "last_anchor_created_at": anchor_times[-1].isoformat(),
        "attested_batch_count": len(due_attestations),
        "covered_schedule_date_count": len(schedule_dates),
        "maximum_observed_anchor_gap_seconds": max_gap_seconds,
        "maximum_allowed_anchor_gap_seconds": _MAX_CADENCE_GAP.total_seconds(),
        "status": "LIVE_CADENCE_VERIFIED",
    }
