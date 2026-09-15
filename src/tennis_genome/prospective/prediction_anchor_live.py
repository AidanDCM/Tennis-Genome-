from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from tennis_genome.prospective.pilot import ProspectivePilotStore, attest_anchor
from tennis_genome.prospective.prediction_anchor_github import (
    GitHubGetBytes,
    LivePredictionAnchorEvidence,
    fetch_authenticated_prediction_anchor_evidence,
    validate_retained_prediction_anchor_evidence,
)

LIVE_PREDICTION_ANCHOR_VERSION = "FULL-STACK-PILOT-001-live-anchor-store-v1"
LIVE_PREDICTION_ANCHOR_MODE = "LIVE_GITHUB_PREDICTION_LEDGER_V1"
_ZERO_SHA256 = "0" * 64


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


def _require_sha256(value: object, *, field: str) -> str:
    text = str(value if value is not None else "").strip()
    if len(text) != 64 or any(char not in "0123456789abcdef" for char in text):
        raise ValueError(f"{field} must be lowercase SHA-256")
    return text


def _record_sha256(unsigned: dict[str, object]) -> str:
    return _sha256_bytes(_canonical_json(unsigned))


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


def _prediction_record(
    pilot_store: ProspectivePilotStore,
    prediction_sha256: str,
) -> dict[str, object]:
    record = pilot_store.find_record(prediction_sha256)
    if record.get("record_type") != "PREDICTION_COMMIT":
        raise ValueError("live prediction anchor must reference a prediction commit")
    return record


def _same_commitment(
    retained: LivePredictionAnchorEvidence,
    current: LivePredictionAnchorEvidence,
) -> bool:
    return (
        retained.comment_id == current.comment_id
        and retained.workflow_run_id == current.workflow_run_id
        and retained.anchor_created_at == current.anchor_created_at
        and retained.workflow_source_sha == current.workflow_source_sha
        and _canonical_json(retained.receipt) == _canonical_json(current.receipt)
    )


