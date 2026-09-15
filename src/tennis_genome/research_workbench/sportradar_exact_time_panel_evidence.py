from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from .contracts import WorkbenchRecord
from .sportradar_exact_time_panel import (
    ProviderAccessFailureEvidence,
    SportradarExactTimePanelManifest,
    build_exact_time_panel_manifest,
    parse_season_inventory_bytes,
    verify_season_inventory_integrity,
)
from .sportradar_season_inventory import (
    SportradarSeasonInventory,
    build_sportradar_season_inventory,
)

RECEIPT_ID = "SPORTRADAR-HISTORICAL-EXACT-TIME-PANEL-EVIDENCE-RECEIPT-001"
FINALIZER_PATH = (
    "src/tennis_genome/research_workbench/sportradar_exact_time_panel_evidence.py"
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_FINALIZABLE_ACCESS_STATUSES = frozenset({404, 410})


class RawInventoryEvidenceIdentity(WorkbenchRecord):
    role: Literal[
        "ATP_COMPETITIONS_BY_CATEGORY",
        "WTA_COMPETITIONS_BY_CATEGORY",
        "COMPETITION_SEASONS",
    ]
    binding_id: str
    sha256: str

    def model_post_init(self, __context: object) -> None:
        if not self.binding_id.strip():
            raise ValueError("raw inventory evidence binding_id must be non-empty")
        _require_sha256(self.sha256, field="raw inventory evidence sha256")


class EvidenceBoundExactTimePanelReceipt(WorkbenchRecord):
    receipt_id: Literal[
        "SPORTRADAR-HISTORICAL-EXACT-TIME-PANEL-EVIDENCE-RECEIPT-001"
    ] = RECEIPT_ID
    frozen_inventory: SportradarSeasonInventory
    panel_manifest: SportradarExactTimePanelManifest
    panel_manifest_semantic_sha256: str
    inventory_file_sha256: str
    inventory_semantic_sha256: str
    raw_inventory_evidence: tuple[RawInventoryEvidenceIdentity, ...]
    raw_inventory_evidence_set_sha256: str
    finalizer_code_sha256: str

    def model_post_init(self, __context: object) -> None:
        for field_name, value in (
            ("panel_manifest_semantic_sha256", self.panel_manifest_semantic_sha256),
            ("inventory_file_sha256", self.inventory_file_sha256),
            ("inventory_semantic_sha256", self.inventory_semantic_sha256),
            (
                "raw_inventory_evidence_set_sha256",
                self.raw_inventory_evidence_set_sha256,
            ),
            ("finalizer_code_sha256", self.finalizer_code_sha256),
        ):
            _require_sha256(value, field=field_name)

        verify_season_inventory_integrity(self.frozen_inventory)
        if self.inventory_semantic_sha256 != self.frozen_inventory.semantic_sha256:
            raise ValueError("receipt frozen inventory semantic SHA-256 does not reproduce")
        if self.panel_manifest_semantic_sha256 != self.panel_manifest.semantic_sha256:
            raise ValueError("panel manifest semantic SHA-256 does not reproduce")
        if self.inventory_file_sha256 != self.panel_manifest.inventory_file_sha256:
            raise ValueError("receipt inventory file SHA-256 does not match panel manifest")
        if self.inventory_semantic_sha256 != self.panel_manifest.inventory_semantic_sha256:
            raise ValueError(
                "receipt inventory semantic SHA-256 does not match panel manifest"
            )
        _verify_manifest_has_only_resource_level_access_failures(self.panel_manifest)

        evidence = self.raw_inventory_evidence
        if not evidence:
            raise ValueError("raw inventory evidence set must not be empty")
        keys = [(row.role, row.binding_id) for row in evidence]
        if len(keys) != len(set(keys)):
            raise ValueError("raw inventory evidence identities must be unique")
        expected_order = tuple(sorted(evidence, key=_evidence_sort_key))
        if evidence != expected_order:
            raise ValueError("raw inventory evidence identities are not canonically ordered")

        atp_rows = [
            row for row in evidence if row.role == "ATP_COMPETITIONS_BY_CATEGORY"
        ]
        wta_rows = [
            row for row in evidence if row.role == "WTA_COMPETITIONS_BY_CATEGORY"
        ]
        if len(atp_rows) != 1 or atp_rows[0].binding_id != "sr:category:3":
            raise ValueError("receipt requires exactly the ATP category 3 catalog identity")
        if len(wta_rows) != 1 or wta_rows[0].binding_id != "sr:category:6":
            raise ValueError("receipt requires exactly the WTA category 6 catalog identity")
        if atp_rows[0].sha256 != self.frozen_inventory.atp_competitions_sha256:
            raise ValueError("ATP raw evidence identity does not match frozen inventory")
        if wta_rows[0].sha256 != self.frozen_inventory.wta_competitions_sha256:
            raise ValueError("WTA raw evidence identity does not match frozen inventory")

        expected_seasons = {
            row.competition_id: row.payload_sha256
            for row in self.frozen_inventory.season_catalogs
        }
        observed_seasons = {
            row.binding_id: row.sha256
            for row in evidence
            if row.role == "COMPETITION_SEASONS"
        }
        if observed_seasons != expected_seasons:
            raise ValueError(
                "Competition Seasons raw evidence identities do not match frozen inventory"
            )

        expected_set_sha = hashlib.sha256(
            _canonical_json([row.canonical_payload() for row in evidence])
        ).hexdigest()
        if self.raw_inventory_evidence_set_sha256 != expected_set_sha:
            raise ValueError("raw inventory evidence-set SHA-256 does not reproduce")


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _require_sha256(value: str, *, field: str) -> None:
    if not _SHA256_RE.fullmatch(value):
        raise ValueError(f"{field} must be a lowercase SHA-256")


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _aware_time(value: str, *, field: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return parsed.astimezone(UTC)


def _evidence_sort_key(row: RawInventoryEvidenceIdentity) -> tuple[int, str]:
    role_order = {
        "ATP_COMPETITIONS_BY_CATEGORY": 0,
        "WTA_COMPETITIONS_BY_CATEGORY": 1,
        "COMPETITION_SEASONS": 2,
    }
    return role_order[row.role], row.binding_id


def _strict_json_object(content: bytes, *, label: str) -> dict[str, object]:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{label} must be UTF-8 JSON") from exc

    def reject_nonfinite(value: str) -> None:
        raise ValueError(f"non-finite JSON constant is forbidden: {value}")

    try:
        payload = json.loads(text, parse_constant=reject_nonfinite)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def _validate_finalizable_access_failures(
    access_failures: dict[str, ProviderAccessFailureEvidence],
) -> None:
    """Reject authentication/configuration failures as season-level negative evidence."""

    for season_id, evidence in access_failures.items():
        if evidence.season_id != season_id:
            raise ValueError("access-failure dictionary key does not match evidence season ID")
        if evidence.http_status not in _FINALIZABLE_ACCESS_STATUSES:
            raise ValueError(
                "authentication/authorization or transient HTTP failures do not finalize "
                f"historical season {season_id}; only retained 404/410 resource responses "
                "may finalize HISTORY_NOT_AVAILABLE"
            )
        if evidence.failure_class != "HISTORY_NOT_AVAILABLE":
            raise ValueError(
                "only HISTORY_NOT_AVAILABLE may finalize an evidence-bound historical panel"
            )


def _verify_manifest_has_only_resource_level_access_failures(
    manifest: SportradarExactTimePanelManifest,
) -> None:
    for row in manifest.rows:
        if row.disposition != "ACCESS_FAILURE":
            continue
        if row.failure_reasons != ("HISTORY_NOT_AVAILABLE",):
            raise ValueError(
                "evidence-bound panel receipts reject authentication/authorization access "
                "failures; ACCESS_FAILURE must be resource-level HISTORY_NOT_AVAILABLE"
            )


def verify_inventory_against_raw_provider_evidence(
    *,
    inventory_content: bytes,
    atp_competitions_path: Path,
    wta_competitions_path: Path,
    season_response_paths: dict[str, Path],
) -> SportradarSeasonInventory:
    """Re-derive the frozen inventory from retained provider bytes and require equality."""

    inventory = parse_season_inventory_bytes(inventory_content)
    verify_season_inventory_integrity(inventory)
    rebuilt = build_sportradar_season_inventory(
        atp_competitions_path=atp_competitions_path,
        wta_competitions_path=wta_competitions_path,
        season_response_paths=season_response_paths,
        snapshot_at=_aware_time(inventory.snapshot_at, field="inventory.snapshot_at"),
    )
    if rebuilt.canonical_payload() != inventory.canonical_payload():
        raise ValueError(
            "frozen season inventory does not exactly re-derive from retained provider "
            f"evidence; supplied={inventory.semantic_sha256}, "
            f"rederived={rebuilt.semantic_sha256}"
        )
    return inventory


def _raw_evidence_identities(
    *,
    inventory: SportradarSeasonInventory,
    atp_competitions_path: Path,
    wta_competitions_path: Path,
    season_response_paths: dict[str, Path],
) -> tuple[RawInventoryEvidenceIdentity, ...]:
    rows = [
        RawInventoryEvidenceIdentity(
            role="ATP_COMPETITIONS_BY_CATEGORY",
            binding_id="sr:category:3",
            sha256=_file_sha256(atp_competitions_path),
        ),
        RawInventoryEvidenceIdentity(
            role="WTA_COMPETITIONS_BY_CATEGORY",
            binding_id="sr:category:6",
            sha256=_file_sha256(wta_competitions_path),
        ),
    ]
    rows.extend(
        RawInventoryEvidenceIdentity(
            role="COMPETITION_SEASONS",
            binding_id=competition_id,
            sha256=_file_sha256(path),
        )
        for competition_id, path in sorted(season_response_paths.items())
    )
    evidence = tuple(sorted(rows, key=_evidence_sort_key))

    if evidence[0].sha256 != inventory.atp_competitions_sha256:
        raise ValueError("ATP raw inventory evidence changed during finalization")
    if evidence[1].sha256 != inventory.wta_competitions_sha256:
        raise ValueError("WTA raw inventory evidence changed during finalization")
    expected_season_hashes = {
        row.competition_id: row.payload_sha256 for row in inventory.season_catalogs
    }
    observed_season_hashes = {
        row.binding_id: row.sha256
        for row in evidence
        if row.role == "COMPETITION_SEASONS"
    }
    if observed_season_hashes != expected_season_hashes:
        raise ValueError("Competition Seasons raw evidence changed during finalization")
    return evidence


def build_evidence_bound_exact_time_panel_receipt(
    *,
    inventory_content: bytes,
    atp_competitions_path: Path,
    wta_competitions_path: Path,
    season_response_paths: dict[str, Path],
    admitted_audits: dict[str, bytes],
    failed_audits: dict[str, bytes],
    access_failures: dict[str, ProviderAccessFailureEvidence],
    repo_root: Path,
) -> EvidenceBoundExactTimePanelReceipt:
    inventory = verify_inventory_against_raw_provider_evidence(
        inventory_content=inventory_content,
        atp_competitions_path=atp_competitions_path,
        wta_competitions_path=wta_competitions_path,
        season_response_paths=season_response_paths,
    )
    evidence = _raw_evidence_identities(
        inventory=inventory,
        atp_competitions_path=atp_competitions_path,
        wta_competitions_path=wta_competitions_path,
        season_response_paths=season_response_paths,
    )
    _validate_finalizable_access_failures(access_failures)
    manifest = build_exact_time_panel_manifest(
        inventory_content=inventory_content,
        admitted_audits=admitted_audits,
        failed_audits=failed_audits,
        access_failures=access_failures,
        repo_root=repo_root,
    )
    evidence_set_sha = hashlib.sha256(
        _canonical_json([row.canonical_payload() for row in evidence])
    ).hexdigest()
    finalizer_path = repo_root / FINALIZER_PATH
    if not finalizer_path.is_file():
        raise ValueError(f"required evidence finalizer code file is missing: {FINALIZER_PATH}")
    return EvidenceBoundExactTimePanelReceipt(
        frozen_inventory=inventory,
        panel_manifest=manifest,
        panel_manifest_semantic_sha256=manifest.semantic_sha256,
        inventory_file_sha256=hashlib.sha256(inventory_content).hexdigest(),
        inventory_semantic_sha256=inventory.semantic_sha256,
        raw_inventory_evidence=evidence,
        raw_inventory_evidence_set_sha256=evidence_set_sha,
        finalizer_code_sha256=_file_sha256(finalizer_path),
    )


def _parse_path_binding(value: str, *, option: str) -> tuple[str, Path]:
    binding_id, separator, raw_path = value.partition("::")
    if not separator or not binding_id.strip() or not raw_path.strip():
        raise argparse.ArgumentTypeError(f"{option} must be ID::PATH")
    return binding_id.strip(), Path(raw_path)


def _load_bound_bytes(values: list[str], *, option: str) -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    for value in values:
        binding_id, path = _parse_path_binding(value, option=option)
        if binding_id in result:
            raise ValueError(f"duplicate {option} binding for {binding_id}")
        result[binding_id] = path.read_bytes()
    return result


def _load_season_paths(values: list[str]) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for value in values:
        competition_id, path = _parse_path_binding(value, option="--seasons")
        if competition_id in result:
            raise ValueError(f"duplicate --seasons binding for {competition_id}")
        result[competition_id] = path
    return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Finalize a Sportradar exact-time panel only after re-deriving its frozen "
            "inventory from retained raw provider evidence"
        )
    )
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--atp-competitions", required=True, type=Path)
    parser.add_argument("--wta-competitions", required=True, type=Path)
    parser.add_argument(
        "--seasons",
        action="append",
        required=True,
        help="retained Competition Seasons binding COMPETITION_ID::RAW_JSON; repeat",
    )
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--admitted-audit", action="append", default=[])
    parser.add_argument("--failed-audit", action="append", default=[])
    parser.add_argument(
        "--access-failure",
        action="append",
        default=[],
        help=(
            "self-contained ProviderAccessFailureEvidence JSON for a retained 404/410 "
            "resource response; repeat"
        ),
    )
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    inventory_content = args.inventory.read_bytes()
    season_paths = _load_season_paths(args.seasons)
    admitted = _load_bound_bytes(args.admitted_audit, option="--admitted-audit")
    failed = _load_bound_bytes(args.failed_audit, option="--failed-audit")
    access: dict[str, ProviderAccessFailureEvidence] = {}
    for path_text in args.access_failure:
        path = Path(path_text)
        payload = _strict_json_object(path.read_bytes(), label="access failure evidence")
        evidence = ProviderAccessFailureEvidence.model_validate(payload)
        if evidence.season_id in access:
            raise ValueError(f"duplicate access-failure evidence for {evidence.season_id}")
        access[evidence.season_id] = evidence

    receipt = build_evidence_bound_exact_time_panel_receipt(
        inventory_content=inventory_content,
        atp_competitions_path=args.atp_competitions,
        wta_competitions_path=args.wta_competitions,
        season_response_paths=season_paths,
        admitted_audits=admitted,
        failed_audits=failed,
        access_failures=access,
        repo_root=args.repo_root,
    )
    rendered = json.dumps(
        receipt.canonical_payload(), indent=2, sort_keys=True, ensure_ascii=False
    ) + "\n"
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
