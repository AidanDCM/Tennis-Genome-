from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

CENSUS_VERSION = "FULL-STACK-FORWARD-001-census-v1"
DISCOVERY_SCHEMA = "full-stack-forward-census-discovery-v1"
DISPOSITION_SCHEMA = "full-stack-forward-census-disposition-v1"
_ZERO_SHA256 = "0" * 64


class CensusStatus(StrEnum):
    PREDICTED = "PREDICTED"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    INPUT_UNAVAILABLE = "INPUT_UNAVAILABLE"
    EXCLUDED_PREMATCH = "EXCLUDED_PREMATCH"
    OPERATIONAL_FAILURE = "OPERATIONAL_FAILURE"


_REASON_CODES: dict[CensusStatus, frozenset[str]] = {
    CensusStatus.PREDICTED: frozenset({"PREDICTION_COMMITTED"}),
    CensusStatus.NOT_ELIGIBLE: frozenset(
        {
            "UNSUPPORTED_TOUR",
            "NOT_SINGLES",
            "UNSUPPORTED_BEST_OF",
            "EVENT_CANCELLED_PREMATCH",
        }
    ),
    CensusStatus.INPUT_UNAVAILABLE: frozenset(
        {
            "SOURCE_MANIFEST_UNAVAILABLE",
            "FOUNDATIONAL_STATE_UNAVAILABLE",
            "PROFILE_STATE_UNAVAILABLE",
            "SERVE_RETURN_STATE_UNAVAILABLE",
            "IDENTITY_UNRESOLVED",
        }
    ),
    CensusStatus.EXCLUDED_PREMATCH: frozenset(
        {
            "CALCULATOR_CONTRACT_REJECTED",
            "PREMATCH_SOURCE_INVALID",
            "SCHEDULE_INVALID",
        }
    ),
    CensusStatus.OPERATIONAL_FAILURE: frozenset(
        {
            "MISSED_COMMIT_WINDOW",
            "PIPELINE_FAILURE",
        }
    ),
}


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
    try:
        parsed = datetime.fromisoformat(str(value))
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


def _optional_text(raw: dict[str, object], field: str) -> str | None:
    value = raw.get(field)
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        raise ValueError(f"{field} must be null or non-empty")
    return text


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


def _validate_reason(status: CensusStatus, reason_code: str) -> None:
    allowed = _REASON_CODES[status]
    if reason_code not in allowed:
        raise ValueError(
            f"reason_code {reason_code!r} is not allowed for {status.value}; "
            f"allowed={sorted(allowed)}"
        )


