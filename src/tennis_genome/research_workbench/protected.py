from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from .exposure import ExposureGraph, ExposureKind, ExposureRecord


@dataclass(frozen=True)
class ProtectedDatasetReference:
    """Opaque identity for one protected outcome population."""

    dataset_id: str
    protected_source_id: str
    content_sha256: str

    def validate(self) -> None:
        if not self.dataset_id.strip() or not self.protected_source_id.strip():
            raise ValueError("protected dataset identifiers must be nonblank")
        if len(self.content_sha256) != 64 or any(
            ch not in "0123456789abcdef" for ch in self.content_sha256
        ):
            raise ValueError("protected dataset content_sha256 must be lowercase SHA-256")


@dataclass(frozen=True)
class ProtectedOpenAuthorization:
    """Explicit authority to consume one protected dataset."""

    evaluation_id: str
    procedure_ids: tuple[str, ...]
    purpose: str
    human_approver: str
    capability: str

    def validate(self) -> None:
        if not self.evaluation_id.strip():
            raise ValueError("evaluation_id is required")
        if not self.procedure_ids or any(not item.strip() for item in self.procedure_ids):
            raise ValueError("procedure_ids must contain nonblank procedure identities")
        if len(set(self.procedure_ids)) != len(self.procedure_ids):
            raise ValueError("procedure_ids must be unique")
        if not self.purpose.strip() or not self.human_approver.strip():
            raise ValueError("purpose and human_approver are required")
        if not self.capability:
            raise ValueError("capability is required")


@dataclass(frozen=True)
class ProtectedOpenReceipt:
    schema_version: str
    dataset_id: str
    protected_source_id: str
    content_sha256: str
    evaluation_id: str
    procedure_ids: tuple[str, ...]
    purpose: str
    human_approver: str
    opened_at_utc: str
    irreversible: bool
    boundary_status: str

    @property
    def exposure_id(self) -> str:
        payload = json.dumps(
            asdict(self),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return "protected-open:" + hashlib.sha256(payload).hexdigest()

    def to_exposure_record(self) -> ExposureRecord:
        return ExposureRecord(
            exposure_id=self.exposure_id,
            actor=self.human_approver,
            source_ids=(self.protected_source_id,),
            information_kinds=(
                ExposureKind.RAW_OUTCOMES,
                ExposureKind.PROTECTED_RESULT,
            ),
            description=(
                "Protected population was irreversibly opened for evaluation "
                f"{self.evaluation_id}: {self.purpose}"
            ),
            decision_ids=self.procedure_ids,
        )


class ProtectedDataVault:
    """Fail-closed single-use access to protected outcome bytes.

    This class deliberately refuses to pretend that a same-user directory is a hard
    scientific boundary. Bytes are never released unless deployment attests that the
    vault is controlled by a separate OS/credential principal.

    The irreversible claim is created *before* bytes are read. If a process crashes or
    the content hash fails after claiming access, the population remains burned rather
    than becoming replayable.
    """

    def __init__(
        self,
        *,
        vault_root: Path,
        audit_root: Path,
        capability_sha256: str,
        separate_principal: bool,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        if len(capability_sha256) != 64 or any(
            ch not in "0123456789abcdef" for ch in capability_sha256
        ):
            raise ValueError("capability_sha256 must be lowercase SHA-256")
        self._vault_root = Path(vault_root)
        self._audit_root = Path(audit_root)
        self._capability_sha256 = capability_sha256
        self._separate_principal = separate_principal
        self._now = now or (lambda: datetime.now(UTC))

    @property
    def boundary_status(self) -> str:
        return (
            "OS_CREDENTIAL_ENFORCED"
            if self._separate_principal
            else "NOT_PHYSICALLY_ENFORCED"
        )

    def _claim_path(self, dataset_id: str) -> Path:
        digest = hashlib.sha256(dataset_id.encode("utf-8")).hexdigest()
        return self._audit_root / f"{digest}.burn.json"

    def _dataset_path(self, dataset_id: str) -> Path:
        digest = hashlib.sha256(dataset_id.encode("utf-8")).hexdigest()
        return self._vault_root / f"{digest}.holdout"

    def open_once(
        self,
        *,
        reference: ProtectedDatasetReference,
        authorization: ProtectedOpenAuthorization,
        exposure_graph: ExposureGraph,
    ) -> tuple[bytes, ProtectedOpenReceipt]:
        reference.validate()
        authorization.validate()
        if not self._separate_principal:
            raise PermissionError(
                "protected access refused: separate OS/credential principal "
                "is not established"
            )

        supplied = hashlib.sha256(authorization.capability.encode("utf-8")).hexdigest()
        if not hmac.compare_digest(supplied, self._capability_sha256):
            raise PermissionError("protected access refused: invalid authorization capability")

        opened_at = self._now()
        if opened_at.tzinfo is None or opened_at.utcoffset() is None:
            raise RuntimeError("protected vault clock must return a timezone-aware datetime")
        opened_at = opened_at.astimezone(UTC)
        receipt = ProtectedOpenReceipt(
            schema_version="tennis-workbench-protected-open-v1",
            dataset_id=reference.dataset_id,
            protected_source_id=reference.protected_source_id,
            content_sha256=reference.content_sha256,
            evaluation_id=authorization.evaluation_id,
            procedure_ids=authorization.procedure_ids,
            purpose=authorization.purpose,
            human_approver=authorization.human_approver,
            opened_at_utc=opened_at.isoformat(),
            irreversible=True,
            boundary_status=self.boundary_status,
        )

        self._audit_root.mkdir(parents=True, exist_ok=True)
        claim_path = self._claim_path(reference.dataset_id)
        encoded_receipt = (
            json.dumps(
                asdict(receipt),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            )
            + "\n"
        ).encode("utf-8")
        try:
            fd = os.open(claim_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise PermissionError(
                "protected population was already opened or claimed; access is irreversible"
            ) from exc
        try:
            os.write(fd, encoded_receipt)
            os.fsync(fd)
        finally:
            os.close(fd)

        dataset_path = self._dataset_path(reference.dataset_id)
        content = dataset_path.read_bytes()
        observed_sha256 = hashlib.sha256(content).hexdigest()
        if not hmac.compare_digest(observed_sha256, reference.content_sha256):
            raise PermissionError(
                "protected content hash mismatch after irreversible burn; population "
                "must not be reused"
            )

        exposure = receipt.to_exposure_record()
        exposure_graph.add(exposure)
        return content, receipt


def write_protected_dataset(
    *,
    vault_root: Path,
    reference: ProtectedDatasetReference,
    content: bytes,
) -> Path:
    """Administrative helper for staging protected bytes before research access.

    It refuses replacement. Creation of protected bytes and research-time opening are
    intentionally separate capabilities.
    """

    reference.validate()
    observed_sha256 = hashlib.sha256(content).hexdigest()
    if not hmac.compare_digest(observed_sha256, reference.content_sha256):
        raise ValueError("protected dataset bytes do not match reference content_sha256")
    vault_root = Path(vault_root)
    vault_root.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(reference.dataset_id.encode("utf-8")).hexdigest()
    path = vault_root / f"{digest}.holdout"
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise FileExistsError("protected dataset already staged; replacement is forbidden") from exc
    try:
        os.write(fd, content)
        os.fsync(fd)
    finally:
        os.close(fd)
    return path