class LivePredictionAnchorStore:
    """Append-only sidecar proving pilot anchors came from live GitHub server state."""

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
            raise RuntimeError("live prediction anchor store is locked") from exc
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
                value = json.loads(path.read_text(encoding="utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError(f"live prediction anchor record is invalid: {path.name}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"live prediction anchor record is not an object: {path.name}")
            records.append(value)
        return records

    def _store_evidence(self, payload: bytes) -> str:
        digest = _sha256_bytes(payload)
        target = self.evidence_dir / digest
        if target.exists():
            if target.read_bytes() != payload:
                raise RuntimeError(f"live prediction anchor evidence collision: {digest}")
            return digest
        _atomic_write(target, payload)
        return digest

    def _append(self, payload: dict[str, object]) -> dict[str, object]:
        records = self.records()
        previous = _ZERO_SHA256 if not records else str(records[-1]["record_sha256"])
        unsigned = dict(payload)
        unsigned["live_prediction_anchor_version"] = LIVE_PREDICTION_ANCHOR_VERSION
        unsigned["sequence"] = len(records) + 1
        unsigned["previous_record_sha256"] = previous
        digest = _record_sha256(unsigned)
        record = {**unsigned, "record_sha256": digest}
        name = f"{len(records) + 1:08d}-{digest}.json"
        _atomic_write(self.records_dir / name, _pretty_json(record))
        return record

    def verify(
        self,
        *,
        pilot_store: ProspectivePilotStore,
        github_get_bytes: GitHubGetBytes | None = None,
        revalidate_live: bool = True,
    ) -> dict[str, object]:
        pilot_report = pilot_store.verify()
        paths = self._record_paths()
        records = self.records()
        previous = _ZERO_SHA256
        prediction_shas: set[str] = set()
        comment_ids: set[int] = set()
        run_ids: set[int] = set()

        pilot_anchors = {
            str(record.get("prediction_record_sha256")): record
            for record in pilot_store.records()
            if record.get("record_type") == "ANCHOR_ATTESTATION"
        }

        for sequence, record in enumerate(records, start=1):
            if record.get("live_prediction_anchor_version") != LIVE_PREDICTION_ANCHOR_VERSION:
                raise ValueError(f"unexpected live prediction anchor version at {sequence}")
            if record.get("record_type") != "LIVE_PREDICTION_ANCHOR":
                raise ValueError(f"unexpected live prediction anchor type at {sequence}")
            if record.get("anchor_evidence_mode") != LIVE_PREDICTION_ANCHOR_MODE:
                raise ValueError("prediction anchor is not promotion-capable live evidence")
            if int(record.get("sequence", -1)) != sequence:
                raise ValueError(f"live prediction anchor sequence gap at {sequence}")

            observed_sha = _require_sha256(
                record.get("record_sha256"),
                field=f"live_prediction_anchor[{sequence}].record_sha256",
            )
            unsigned = dict(record)
            unsigned.pop("record_sha256", None)
            if _record_sha256(unsigned) != observed_sha:
                raise ValueError(f"live prediction anchor digest mismatch at {sequence}")
            if record.get("previous_record_sha256") != previous:
                raise ValueError(f"live prediction anchor chain mismatch at {sequence}")
            expected_name = f"{sequence:08d}-{observed_sha}.json"
            if paths[sequence - 1].name != expected_name:
                raise ValueError(f"live prediction anchor filename mismatch at {sequence}")

            prediction_sha = _require_sha256(
                record.get("prediction_record_sha256"),
                field="prediction_record_sha256",
            )
            _prediction_record(pilot_store, prediction_sha)
            comment_id = int(record.get("github_comment_id", -1))
            run_id = int(record.get("workflow_run_id", -1))
            if comment_id <= 0 or run_id <= 0:
                raise ValueError("live prediction anchor GitHub identities must be positive")
            comment_sha = _require_sha256(
                record.get("github_comment_response_sha256"),
                field="github_comment_response_sha256",
            )
            run_sha = _require_sha256(
                record.get("workflow_run_response_sha256"),
                field="workflow_run_response_sha256",
            )
            if record.get("evidence_sha256") != [comment_sha, run_sha]:
                raise ValueError("live prediction anchor evidence manifest mismatch")
            for digest in (comment_sha, run_sha):
                evidence_path = self.evidence_dir / digest
                if not evidence_path.is_file():
                    raise ValueError(f"missing live prediction anchor evidence {digest}")
                if _sha256_file(evidence_path) != digest:
                    raise ValueError(f"live prediction anchor evidence digest mismatch: {digest}")

            comment_bytes = (self.evidence_dir / comment_sha).read_bytes()
            run_bytes = (self.evidence_dir / run_sha).read_bytes()
            retained = validate_retained_prediction_anchor_evidence(
                comment_response_bytes=comment_bytes,
                workflow_run_response_bytes=run_bytes,
                expected_prediction_sha256=prediction_sha,
            )
            if retained.comment_id != comment_id or retained.workflow_run_id != run_id:
                raise ValueError("retained prediction anchor GitHub identity does not reproduce")
            if record.get("anchor_created_at") != retained.anchor_created_at.isoformat():
                raise ValueError("retained prediction anchor time does not reproduce")
            if record.get("workflow_source_sha") != retained.workflow_source_sha:
                raise ValueError("retained prediction anchor source SHA does not reproduce")

            pilot_anchor = pilot_anchors.get(prediction_sha)
            if pilot_anchor is None:
                raise ValueError("live prediction anchor lacks corresponding pilot attestation")
            if int(pilot_anchor.get("workflow_run_id", -1)) != run_id:
                raise ValueError("pilot/live prediction anchor workflow run differs")
            if pilot_anchor.get("anchor_created_at") != retained.anchor_created_at.isoformat():
                raise ValueError("pilot/live prediction anchor timestamp differs")

            if revalidate_live:
                current = fetch_authenticated_prediction_anchor_evidence(
                    comment_id=comment_id,
                    expected_prediction_sha256=prediction_sha,
                    get_bytes=github_get_bytes,
                )
                if not _same_commitment(retained, current):
                    raise ValueError("live GitHub prediction commitment differs from retained evidence")

            if prediction_sha in prediction_shas:
                raise ValueError("prediction has more than one live anchor")
            if comment_id in comment_ids:
                raise ValueError("GitHub prediction comment is reused")
            if run_id in run_ids:
                raise ValueError("GitHub prediction workflow run is reused")
            prediction_shas.add(prediction_sha)
            comment_ids.add(comment_id)
            run_ids.add(run_id)
            previous = observed_sha

        eligible = 0
        for record in pilot_store.records():
            if record.get("record_type") != "SETTLEMENT":
                continue
            if not bool(record.get("primary_evaluation_eligible")):
                continue
            prediction_sha = str(record.get("prediction_record_sha256", ""))
            if prediction_sha not in prediction_shas:
                raise ValueError(
                    "primary-evaluation settlement lacks trusted live prediction anchor"
                )
            eligible += 1

        return {
            "live_prediction_anchor_version": LIVE_PREDICTION_ANCHOR_VERSION,
            "pilot_chain_head_sha256": pilot_report["chain_head_sha256"],
            "record_count": len(records),
            "trusted_prediction_count": len(prediction_shas),
            "promotion_eligible_settlement_count": eligible,
            "chain_head_sha256": previous,
            "revalidated_live": revalidate_live,
            "status": "LIVE_VERIFIED" if revalidate_live else "RETAINED_VERIFIED",
        }


def attest_live_prediction_anchor(
    *,
    pilot_store: ProspectivePilotStore,
    live_store: LivePredictionAnchorStore,
    prediction_record_sha256: str,
    github_comment_id: int,
    github_get_bytes: GitHubGetBytes | None = None,
) -> dict[str, object]:
    """Authenticate GitHub first, append pilot attestation, then retain exact server evidence."""

    with live_store.write_lock():
        live_store.verify(
            pilot_store=pilot_store,
            github_get_bytes=github_get_bytes,
            revalidate_live=True,
        )
        pilot_report = pilot_store.verify()
        prediction = _prediction_record(pilot_store, prediction_record_sha256)
        if pilot_report.get("chain_head_sha256") != prediction_record_sha256:
            raise ValueError("live anchor may only attest current pilot prediction chain head")
        if any(
            str(record.get("prediction_record_sha256")) == prediction_record_sha256
            for record in live_store.records()
        ):
            raise ValueError("prediction already has a trusted live anchor")

        evidence = fetch_authenticated_prediction_anchor_evidence(
            comment_id=github_comment_id,
            expected_prediction_sha256=prediction_record_sha256,
            get_bytes=github_get_bytes,
        )
        if evidence.receipt.get("chain_head_sha256") != prediction_record_sha256:
            raise ValueError("GitHub prediction anchor does not attest current pilot head")

        with tempfile.TemporaryDirectory() as temp_dir:
            receipt_path = Path(temp_dir) / "anchor-receipt.json"
            run_path = Path(temp_dir) / "workflow-run.json"
            receipt_path.write_bytes(_pretty_json(evidence.receipt))
            run_path.write_bytes(evidence.workflow_run_response_bytes)
            pilot_anchor = attest_anchor(
                store=pilot_store,
                prediction_record_sha256=prediction_record_sha256,
                anchor_receipt_path=receipt_path,
                github_run_metadata_path=run_path,
            )

        comment_sha = live_store._store_evidence(evidence.comment_response_bytes)
        run_sha = live_store._store_evidence(evidence.workflow_run_response_bytes)
        live_record = live_store._append(
            {
                "record_type": "LIVE_PREDICTION_ANCHOR",
                "anchor_evidence_mode": LIVE_PREDICTION_ANCHOR_MODE,
                "prediction_record_sha256": prediction_record_sha256,
                "prediction_id": prediction["prediction_id"],
                "match_id": prediction["match_id"],
                "tour": prediction["tour"],
                "pilot_anchor_record_sha256": pilot_anchor["record_sha256"],
                "github_comment_id": evidence.comment_id,
                "workflow_run_id": evidence.workflow_run_id,
                "workflow_source_sha": evidence.workflow_source_sha,
                "anchor_created_at": evidence.anchor_created_at.isoformat(),
                "github_comment_response_sha256": comment_sha,
                "workflow_run_response_sha256": run_sha,
                "evidence_sha256": [comment_sha, run_sha],
            }
        )
        return live_record


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Promotion-capable live GitHub anchor layer for FULL-STACK-PILOT-001"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    attest = subparsers.add_parser("attest")
    attest.add_argument("--pilot-store", required=True, type=Path)
    attest.add_argument("--live-store", required=True, type=Path)
    attest.add_argument("--prediction-record-sha256", required=True)
    attest.add_argument("--github-comment-id", required=True, type=int)
    verify = subparsers.add_parser("verify")
    verify.add_argument("--pilot-store", required=True, type=Path)
    verify.add_argument("--live-store", required=True, type=Path)
    verify.add_argument("--retained-only", action="store_true")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    pilot_store = ProspectivePilotStore(args.pilot_store)
    live_store = LivePredictionAnchorStore(args.live_store)
    if args.command == "attest":
        result = attest_live_prediction_anchor(
            pilot_store=pilot_store,
            live_store=live_store,
            prediction_record_sha256=args.prediction_record_sha256,
            github_comment_id=args.github_comment_id,
        )
    else:
        result = live_store.verify(
            pilot_store=pilot_store,
            revalidate_live=not args.retained_only,
        )
    print(_pretty_json(result).decode("utf-8"), end="")


if __name__ == "__main__":
    main()