class EventCensusStore:
    """Append-only local denominator ledger for prospective event completeness.

    The census proves that an event which entered the supervised discovery stream cannot
    silently disappear. It does not, by itself, prove the upstream provider feed was
    complete; retained provider-batch anchoring is a later hardening step.
    """

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
            raise RuntimeError("event census is locked; confirm no writer is active") from exc
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
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError(f"census record is not a JSON object: {path.name}")
            result.append(payload)
        return result

    def _store_evidence_bytes(self, payload: bytes) -> str:
        digest = _sha256_bytes(payload)
        target = self.evidence_dir / digest
        if target.exists():
            if target.read_bytes() != payload:
                raise RuntimeError(f"census evidence hash collision/corruption: {digest}")
            return digest
        _atomic_write(target, payload)
        return digest

    def _store_evidence_file(self, path: Path) -> str:
        return self._store_evidence_bytes(path.read_bytes())

    def _append_record(self, payload: dict[str, object]) -> dict[str, object]:
        report = self.verify()
        sequence = int(report["record_count"]) + 1
        previous = str(report["chain_head_sha256"])
        unsigned = dict(payload)
        forbidden = {"sequence", "previous_record_sha256", "record_sha256"}.intersection(unsigned)
        if forbidden:
            raise ValueError(f"census payload contains reserved fields: {sorted(forbidden)}")
        unsigned["census_version"] = CENSUS_VERSION
        unsigned["sequence"] = sequence
        unsigned["previous_record_sha256"] = previous
        digest = _record_sha256(unsigned)
        record = dict(unsigned)
        record["record_sha256"] = digest
        filename = f"{sequence:08d}-{digest}.json"
        _atomic_write(self.records_dir / filename, _pretty_json(record))
        return record

    def find_record(self, record_sha256: str) -> dict[str, object]:
        matches = [
            record
            for record in self.records()
            if str(record.get("record_sha256", "")) == record_sha256
        ]
        if len(matches) != 1:
            raise ValueError(f"expected exactly one census record {record_sha256}")
        return matches[0]

    def verify(self) -> dict[str, object]:
        paths = self._record_paths()
        records = self.records()
        expected_previous = _ZERO_SHA256
        discoveries: dict[str, dict[str, object]] = {}
        dispositions: dict[str, dict[str, object]] = {}
        status_counts: Counter[str] = Counter()
        reason_counts: Counter[str] = Counter()

        for expected_sequence, record in enumerate(records, start=1):
            if record.get("census_version") != CENSUS_VERSION:
                raise ValueError(f"unexpected census version at sequence {expected_sequence}")
            if int(record.get("sequence", -1)) != expected_sequence:
                raise ValueError(f"census sequence gap at {expected_sequence}")
            observed_sha = str(record.get("record_sha256", ""))
            unsigned = dict(record)
            unsigned.pop("record_sha256", None)
            if _record_sha256(unsigned) != observed_sha:
                raise ValueError(f"census record digest mismatch at sequence {expected_sequence}")
            if record.get("previous_record_sha256") != expected_previous:
                raise ValueError(f"census hash chain mismatch at sequence {expected_sequence}")
            expected_name = f"{expected_sequence:08d}-{observed_sha}.json"
            if paths[expected_sequence - 1].name != expected_name:
                raise ValueError(f"census record filename mismatch at sequence {expected_sequence}")

            evidence_hashes = record.get("evidence_sha256", [])
            if not isinstance(evidence_hashes, list) or not evidence_hashes:
                raise ValueError(f"census record {observed_sha} has no evidence manifest")
            for digest_raw in evidence_hashes:
                digest = str(digest_raw)
                if len(digest) != 64:
                    raise ValueError(f"invalid census evidence digest in {observed_sha}")
                evidence_path = self.evidence_dir / digest
                if not evidence_path.is_file():
                    raise ValueError(f"missing census evidence {digest}")
                if _sha256_file(evidence_path) != digest:
                    raise ValueError(f"census evidence digest mismatch: {digest}")

            record_type = str(record.get("record_type", ""))
            event_key = str(record.get("event_key", ""))
            if record_type == "CENSUS_DISCOVERY":
                if not event_key or event_key in discoveries:
                    raise ValueError("census discovery event_key must be unique and non-empty")
                observed_at = _parse_time(record.get("observed_at"), field="observed_at")
                scheduled_start = _parse_time(
                    record.get("scheduled_start"), field="scheduled_start"
                )
                if observed_at >= scheduled_start:
                    raise ValueError("census discovery must occur before scheduled start")
                evidence_sha = str(record.get("discovery_evidence_sha256", ""))
                if evidence_sha not in evidence_hashes:
                    raise ValueError("census discovery evidence is not retained")
                raw = _json_object(self.evidence_dir / evidence_sha, label="census discovery")
                if raw.get("schema_version") != DISCOVERY_SCHEMA:
                    raise ValueError("census discovery evidence schema is not supported")
                expected = {
                    "provider": _required_text(raw, "provider"),
                    "provider_event_id": _required_text(raw, "provider_event_id"),
                    "tour": _required_text(raw, "tour"),
                    "event_type": _required_text(raw, "event_type"),
                    "observed_at": _parse_time(
                        raw.get("observed_at"), field="observed_at"
                    ).isoformat(),
                    "scheduled_start": _parse_time(
                        raw.get("scheduled_start"), field="scheduled_start"
                    ).isoformat(),
                    "match_id": _optional_text(raw, "match_id"),
                }
                for field, value in expected.items():
                    if record.get(field) != value:
                        raise ValueError(
                            f"census discovery {field} does not reproduce from evidence"
                        )
                if event_key != f"{expected['provider']}:{expected['provider_event_id']}":
                    raise ValueError("census discovery event_key does not reproduce")
                discoveries[event_key] = record
            elif record_type == "CENSUS_DISPOSITION":
                discovery = discoveries.get(event_key)
                if discovery is None:
                    raise ValueError("census disposition must reference an earlier discovery")
                if event_key in dispositions:
                    raise ValueError(f"census event disposed more than once: {event_key}")
                status = CensusStatus(str(record.get("status", "")))
                reason_code = str(record.get("reason_code", ""))
                _validate_reason(status, reason_code)
                disposed_at = _parse_time(record.get("disposed_at"), field="disposed_at")
                scheduled_start = _parse_time(
                    discovery.get("scheduled_start"), field="scheduled_start"
                )
                if status != CensusStatus.OPERATIONAL_FAILURE and disposed_at >= scheduled_start:
                    raise ValueError(
                        f"{status.value} disposition must be recorded before scheduled start"
                    )
                prediction_sha = record.get("prediction_record_sha256")
                match_id = record.get("match_id")
                if status == CensusStatus.PREDICTED:
                    if not isinstance(prediction_sha, str) or len(prediction_sha) != 64:
                        raise ValueError("PREDICTED disposition requires prediction_record_sha256")
                    if not isinstance(match_id, str) or not match_id.strip():
                        raise ValueError("PREDICTED disposition requires match_id")
                elif prediction_sha is not None or match_id is not None:
                    raise ValueError("non-PREDICTED disposition may not bind a prediction")

                disposition_evidence_sha = str(record.get("disposition_evidence_sha256", ""))
                if disposition_evidence_sha not in evidence_hashes:
                    raise ValueError("census disposition evidence is not retained")
                raw = _json_object(
                    self.evidence_dir / disposition_evidence_sha,
                    label="census disposition",
                )
                if raw.get("schema_version") != DISPOSITION_SCHEMA:
                    raise ValueError("census disposition evidence schema is not supported")
                expected_disposition = {
                    "event_key": _required_text(raw, "event_key"),
                    "status": _required_text(raw, "status"),
                    "reason_code": _required_text(raw, "reason_code"),
                    "disposed_at": _parse_time(
                        raw.get("disposed_at"), field="disposed_at"
                    ).isoformat(),
                    "prediction_record_sha256": _optional_text(raw, "prediction_record_sha256"),
                    "match_id": _optional_text(raw, "match_id"),
                }
                for field, value in expected_disposition.items():
                    if record.get(field) != value:
                        raise ValueError(
                            f"census disposition {field} does not reproduce from evidence"
                        )
                status_counts[status.value] += 1
                reason_counts[reason_code] += 1
                dispositions[event_key] = record
            else:
                raise ValueError(f"unknown census record type: {record_type!r}")
            expected_previous = observed_sha

        open_keys = sorted(set(discoveries) - set(dispositions))
        return {
            "census_version": CENSUS_VERSION,
            "record_count": len(records),
            "discovery_count": len(discoveries),
            "disposition_count": len(dispositions),
            "open_count": len(open_keys),
            "open_event_keys": open_keys,
            "status_counts": dict(sorted(status_counts.items())),
            "reason_counts": dict(sorted(reason_counts.items())),
            "chain_head_sha256": expected_previous,
            "status": "VERIFIED",
        }


