from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path

import pytest

from tennis_genome.research_workbench import (
    ExposureGraph,
    ProtectedDataVault,
    ProtectedDatasetReference,
    ProtectedOpenAuthorization,
    write_protected_dataset,
)


def _reference(content: bytes) -> ProtectedDatasetReference:
    return ProtectedDatasetReference(
        dataset_id="future-holdout-001",
        protected_source_id="protected:future-holdout-001",
        content_sha256=hashlib.sha256(content).hexdigest(),
    )


def _authorization(capability: str = "correct-secret") -> ProtectedOpenAuthorization:
    return ProtectedOpenAuthorization(
        evaluation_id="eval-protected-001",
        procedure_ids=("proc-a", "proc-b"),
        purpose="single registered protected comparison",
        human_approver="independent-reviewer",
        capability=capability,
    )


def _vault(
    tmp_path: Path,
    *,
    capability: str = "correct-secret",
    separate_principal: bool = True,
) -> ProtectedDataVault:
    return ProtectedDataVault(
        vault_root=tmp_path / "vault",
        audit_root=tmp_path / "audit",
        capability_sha256=hashlib.sha256(capability.encode("utf-8")).hexdigest(),
        separate_principal=separate_principal,
        now=lambda: datetime(2026, 10, 1, 12, 0, tzinfo=UTC),
    )


def test_vault_refuses_to_fake_physical_boundary(tmp_path: Path) -> None:
    content = b'{"outcomes":[1,0]}\n'
    reference = _reference(content)
    write_protected_dataset(
        vault_root=tmp_path / "vault",
        reference=reference,
        content=content,
    )
    vault = _vault(tmp_path, separate_principal=False)

    assert vault.boundary_status == "NOT_PHYSICALLY_ENFORCED"
    with pytest.raises(PermissionError, match="separate OS/credential principal"):
        vault.open_once(
            reference=reference,
            authorization=_authorization(),
            exposure_graph=ExposureGraph(),
        )


def test_open_once_burns_before_release_and_registers_exposure(tmp_path: Path) -> None:
    content = b'{"outcomes":[1,0]}\n'
    reference = _reference(content)
    write_protected_dataset(
        vault_root=tmp_path / "vault",
        reference=reference,
        content=content,
    )
    vault = _vault(tmp_path)
    graph = ExposureGraph()

    opened, receipt = vault.open_once(
        reference=reference,
        authorization=_authorization(),
        exposure_graph=graph,
    )

    assert opened == content
    assert receipt.irreversible is True
    assert receipt.boundary_status == "OS_CREDENTIAL_ENFORCED"
    exposure = graph.get(receipt.exposure_id)
    assert exposure.source_ids == ("protected:future-holdout-001",)
    assert exposure.decision_ids == ("proc-a", "proc-b")

    burn_files = list((tmp_path / "audit").glob("*.burn.json"))
    assert len(burn_files) == 1
    retained = json.loads(burn_files[0].read_text(encoding="utf-8"))
    assert retained["dataset_id"] == reference.dataset_id
    assert retained["irreversible"] is True

    with pytest.raises(PermissionError, match="already opened or claimed"):
        vault.open_once(
            reference=reference,
            authorization=_authorization(),
            exposure_graph=graph,
        )


def test_bad_capability_does_not_consume_holdout(tmp_path: Path) -> None:
    content = b'{"outcomes":[1,0]}\n'
    reference = _reference(content)
    write_protected_dataset(
        vault_root=tmp_path / "vault",
        reference=reference,
        content=content,
    )
    vault = _vault(tmp_path)

    with pytest.raises(PermissionError, match="invalid authorization capability"):
        vault.open_once(
            reference=reference,
            authorization=_authorization("wrong-secret"),
            exposure_graph=ExposureGraph(),
        )

    assert not (tmp_path / "audit").exists()


def test_hash_mismatch_after_claim_remains_irreversibly_burned(tmp_path: Path) -> None:
    content = b'{"outcomes":[1,0]}\n'
    reference = _reference(content)
    path = write_protected_dataset(
        vault_root=tmp_path / "vault",
        reference=reference,
        content=content,
    )
    path.write_bytes(b'{"outcomes":[0,0]}\n')
    vault = _vault(tmp_path)

    with pytest.raises(PermissionError, match="hash mismatch after irreversible burn"):
        vault.open_once(
            reference=reference,
            authorization=_authorization(),
            exposure_graph=ExposureGraph(),
        )

    burn_files = list((tmp_path / "audit").glob("*.burn.json"))
    assert len(burn_files) == 1
    with pytest.raises(PermissionError, match="already opened or claimed"):
        vault.open_once(
            reference=reference,
            authorization=_authorization(),
            exposure_graph=ExposureGraph(),
        )


def test_staging_rejects_wrong_bytes_and_replacement(tmp_path: Path) -> None:
    content = b'{"outcomes":[1,0]}\n'
    reference = _reference(content)

    with pytest.raises(ValueError, match="do not match"):
        write_protected_dataset(
            vault_root=tmp_path / "vault",
            reference=reference,
            content=b"different",
        )

    write_protected_dataset(
        vault_root=tmp_path / "vault",
        reference=reference,
        content=content,
    )
    with pytest.raises(FileExistsError, match="replacement is forbidden"):
        write_protected_dataset(
            vault_root=tmp_path / "vault",
            reference=reference,
            content=content,
        )


def test_exposure_generated_by_open_blocks_fresh_confirmation(tmp_path: Path) -> None:
    content = b'{"outcomes":[1,0]}\n'
    reference = _reference(content)
    write_protected_dataset(
        vault_root=tmp_path / "vault",
        reference=reference,
        content=content,
    )
    vault = _vault(tmp_path)
    graph = ExposureGraph()
    _, receipt = vault.open_once(
        reference=reference,
        authorization=_authorization(),
        exposure_graph=graph,
    )

    with pytest.raises(ValueError, match="not independent"):
        graph.assert_independent(
            exposure_ids=(receipt.exposure_id,),
            protected_source_ids=("protected:future-holdout-001",),
        )
