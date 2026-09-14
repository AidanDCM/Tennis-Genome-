from __future__ import annotations

import hashlib
import json

from tennis_genome.prospective.pilot import ProspectivePilotStore

PACKET_SCHEMA = "full-stack-pilot-anchor-packet-v1"
REPOSITORY = "AidanDCM/Tennis-Genome-"
WORKFLOW_PATH = ".github/workflows/prospective_evidence_anchor.yml"
WORKFLOW_NAME = "Prospective Evidence Anchor"
INPUT_FIELDS = ("prediction_record_sha256", "chain_head_sha256")


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def build_prediction_anchor_packet(
    *,
    store: ProspectivePilotStore,
    prediction_record_sha256: str | None = None,
) -> dict[str, object]:
    """Build exact workflow inputs for the current verified prediction ledger head."""

    report = store.verify()
    records = store.records()
    if not records:
        raise ValueError("prospective pilot store has no retained records")

    if prediction_record_sha256 is None:
        record = records[-1]
    else:
        matches = [
            record
            for record in records
            if str(record.get("record_sha256", "")) == prediction_record_sha256
        ]
        if len(matches) != 1:
            raise ValueError("requested prediction record SHA was not found exactly once")
        record = matches[0]

    if record.get("record_type") != "PREDICTION_COMMIT":
        raise ValueError("prediction anchor packet requires a PREDICTION_COMMIT record")

    prediction_sha = str(record.get("record_sha256", ""))
    chain_head = str(report.get("chain_head_sha256", ""))
    if prediction_sha != chain_head:
        raise ValueError(
            "prediction anchor packet may only attest the current ledger-head prediction"
        )

    for field, value in (
        ("prediction_record_sha256", prediction_sha),
        ("chain_head_sha256", chain_head),
    ):
        if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
            raise ValueError(f"{field} must be lowercase SHA-256")

    inputs = {
        "prediction_record_sha256": prediction_sha,
        "chain_head_sha256": chain_head,
    }
    if tuple(inputs) != INPUT_FIELDS:
        raise AssertionError("prospective anchor input contract drifted")

    core = {
        "schema_version": PACKET_SCHEMA,
        "repository": REPOSITORY,
        "workflow_name": WORKFLOW_NAME,
        "workflow_path": WORKFLOW_PATH,
        "record_sequence": int(record["sequence"]),
        "prediction_id": str(record["prediction_id"]),
        "match_id": str(record["match_id"]),
        "tour": str(record["tour"]),
        "inputs": inputs,
    }
    return {
        **core,
        "packet_sha256": hashlib.sha256(_canonical_json(core)).hexdigest(),
    }
