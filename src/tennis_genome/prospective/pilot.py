from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
import platform
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from tennis_genome.calculator.contract import load_validated_matchup_calculator
from tennis_genome.calculator.io import load_matchup_input

PILOT_VERSION = "FULL-STACK-PILOT-001-ledger-v1"
_ZERO_SHA256 = "0" * 64
_RUNTIME_DISTRIBUTIONS = (
    "annotated-types",
    "cloudpickle",
    "duckdb",
    "joblib",
    "narwhals",
    "numpy",
    "pandas",
    "pyarrow",
    "pydantic",
    "pydantic-core",
    "python-dateutil",
    "scikit-learn",
    "scipy",
    "six",
    "threadpoolctl",
    "typing-extensions",
    "typing-inspection",
)
_FINISH_STATUSES = frozenset({"COMPLETED", "RETIREMENT", "WALKOVER", "DEFAULTED"})


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


def _parse_time(value: str, *, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO-8601 datetime") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return parsed


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _source_tree_sha256() -> str:
    package_root = Path(__file__).resolve().parents[1]
    digest = hashlib.sha256()
    for path in sorted(package_root.rglob("*.py")):
        relative = path.relative_to(package_root).as_posix().encode("utf-8")
        digest.update(relative)
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def runtime_manifest() -> dict[str, object]:
    versions: dict[str, str] = {}
    for distribution in _RUNTIME_DISTRIBUTIONS:
        try:
            versions[distribution] = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError as exc:
            raise RuntimeError(
                f"required runtime distribution is unavailable: {distribution}"
            ) from exc
    return {
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "packages": versions,
        "source_tree_sha256": _source_tree_sha256(),
    }


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


class ProspectivePilotStore:
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
                "prospective pilot store is locked; recover only after confirming "
                "no writer is active"
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
            payload = json.loads(path.read_text())
            if not isinstance(payload, dict):
                raise ValueError(f"prospective record is not a JSON object: {path.name}")
            records.append(payload)
        return records

    def _store_evidence_bytes(self, payload: bytes) -> str:
        digest = _sha256_bytes(payload)
        path = self.evidence_dir / digest
        if path.exists():
            if path.read_bytes() != payload:
                raise RuntimeError(f"evidence hash collision or corruption: {digest}")
            return digest
        _atomic_write(path, payload)
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
            raise ValueError(f"record payload contains reserved fields: {sorted(forbidden)}")
        unsigned["pilot_version"] = PILOT_VERSION
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
            raise ValueError(f"expected exactly one prospective record {record_sha256}")
        return matches[0]

    def verify(self) -> dict[str, object]:
        paths = self._record_paths()
        records = self.records()
        expected_previous = _ZERO_SHA256
        prediction_ids: set[str] = set()
        match_ids: set[str] = set()
        prediction_by_sha: dict[str, dict[str, object]] = {}
        settled_predictions: set[str] = set()
        prediction_count = 0
        settlement_count = 0

        for expected_sequence, record in enumerate(records, start=1):
            if record.get("pilot_version") != PILOT_VERSION:
                raise ValueError(f"unexpected pilot version at sequence {expected_sequence}")
            if int(record.get("sequence", -1)) != expected_sequence:
                raise ValueError(f"prospective sequence gap at {expected_sequence}")
            observed_sha = str(record.get("record_sha256", ""))
            unsigned = dict(record)
            unsigned.pop("record_sha256", None)
            if _record_sha256(unsigned) != observed_sha:
                raise ValueError(
                    f"prospective record digest mismatch at sequence {expected_sequence}"
                )
            if record.get("previous_record_sha256") != expected_previous:
                raise ValueError(f"prospective hash chain mismatch at sequence {expected_sequence}")
            expected_name = f"{expected_sequence:08d}-{observed_sha}.json"
            if paths[expected_sequence - 1].name != expected_name:
                raise ValueError(
                    f"prospective record filename mismatch at sequence {expected_sequence}"
                )

            evidence_hashes = record.get("evidence_sha256", [])
            if not isinstance(evidence_hashes, list) or not evidence_hashes:
                raise ValueError(f"record {observed_sha} has no evidence manifest")
            for evidence_sha_raw in evidence_hashes:
                evidence_sha = str(evidence_sha_raw)
                if len(evidence_sha) != 64:
                    raise ValueError(f"invalid evidence SHA-256 in record {observed_sha}")
                evidence_path = self.evidence_dir / evidence_sha
                if not evidence_path.is_file():
                    raise ValueError(f"missing evidence {evidence_sha} for record {observed_sha}")
                if _sha256_file(evidence_path) != evidence_sha:
                    raise ValueError(f"evidence digest mismatch: {evidence_sha}")

            record_type = str(record.get("record_type", ""))
            if record_type == "PREDICTION_COMMIT":
                prediction_count += 1
                prediction_id = str(record.get("prediction_id", ""))
                match_id = str(record.get("match_id", ""))
                if not prediction_id or prediction_id in prediction_ids:
                    raise ValueError(
                        f"duplicate/empty prediction_id at sequence {expected_sequence}"
                    )
                if not match_id or match_id in match_ids:
                    raise ValueError(f"duplicate/empty match_id at sequence {expected_sequence}")
                prediction_ids.add(prediction_id)
                match_ids.add(match_id)
                committed_at = _parse_time(str(record["committed_at"]), field="committed_at")
                scheduled_start = _parse_time(
                    str(record["scheduled_start"]), field="scheduled_start"
                )
                if committed_at >= scheduled_start:
                    raise ValueError("prediction commitment does not precede scheduled start")
                p_a = float(record["final_probability_a"])
                p_b = float(record["final_probability_b"])
                if not math.isfinite(p_a) or not math.isfinite(p_b):
                    raise ValueError("prospective probability is non-finite")
                if not 0.0 <= p_a <= 1.0 or not 0.0 <= p_b <= 1.0:
                    raise ValueError("prospective probability is outside [0, 1]")
                if abs((p_a + p_b) - 1.0) > 1e-9:
                    raise ValueError("prospective probabilities do not sum to one")
                source_hashes = record.get("source_manifest_hashes", [])
                if not isinstance(source_hashes, list) or not source_hashes:
                    raise ValueError("prediction record lacks source manifest hashes")
                if not set(str(value) for value in source_hashes).issubset(
                    set(str(value) for value in evidence_hashes)
                ):
                    raise ValueError("source manifest evidence is not retained")
                prediction_by_sha[observed_sha] = record
            elif record_type == "SETTLEMENT":
                settlement_count += 1
                prediction_sha = str(record.get("prediction_record_sha256", ""))
                if prediction_sha in settled_predictions:
                    raise ValueError(f"prediction settled more than once: {prediction_sha}")
                prediction = prediction_by_sha.get(prediction_sha)
                if prediction is None:
                    raise ValueError("settlement does not reference an earlier prediction record")
                settled_predictions.add(prediction_sha)
                winner = str(record.get("winner_player_id", ""))
                if winner not in {str(prediction["player_a_id"]), str(prediction["player_b_id"])}:
                    raise ValueError("settlement winner is not a prediction competitor")
                status = str(record.get("finish_status", ""))
                if status not in _FINISH_STATUSES:
                    raise ValueError(f"unrecognized finish status: {status}")
                settled_at = _parse_time(str(record["settled_at"]), field="settled_at")
                actual_raw = record.get("actual_start")
                actual_start = (
                    None
                    if actual_raw is None
                    else _parse_time(str(actual_raw), field="actual_start")
                )
                if actual_start is not None and settled_at < actual_start:
                    raise ValueError("settlement was recorded before actual start")
                committed_at = _parse_time(
                    str(prediction["committed_at"]), field="prediction.committed_at"
                )
                expected_timing = (
                    "ACTUAL_START_UNVERIFIED"
                    if actual_start is None
                    else (
                        "PRE_START_VERIFIED"
                        if committed_at < actual_start
                        else "COMMIT_NOT_PRE_START"
                    )
                )
                if record.get("timing_status") != expected_timing:
                    raise ValueError("settlement timing status does not reproduce")
                expected_primary = status == "COMPLETED" and expected_timing == "PRE_START_VERIFIED"
                if bool(record.get("primary_evaluation_eligible")) != expected_primary:
                    raise ValueError("primary evaluation eligibility does not reproduce")
            else:
                raise ValueError(f"unknown prospective record type: {record_type!r}")

            expected_previous = observed_sha

        return {
            "pilot_version": PILOT_VERSION,
            "record_count": len(records),
            "prediction_count": prediction_count,
            "settlement_count": settlement_count,
            "chain_head_sha256": expected_previous,
            "status": "VERIFIED",
        }

    def recover(self) -> dict[str, object]:
        removed: list[str] = []
        for directory in (self.root, self.records_dir, self.evidence_dir):
            if not directory.exists():
                continue
            for path in directory.glob("*.tmp"):
                removed.append(str(path.relative_to(self.root)))
                path.unlink()
        if self.lock_path.exists():
            removed.append(str(self.lock_path.relative_to(self.root)))
            self.lock_path.unlink()
        report = self.verify()
        report["recovery_removed"] = sorted(removed)
        return report


def commit_prediction(
    *,
    store: ProspectivePilotStore,
    bundle_path: Path,
    input_path: Path,
    scheduled_start: str,
    source_evidence_paths: Sequence[Path],
    schedule_evidence_path: Path,
    now: Callable[[], datetime] = _utc_now,
) -> dict[str, object]:
    with store.write_lock():
        store.verify()
        calculator = load_validated_matchup_calculator(bundle_path)
        matchup = load_matchup_input(input_path)
        committed_at = now()
        if committed_at.tzinfo is None or committed_at.utcoffset() is None:
            raise ValueError("commit clock must return a timezone-aware datetime")
        committed_at = committed_at.astimezone(UTC)
        scheduled = _parse_time(scheduled_start, field="scheduled_start")
        if committed_at >= scheduled:
            raise ValueError("prediction commitment must precede scheduled start")
        if matchup.created_at > committed_at:
            raise ValueError("matchup created_at cannot be later than commitment time")
        if matchup.created_at >= scheduled:
            raise ValueError("matchup created_at must precede scheduled start")

        if any(
            record.get("record_type") == "PREDICTION_COMMIT"
            and (
                record.get("prediction_id") == matchup.prediction_id
                or record.get("match_id") == matchup.match_id
            )
            for record in store.records()
        ):
            raise ValueError(
                "pilot allows only one committed prediction per prediction_id/match_id"
            )

        source_by_sha = {_sha256_file(path): path for path in source_evidence_paths}
        expected_source = set(matchup.source_manifest_hashes)
        if set(source_by_sha) != expected_source:
            raise ValueError(
                "source evidence SHA-256 set must exactly match matchup source_manifest_hashes"
            )

        input_sha = store._store_evidence_file(input_path)
        source_shas = [
            store._store_evidence_file(source_by_sha[digest])
            for digest in matchup.source_manifest_hashes
        ]
        schedule_sha = store._store_evidence_file(schedule_evidence_path)
        bundle_file_sha = store._store_evidence_file(bundle_path)

        result = calculator.calculate(matchup)
        calculation_sha = store._store_evidence_bytes(_pretty_json(result.to_dict()))
        runtime_sha = store._store_evidence_bytes(_pretty_json(runtime_manifest()))

        strict_core = result.prediction.component_probabilities.get("strict_core_v1")
        if strict_core is None or not math.isfinite(float(strict_core)):
            raise ValueError("calculation lacks finite strict_core_v1 comparator")

        evidence = list(
            dict.fromkeys(
                [
                    input_sha,
                    *source_shas,
                    schedule_sha,
                    bundle_file_sha,
                    calculation_sha,
                    runtime_sha,
                ]
            )
        )
        return store._append_record(
            {
                "record_type": "PREDICTION_COMMIT",
                "prediction_id": matchup.prediction_id,
                "match_id": matchup.match_id,
                "tour": matchup.tour,
                "player_a_id": matchup.player_a_id,
                "player_b_id": matchup.player_b_id,
                "prediction_cutoff_at": matchup.prediction_cutoff_at.isoformat(),
                "calculation_created_at": matchup.created_at.isoformat(),
                "scheduled_start": scheduled.isoformat(),
                "committed_at": committed_at.isoformat(),
                "final_probability_a": result.prediction.p_player_a,
                "final_probability_b": result.prediction.p_player_b,
                "strict_core_probability_a": float(strict_core),
                "production_bundle_sha256": result.production_bundle_sha256,
                "production_neighbor_bank_sha256": {
                    "ATP": calculator.bundle.atp.neighbor_bank.sha256,
                    "WTA": calculator.bundle.wta.neighbor_bank.sha256,
                },
                "bundle_file_sha256": bundle_file_sha,
                "input_sha256": input_sha,
                "calculation_sha256": calculation_sha,
                "runtime_manifest_sha256": runtime_sha,
                "source_manifest_hashes": list(matchup.source_manifest_hashes),
                "schedule_evidence_sha256": schedule_sha,
                "evidence_sha256": evidence,
                "assessment_status": result.assessment_status,
            }
        )


def settle_prediction(
    *,
    store: ProspectivePilotStore,
    prediction_record_sha256: str,
    winner_player_id: str,
    finish_status: str,
    settlement_evidence_path: Path,
    actual_start: str | None,
    now: Callable[[], datetime] = _utc_now,
) -> dict[str, object]:
    with store.write_lock():
        store.verify()
        prediction = store.find_record(prediction_record_sha256)
        if prediction.get("record_type") != "PREDICTION_COMMIT":
            raise ValueError("settlement must reference a prediction commit record")
        if any(
            record.get("record_type") == "SETTLEMENT"
            and record.get("prediction_record_sha256") == prediction_record_sha256
            for record in store.records()
        ):
            raise ValueError("prediction already has a settlement record")

        status = finish_status.upper()
        if status not in _FINISH_STATUSES:
            raise ValueError(f"finish_status must be one of {sorted(_FINISH_STATUSES)}")
        if winner_player_id not in {str(prediction["player_a_id"]), str(prediction["player_b_id"])}:
            raise ValueError("winner_player_id must match a canonical prediction competitor")

        settled_at = now()
        if settled_at.tzinfo is None or settled_at.utcoffset() is None:
            raise ValueError("settlement clock must return a timezone-aware datetime")
        settled_at = settled_at.astimezone(UTC)
        parsed_actual = (
            None if actual_start is None else _parse_time(actual_start, field="actual_start")
        )
        if parsed_actual is not None and settled_at < parsed_actual:
            raise ValueError("settlement cannot be recorded before actual start")

        committed = _parse_time(str(prediction["committed_at"]), field="committed_at")
        timing_status = (
            "ACTUAL_START_UNVERIFIED"
            if parsed_actual is None
            else ("PRE_START_VERIFIED" if committed < parsed_actual else "COMMIT_NOT_PRE_START")
        )
        primary_eligible = status == "COMPLETED" and timing_status == "PRE_START_VERIFIED"
        settlement_sha = store._store_evidence_file(settlement_evidence_path)
        return store._append_record(
            {
                "record_type": "SETTLEMENT",
                "prediction_record_sha256": prediction_record_sha256,
                "prediction_id": prediction["prediction_id"],
                "match_id": prediction["match_id"],
                "tour": prediction["tour"],
                "winner_player_id": winner_player_id,
                "finish_status": status,
                "actual_start": None if parsed_actual is None else parsed_actual.isoformat(),
                "settled_at": settled_at.isoformat(),
                "timing_status": timing_status,
                "primary_evaluation_eligible": primary_eligible,
                "settlement_evidence_sha256": settlement_sha,
                "evidence_sha256": [settlement_sha],
            }
        )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Immutable supervised prospective evidence ledger for TGE-Independent-v1"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    commit = subparsers.add_parser("commit", help="calculate and immutably commit a prediction")
    commit.add_argument("--store", required=True, type=Path)
    commit.add_argument("--bundle", required=True, type=Path)
    commit.add_argument("--input", required=True, type=Path)
    commit.add_argument("--scheduled-start", required=True)
    commit.add_argument("--source-evidence", action="append", type=Path, default=[])
    commit.add_argument("--schedule-evidence", required=True, type=Path)

    settle = subparsers.add_parser("settle", help="append a separate settlement record")
    settle.add_argument("--store", required=True, type=Path)
    settle.add_argument("--prediction-record-sha256", required=True)
    settle.add_argument("--winner-player-id", required=True)
    settle.add_argument("--finish-status", required=True, choices=sorted(_FINISH_STATUSES))
    settle.add_argument("--actual-start")
    settle.add_argument("--settlement-evidence", required=True, type=Path)

    verify = subparsers.add_parser("verify", help="verify the complete evidence/hash chain")
    verify.add_argument("--store", required=True, type=Path)

    recover = subparsers.add_parser("recover", help="remove interrupted temp/lock files and verify")
    recover.add_argument("--store", required=True, type=Path)
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    store = ProspectivePilotStore(args.store)
    if args.command == "commit":
        result = commit_prediction(
            store=store,
            bundle_path=args.bundle,
            input_path=args.input,
            scheduled_start=args.scheduled_start,
            source_evidence_paths=args.source_evidence,
            schedule_evidence_path=args.schedule_evidence,
        )
    elif args.command == "settle":
        result = settle_prediction(
            store=store,
            prediction_record_sha256=args.prediction_record_sha256,
            winner_player_id=args.winner_player_id,
            finish_status=args.finish_status,
            settlement_evidence_path=args.settlement_evidence,
            actual_start=args.actual_start,
        )
    elif args.command == "verify":
        result = store.verify()
    else:
        result = store.recover()
    print(_pretty_json(result).decode("utf-8"), end="")


if __name__ == "__main__":
    main()