def record_discovery(
    *,
    store: EventCensusStore,
    discovery_evidence_path: Path,
) -> dict[str, object]:
    with store.write_lock():
        store.verify()
        raw = _json_object(discovery_evidence_path, label="census discovery")
        if raw.get("schema_version") != DISCOVERY_SCHEMA:
            raise ValueError("census discovery evidence schema is not supported")
        provider = _required_text(raw, "provider")
        provider_event_id = _required_text(raw, "provider_event_id")
        event_key = f"{provider}:{provider_event_id}"
        if any(record.get("event_key") == event_key for record in store.records()):
            raise ValueError(f"census event already exists: {event_key}")
        observed_at = _parse_time(raw.get("observed_at"), field="observed_at")
        scheduled_start = _parse_time(raw.get("scheduled_start"), field="scheduled_start")
        if observed_at >= scheduled_start:
            raise ValueError("census discovery must occur before scheduled start")
        evidence_sha = store._store_evidence_file(discovery_evidence_path)
        return store._append_record(
            {
                "record_type": "CENSUS_DISCOVERY",
                "event_key": event_key,
                "provider": provider,
                "provider_event_id": provider_event_id,
                "tour": _required_text(raw, "tour"),
                "event_type": _required_text(raw, "event_type"),
                "observed_at": observed_at.isoformat(),
                "scheduled_start": scheduled_start.isoformat(),
                "match_id": _optional_text(raw, "match_id"),
                "discovery_evidence_sha256": evidence_sha,
                "evidence_sha256": [evidence_sha],
            }
        )


