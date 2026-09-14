from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from pathlib import Path

from tennis_genome.prospective.census import EventCensusStore

BATCH_VERSION = "FULL-STACK-FORWARD-001-provider-batch-v1"
BATCH_SCHEMA = "full-stack-forward-provider-batch-v1"
_PROVIDER = "SPORTRADAR"
_ZERO_SHA256 = "0" * 64
_IN_SCOPE_CATEGORIES = {
    "sr:category:3": ("ATP", "ATP"),
    "sr:category:6": ("WTA", "WTA"),
}

_CENSUS_REQUIRED = "CENSUS_REQUIRED"
_OUT_OF_SCOPE = "OUT_OF_SCOPE"
_DENOMINATOR_FAILURE = "DENOMINATOR_FAILURE"


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


def _as_dict(value: object, *, field: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object")
    return value


def _as_list(value: object, *, field: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be an array")
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


def _json_object(path: Path, *, label: str) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} must be UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def _record_sha256(record_without_sha: dict[str, object]) -> str:
    return _sha256_bytes(_canonical_json(record_without_sha))


def _event_row(summary: object, *, observed_at: datetime) -> dict[str, object]:
    root = _as_dict(summary, field="summary")
    event = _as_dict(root.get("sport_event"), field="sport_event")
    event_id = _required_text(event, "id")
    context = _as_dict(event.get("sport_event_context"), field="sport_event_context")
    category = _as_dict(context.get("category"), field="sport_event_context.category")
    competition = _as_dict(
        context.get("competition"),
        field="sport_event_context.competition",
    )
    category_id = _required_text(category, "id")
    category_name = _required_text(category, "name")
    competition_type = _required_text(competition, "type").lower()
    provider_status = _required_text(
        _as_dict(root.get("sport_event_status", {}), field="sport_event_status"),
        "status",
    ).lower()

    category_scope = _IN_SCOPE_CATEGORIES.get(category_id)
    if category_scope is None:
        return {
            "provider_event_id": event_id,
            "tour": None,
            "scheduled_start": None,
            "category_id": category_id,
            "category_name": category_name,
            "competition_type": competition_type,
            "provider_status": provider_status,
            "classification": _OUT_OF_SCOPE,
            "reason_code": "TOUR_CATEGORY_OUT_OF_SCOPE",
        }

    tour, expected_name = category_scope
    if category_name.upper() != expected_name:
        raise ValueError(
            f"Sportradar category semantic drift for {category_id}: {category_name!r}"
        )
    if competition_type != "singles":
        return {
            "provider_event_id": event_id,
            "tour": tour,
            "scheduled_start": None,
            "category_id": category_id,
            "category_name": category_name,
            "competition_type": competition_type,
            "provider_status": provider_status,
            "classification": _OUT_OF_SCOPE,
            "reason_code": "NOT_SINGLES",
        }

    try:
        scheduled_start = _parse_time(event.get("start_time"), field="sport_event.start_time")
    except ValueError:
        return {
            "provider_event_id": event_id,
            "tour": tour,
            "scheduled_start": None,
            "category_id": category_id,
            "category_name": category_name,
            "competition_type": competition_type,
            "provider_status": provider_status,
            "classification": _DENOMINATOR_FAILURE,
            "reason_code": "SCHEDULE_INVALID",
        }

    if observed_at >= scheduled_start:
        return {
            "provider_event_id": event_id,
            "tour": tour,
            "scheduled_start": scheduled_start.isoformat(),
            "category_id": category_id,
            "category_name": category_name,
            "competition_type": competition_type,
            "provider_status": provider_status,
            "classification": _DENOMINATOR_FAILURE,
            "reason_code": "DISCOVERY_WINDOW_MISSED",
        }

    return {
        "provider_event_id": event_id,
        "tour": tour,
        "scheduled_start": scheduled_start.isoformat(),
        "category_id": category_id,
        "category_name": category_name,
        "competition_type": competition_type,
        "provider_status": provider_status,
        "classification": _CENSUS_REQUIRED,
        "reason_code": "TOUR_LEVEL_SINGLES_PRESTART",
    }


def build_batch_manifest(
    *,
    raw_payload: object,
    schedule_date: date,
    observed_at: datetime,
    raw_payload_sha256: str,
) -> dict[str, object]:
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise ValueError("observed_at must be timezone-aware")
    observed_at = observed_at.astimezone(UTC)
    root = _as_dict(raw_payload, field="Sportradar daily summaries response")
    summaries = _as_list(root.get("summaries"), field="summaries")
    events = [_event_row(summary, observed_at=observed_at) for summary in summaries]
    ids = [str(event["provider_event_id"]) for event in events]
    if len(ids) != len(set(ids)):
        raise ValueError("Sportradar daily batch contains duplicate sport-event IDs")
    events.sort(key=lambda item: str(item["provider_event_id"]))
    return {
        "schema_version": BATCH_SCHEMA,
        "provider": _PROVIDER,
        "schedule_date": schedule_date.isoformat(),
        "observed_at": observed_at.isoformat(),
        "raw_payload_sha256": raw_payload_sha256,
        "raw_summary_count": len(summaries),
        "events": events,
    }


class ProviderBatchStore:
    """Append-only retained Sportradar batch evidence for denominator auditing."""

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
            raise RuntimeError("provider-batch store is locked; confirm no writer is active") from exc
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
                raise ValueError(f"provider-batch record is not an object: {path.name}")
            records.append(payload)
        return records

    def _store_evidence(self, payload: bytes) -> str:
        digest = _sha256_bytes(payload)
        target = self.evidence_dir / digest
        if target.exists():
            if target.read_bytes() != payload:
                raise RuntimeError(f"provider-batch evidence hash collision: {digest}")
            return digest
        _atomic_write(target, payload)
        return digest

    def _append_record(self, payload: dict[str, object]) -> dict[str, object]:
        report = self.verify()
        sequence = int(report["record_count"]) + 1
        unsigned = dict(payload)
        unsigned["batch_version"] = BATCH_VERSION
        unsigned["sequence"] = sequence
        unsigned["previous_record_sha256"] = report["chain_head_sha256"]
        digest = _record_sha256(unsigned)
        record = dict(unsigned)
        record["record_sha256"] = digest
        name = f"{sequence:08d}-{digest}.json"
        _atomic_write(self.records_dir / name, _pretty_json(record))
        return record

    def verify(self) -> dict[str, object]:
        paths = self._record_paths()
        records = self.records()
        previous = _ZERO_SHA256
        schedule_dates: Counter[str] = Counter()
        classification_counts: Counter[str] = Counter()

        for sequence, record in enumerate(records, start=1):
            if record.get("batch_version") != BATCH_VERSION:
                raise ValueError(f"unexpected provider-batch version at sequence {sequence}")
            if int(record.get("sequence", -1)) != sequence:
                raise ValueError(f"provider-batch sequence gap at {sequence}")
            observed_sha = str(record.get("record_sha256", ""))
            unsigned = dict(record)
            unsigned.pop("record_sha256", None)
            if _record_sha256(unsigned) != observed_sha:
                raise ValueError(f"provider-batch record digest mismatch at sequence {sequence}")
            if record.get("previous_record_sha256") != previous:
                raise ValueError(f"provider-batch hash chain mismatch at sequence {sequence}")
            expected_name = f"{sequence:08d}-{observed_sha}.json"
            if paths[sequence - 1].name != expected_name:
                raise ValueError(f"provider-batch filename mismatch at sequence {sequence}")

            raw_sha = str(record.get("raw_payload_sha256", ""))
            manifest_sha = str(record.get("manifest_sha256", ""))
            for digest in (raw_sha, manifest_sha):
                evidence = self.evidence_dir / digest
                if len(digest) != 64 or not evidence.is_file():
                    raise ValueError(f"missing provider-batch evidence {digest}")
                if _sha256_file(evidence) != digest:
                    raise ValueError(f"provider-batch evidence digest mismatch: {digest}")

            raw = _json_object(self.evidence_dir / raw_sha, label="provider batch raw payload")
            manifest = _json_object(
                self.evidence_dir / manifest_sha,
                label="provider batch manifest",
            )
            rebuilt = build_batch_manifest(
                raw_payload=raw,
                schedule_date=date.fromisoformat(str(record.get("schedule_date"))),
                observed_at=_parse_time(record.get("observed_at"), field="observed_at"),
                raw_payload_sha256=raw_sha,
            )
            if _canonical_json(rebuilt) != _canonical_json(manifest):
                raise ValueError("provider-batch manifest does not reproduce from raw evidence")
            for field in ("schedule_date", "observed_at", "raw_summary_count"):
                if record.get(field) != manifest.get(field):
                    raise ValueError(f"provider-batch {field} does not reproduce from evidence")
            schedule_dates[str(record["schedule_date"])] += 1
            for event in _as_list(manifest.get("events"), field="manifest.events"):
                row = _as_dict(event, field="manifest event")
                classification_counts[_required_text(row, "classification")] += 1
            previous = observed_sha

        return {
            "batch_version": BATCH_VERSION,
            "record_count": len(records),
            "schedule_date_counts": dict(sorted(schedule_dates.items())),
            "classification_counts": dict(sorted(classification_counts.items())),
            "chain_head_sha256": previous,
            "status": "VERIFIED",
        }


def capture_provider_batch(
    *,
    store: ProviderBatchStore,
    raw_payload_path: Path,
    schedule_date: date,
    observed_at: datetime,
) -> dict[str, object]:
    with store.write_lock():
        store.verify()
        raw_bytes = raw_payload_path.read_bytes()
        raw_sha = store._store_evidence(raw_bytes)
        raw_payload = _json_object(raw_payload_path, label="Sportradar daily summaries response")
        manifest = build_batch_manifest(
            raw_payload=raw_payload,
            schedule_date=schedule_date,
            observed_at=observed_at,
            raw_payload_sha256=raw_sha,
        )
        manifest_sha = store._store_evidence(_pretty_json(manifest))
        return store._append_record(
            {
                "record_type": "PROVIDER_BATCH",
                "provider": _PROVIDER,
                "schedule_date": manifest["schedule_date"],
                "observed_at": manifest["observed_at"],
                "raw_payload_sha256": raw_sha,
                "manifest_sha256": manifest_sha,
                "raw_summary_count": manifest["raw_summary_count"],
                "evidence_sha256": [raw_sha, manifest_sha],
            }
        )


def reconcile_batches_with_census(
    *,
    batch_store: ProviderBatchStore,
    census_store: EventCensusStore,
    complete_through: datetime | None = None,
) -> dict[str, object]:
    batch_report = batch_store.verify()
    census_report = census_store.verify()
    discoveries = {
        str(record["event_key"]): record
        for record in census_store.records()
        if record.get("record_type") == "CENSUS_DISCOVERY"
    }

    required: dict[str, dict[str, object]] = {}
    failures: list[str] = []
    seen_batch_events: set[str] = set()

    cutoff: datetime | None = None
    if complete_through is not None:
        if complete_through.tzinfo is None or complete_through.utcoffset() is None:
            raise ValueError("complete_through must be timezone-aware")
        cutoff = complete_through.astimezone(UTC)

    for record in batch_store.records():
        manifest_sha = str(record["manifest_sha256"])
        manifest = _json_object(
            batch_store.evidence_dir / manifest_sha,
            label="provider batch manifest",
        )
        for raw_event in _as_list(manifest.get("events"), field="manifest.events"):
            event = _as_dict(raw_event, field="manifest event")
            event_id = _required_text(event, "provider_event_id")
            event_key = f"{_PROVIDER}:{event_id}"
            seen_batch_events.add(event_key)
            classification = _required_text(event, "classification")
            start_raw = event.get("scheduled_start")
            start = None if start_raw is None else _parse_time(start_raw, field="scheduled_start")
            in_cutoff = cutoff is None or start is None or start <= cutoff

            if classification == _DENOMINATOR_FAILURE and in_cutoff:
                failures.append(f"{event_key}:{event.get('reason_code')}")
                continue
            if classification != _CENSUS_REQUIRED:
                continue
            if start is None:
                raise ValueError("CENSUS_REQUIRED provider event lacks scheduled_start")
            previous = required.get(event_key)
            if previous is not None:
                if previous.get("tour") != event.get("tour"):
                    raise ValueError("provider event tour changed across retained batches")
                if previous.get("scheduled_start") != event.get("scheduled_start"):
                    raise ValueError("provider event schedule changed across retained batches")
            required[event_key] = event

    if failures:
        raise ValueError(
            "provider batch contains denominator failures at/before completeness cutoff: "
            + ", ".join(sorted(set(failures)))
        )

    missing_discoveries: list[str] = []
    for event_key, event in required.items():
        discovery = discoveries.get(event_key)
        if discovery is None:
            missing_discoveries.append(event_key)
            continue
        if discovery.get("provider") != _PROVIDER:
            raise ValueError("batch/census provider mismatch")
        if discovery.get("tour") != event.get("tour"):
            raise ValueError("batch/census tour mismatch")
        if discovery.get("event_type") != "SINGLES":
            raise ValueError("batch/census event_type mismatch")
        batch_start = _parse_time(event["scheduled_start"], field="batch.scheduled_start")
        census_start = _parse_time(discovery["scheduled_start"], field="census.scheduled_start")
        if batch_start != census_start:
            raise ValueError("batch/census scheduled_start mismatch")
    if missing_discoveries:
        raise ValueError(
            "provider-batch events are missing census discovery: "
            + ", ".join(sorted(missing_discoveries))
        )

    orphan_census = sorted(
        event_key
        for event_key, discovery in discoveries.items()
        if discovery.get("provider") == _PROVIDER and event_key not in seen_batch_events
    )
    if orphan_census:
        raise ValueError(
            "Sportradar census discoveries are absent from retained provider batches: "
            + ", ".join(orphan_census)
        )

    return {
        "batch_version": BATCH_VERSION,
        "batch_chain_head_sha256": batch_report["chain_head_sha256"],
        "census_chain_head_sha256": census_report["chain_head_sha256"],
        "batch_record_count": batch_report["record_count"],
        "required_event_count": len(required),
        "reconciled_event_count": len(required),
        "denominator_failure_count": 0,
        "status": "RECONCILED",
    }