def record_disposition(
    *,
    store: EventCensusStore,
    discovery_record_sha256: str,
    status: CensusStatus,
    reason_code: str,
    disposed_at: datetime,
    prediction_record_sha256: str | None = None,
    match_id: str | None = None,
    supporting_evidence_paths: Sequence[Path] = (),
) -> dict[str, object]:
    with store.write_lock():
        store.verify()
        discovery = store.find_record(discovery_record_sha256)
        if discovery.get("record_type") != "CENSUS_DISCOVERY":
            raise ValueError("census disposition must reference a discovery record")
        event_key = str(discovery["event_key"])
        if any(
            record.get("record_type") == "CENSUS_DISPOSITION"
            and record.get("event_key") == event_key
            for record in store.records()
        ):
            raise ValueError("census event already has a terminal disposition")
        _validate_reason(status, reason_code)
        if disposed_at.tzinfo is None or disposed_at.utcoffset() is None:
            raise ValueError("disposed_at must be timezone-aware")
        disposed_at = disposed_at.astimezone(UTC)
        scheduled_start = _parse_time(discovery["scheduled_start"], field="scheduled_start")
        if status != CensusStatus.OPERATIONAL_FAILURE and disposed_at >= scheduled_start:
            raise ValueError(f"{status.value} disposition must precede scheduled start")
        if status == CensusStatus.PREDICTED:
            if prediction_record_sha256 is None or len(prediction_record_sha256) != 64:
                raise ValueError("PREDICTED disposition requires prediction_record_sha256")
            if match_id is None or not match_id.strip():
                raise ValueError("PREDICTED disposition requires match_id")
        elif prediction_record_sha256 is not None or match_id is not None:
            raise ValueError("non-PREDICTED disposition may not bind a prediction")
        if status != CensusStatus.PREDICTED and not supporting_evidence_paths:
            raise ValueError("non-PREDICTED disposition requires supporting evidence")

        disposition_evidence = {
            "schema_version": DISPOSITION_SCHEMA,
            "event_key": event_key,
            "status": status.value,
            "reason_code": reason_code,
            "disposed_at": disposed_at.isoformat(),
            "prediction_record_sha256": prediction_record_sha256,
            "match_id": match_id,
        }
        disposition_evidence_sha = store._store_evidence_bytes(_pretty_json(disposition_evidence))
        evidence_shas = [disposition_evidence_sha]
        evidence_shas.extend(store._store_evidence_file(path) for path in supporting_evidence_paths)
        evidence_shas = list(dict.fromkeys(evidence_shas))
        return store._append_record(
            {
                "record_type": "CENSUS_DISPOSITION",
                "event_key": event_key,
                "discovery_record_sha256": discovery_record_sha256,
                "status": status.value,
                "reason_code": reason_code,
                "disposed_at": disposed_at.isoformat(),
                "prediction_record_sha256": prediction_record_sha256,
                "match_id": match_id,
                "disposition_evidence_sha256": disposition_evidence_sha,
                "evidence_sha256": evidence_shas,
            }
        )


def reconcile_with_pilot(
    *,
    census_store: EventCensusStore,
    pilot_store: Any,
    complete_through: datetime | None = None,
) -> dict[str, object]:
    """Cross-check census dispositions against the prospective prediction ledger.

    Formal forward analysis should require this reconciliation to pass through the analysis
    cutoff. An event discovered before that cutoff may not remain silently unresolved.
    """

    census_report = census_store.verify()
    pilot_report = pilot_store.verify()
    census_records = census_store.records()
    pilot_records = pilot_store.records()

    discoveries = {
        str(record["event_key"]): record
        for record in census_records
        if record.get("record_type") == "CENSUS_DISCOVERY"
    }
    dispositions = {
        str(record["event_key"]): record
        for record in census_records
        if record.get("record_type") == "CENSUS_DISPOSITION"
    }
    predictions = {
        str(record["record_sha256"]): record
        for record in pilot_records
        if record.get("record_type") == "PREDICTION_COMMIT"
    }

    linked_prediction_shas: set[str] = set()
    for event_key, disposition in dispositions.items():
        if disposition.get("status") != CensusStatus.PREDICTED.value:
            continue
        prediction_sha = str(disposition["prediction_record_sha256"])
        prediction = predictions.get(prediction_sha)
        if prediction is None:
            raise ValueError(
                f"census PREDICTED event has no matching pilot prediction: {event_key}"
            )
        if prediction_sha in linked_prediction_shas:
            raise ValueError(f"pilot prediction linked to multiple census events: {prediction_sha}")
        linked_prediction_shas.add(prediction_sha)
        discovery = discoveries[event_key]
        if disposition.get("match_id") != prediction.get("match_id"):
            raise ValueError("census/pilot match_id mismatch")
        discovery_match = discovery.get("match_id")
        if discovery_match is not None and discovery_match != prediction.get("match_id"):
            raise ValueError("census discovery canonical match_id differs from prediction")
        if discovery.get("tour") != prediction.get("tour"):
            raise ValueError("census/pilot tour mismatch")
        census_start = _parse_time(discovery["scheduled_start"], field="census.scheduled_start")
        pilot_start = _parse_time(prediction["scheduled_start"], field="pilot.scheduled_start")
        if census_start != pilot_start:
            raise ValueError("census/pilot scheduled_start mismatch")
        disposed_at = _parse_time(disposition["disposed_at"], field="disposed_at")
        committed_at = _parse_time(prediction["committed_at"], field="committed_at")
        if disposed_at < committed_at:
            raise ValueError("PREDICTED census disposition predates prediction commitment")

    unlinked_predictions = sorted(set(predictions) - linked_prediction_shas)
    if unlinked_predictions:
        raise ValueError(
            "pilot predictions are missing PREDICTED census disposition: "
            + ", ".join(unlinked_predictions)
        )

    unresolved_past_due: list[str] = []
    if complete_through is not None:
        if complete_through.tzinfo is None or complete_through.utcoffset() is None:
            raise ValueError("complete_through must be timezone-aware")
        cutoff = complete_through.astimezone(UTC)
        for event_key, discovery in discoveries.items():
            if event_key in dispositions:
                continue
            scheduled_start = _parse_time(discovery["scheduled_start"], field="scheduled_start")
            if scheduled_start <= cutoff:
                unresolved_past_due.append(event_key)
        if unresolved_past_due:
            raise ValueError(
                "census has unresolved events at/before completeness cutoff: "
                + ", ".join(sorted(unresolved_past_due))
            )

    return {
        "census_version": CENSUS_VERSION,
        "census_chain_head_sha256": census_report["chain_head_sha256"],
        "pilot_chain_head_sha256": pilot_report["chain_head_sha256"],
        "discovery_count": census_report["discovery_count"],
        "disposition_count": census_report["disposition_count"],
        "prediction_count": pilot_report["prediction_count"],
        "linked_prediction_count": len(linked_prediction_shas),
        "open_count": census_report["open_count"],
        "status_counts": census_report["status_counts"],
        "reason_counts": census_report["reason_counts"],
        "complete_through": (
            None if complete_through is None else complete_through.astimezone(UTC).isoformat()
        ),
        "status": "RECONCILED",
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prospective eligible-event census")
    subparsers = parser.add_subparsers(dest="command", required=True)

    discover = subparsers.add_parser("discover")
    discover.add_argument("--store", required=True, type=Path)
    discover.add_argument("--evidence", required=True, type=Path)

    dispose = subparsers.add_parser("dispose")
    dispose.add_argument("--store", required=True, type=Path)
    dispose.add_argument("--discovery-record-sha256", required=True)
    dispose.add_argument(
        "--status", required=True, choices=[status.value for status in CensusStatus]
    )
    dispose.add_argument("--reason-code", required=True)
    dispose.add_argument("--disposed-at", required=True)
    dispose.add_argument("--prediction-record-sha256")
    dispose.add_argument("--match-id")
    dispose.add_argument("--supporting-evidence", action="append", type=Path, default=[])

    verify = subparsers.add_parser("verify")
    verify.add_argument("--store", required=True, type=Path)
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    store = EventCensusStore(args.store)
    if args.command == "discover":
        result = record_discovery(store=store, discovery_evidence_path=args.evidence)
    elif args.command == "dispose":
        result = record_disposition(
            store=store,
            discovery_record_sha256=args.discovery_record_sha256,
            status=CensusStatus(args.status),
            reason_code=args.reason_code,
            disposed_at=_parse_time(args.disposed_at, field="disposed_at"),
            prediction_record_sha256=args.prediction_record_sha256,
            match_id=args.match_id,
            supporting_evidence_paths=args.supporting_evidence,
        )
    else:
        result = store.verify()
    print(_pretty_json(result).decode("utf-8"), end="")


if __name__ == "__main__":
    main()
