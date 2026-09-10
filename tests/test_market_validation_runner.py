from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from tennis_genome.experiments import market_validation_runner as runner


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, content: bytes) -> None:
    path.write_bytes(content)


def _json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


def _fixture(tmp_path: Path) -> dict[str, Path]:
    paths = {
        "source_manifest": tmp_path / "source-manifest.json",
        "market_hist_records": tmp_path / "market-hist.jsonl",
        "market_hist_qa": tmp_path / "qa.json",
        "power_mde": tmp_path / "power.json",
        "pre_match": tmp_path / "pre-match.parquet",
        "outcomes": tmp_path / "outcomes.parquet",
        "profile_gap_atp": tmp_path / "profile-atp.json",
        "profile_gap_wta": tmp_path / "profile-wta.json",
        "genome_atp": tmp_path / "genome-atp.json",
        "genome_wta": tmp_path / "genome-wta.json",
    }
    for key in (
        "market_hist_records",
        "pre_match",
        "outcomes",
        "profile_gap_atp",
        "profile_gap_wta",
        "genome_atp",
        "genome_wta",
    ):
        _write(paths[key], f"fixture:{key}".encode())

    _json(
        paths["source_manifest"],
        {
            "data_package": "ADVANCED",
            "bundle_sha256": "a" * 64,
        },
    )
    _json(
        paths["market_hist_qa"],
        {
            "experiment_id": "MARKET-HIST-QA-001",
            "effective_overall_status": "ELIGIBLE_CONFIRMATORY",
            "qa_report": {
                "tours": [
                    {"tour": "ATP", "status": "ELIGIBLE_CONFIRMATORY"},
                    {"tour": "WTA", "status": "ELIGIBLE_CONFIRMATORY"},
                ]
            },
            "input_sha256": {
                "source_manifest": _sha(paths["source_manifest"]),
                "market_hist_records": _sha(paths["market_hist_records"]),
                "pre_match": _sha(paths["pre_match"]),
                "outcomes": _sha(paths["outcomes"]),
            },
        },
    )
    _json(
        paths["power_mde"],
        {
            "experiment_id": "POWER-MDE-001",
            "outcome_blind": True,
            "input_sha256": {
                "market_hist_records": _sha(paths["market_hist_records"]),
                "pre_match": _sha(paths["pre_match"]),
                "profile_gap_atp": _sha(paths["profile_gap_atp"]),
                "profile_gap_wta": _sha(paths["profile_gap_wta"]),
                "genome_atp": _sha(paths["genome_atp"]),
                "genome_wta": _sha(paths["genome_wta"]),
            },
        },
    )
    return paths


def _seal(paths: dict[str, Path], created_at: datetime):
    return runner.build_preoutcome_seal(
        source_manifest=paths["source_manifest"],
        market_hist_records=paths["market_hist_records"],
        market_hist_qa=paths["market_hist_qa"],
        power_mde=paths["power_mde"],
        pre_match=paths["pre_match"],
        profile_gap_atp=paths["profile_gap_atp"],
        profile_gap_wta=paths["profile_gap_wta"],
        genome_atp=paths["genome_atp"],
        genome_wta=paths["genome_wta"],
        created_at=created_at,
    )


def test_seal_digest_excludes_runtime_timestamp(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    first = _seal(paths, datetime(2026, 9, 10, 12, tzinfo=timezone.utc))
    second = _seal(paths, datetime(2026, 9, 10, 13, tzinfo=timezone.utc))
    assert first.created_at != second.created_at
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.qa_outcomes_sha256 == _sha(paths["outcomes"])
    assert first.qa_tour_status == {
        "ATP": "ELIGIBLE_CONFIRMATORY",
        "WTA": "ELIGIBLE_CONFIRMATORY",
    }


def test_seal_rejects_nonconfirmatory_tour(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    qa = json.loads(paths["market_hist_qa"].read_text())
    qa["qa_report"]["tours"][1]["status"] = "EXPLORATORY_ONLY_COVERAGE"
    _json(paths["market_hist_qa"], qa)
    with pytest.raises(ValueError, match="QA-eligible ATP and WTA"):
        _seal(paths, datetime(2026, 9, 10, 12, tzinfo=timezone.utc))


def test_seal_rejects_power_input_hash_mismatch(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    _write(paths["genome_wta"], b"mutated-after-power")
    with pytest.raises(ValueError, match="POWER-MDE input hash mismatch for genome_wta"):
        _seal(paths, datetime(2026, 9, 10, 12, tzinfo=timezone.utc))


def test_evaluation_rejects_changed_non_outcome_input(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    seal = _seal(paths, datetime(2026, 9, 10, 12, tzinfo=timezone.utc))
    seal_path = tmp_path / "seal.json"
    _json(seal_path, seal.to_dict())
    _write(paths["profile_gap_atp"], b"changed-after-seal")
    with pytest.raises(ValueError, match="sealed input changed"):
        runner.run_confirmatory_validation(
            preoutcome_seal=seal_path,
            source_manifest=paths["source_manifest"],
            market_hist_records=paths["market_hist_records"],
            market_hist_qa=paths["market_hist_qa"],
            power_mde=paths["power_mde"],
            pre_match=paths["pre_match"],
            outcomes=paths["outcomes"],
            profile_gap_atp=paths["profile_gap_atp"],
            profile_gap_wta=paths["profile_gap_wta"],
            genome_atp=paths["genome_atp"],
            genome_wta=paths["genome_wta"],
            output_dir=tmp_path / "out",
        )


def test_outcome_hash_mismatch_blocks_before_evaluators(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _fixture(tmp_path)
    seal = _seal(paths, datetime(2026, 9, 10, 12, tzinfo=timezone.utc))
    seal_path = tmp_path / "seal.json"
    _json(seal_path, seal.to_dict())
    _write(paths["outcomes"], b"different-outcomes")
    called = {"edge": False, "adv": False}

    def edge_never(**kwargs):
        called["edge"] = True
        raise AssertionError("MARKET-EDGE must not run")

    def adv_never(**kwargs):
        called["adv"] = True
        raise AssertionError("MARKET-EDGE-ADV must not run")

    monkeypatch.setattr(runner, "build_market_edge_artifact", edge_never)
    monkeypatch.setattr(runner, "build_market_edge_adversarial_artifact", adv_never)
    with pytest.raises(ValueError, match="differs from the file frozen by MARKET-HIST-QA"):
        runner.run_confirmatory_validation(
            preoutcome_seal=seal_path,
            source_manifest=paths["source_manifest"],
            market_hist_records=paths["market_hist_records"],
            market_hist_qa=paths["market_hist_qa"],
            power_mde=paths["power_mde"],
            pre_match=paths["pre_match"],
            outcomes=paths["outcomes"],
            profile_gap_atp=paths["profile_gap_atp"],
            profile_gap_wta=paths["profile_gap_wta"],
            genome_atp=paths["genome_atp"],
            genome_wta=paths["genome_wta"],
            output_dir=tmp_path / "out",
        )
    assert called == {"edge": False, "adv": False}


def test_successful_execution_writes_child_artifacts_and_ledger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _fixture(tmp_path)
    seal = _seal(paths, datetime(2026, 9, 10, 12, tzinfo=timezone.utc))
    seal_path = tmp_path / "seal.json"
    _json(seal_path, seal.to_dict())

    monkeypatch.setattr(
        runner,
        "build_market_edge_artifact",
        lambda **kwargs: SimpleNamespace(to_dict=lambda: {"experiment_id": "MARKET-EDGE-001"}),
    )
    monkeypatch.setattr(
        runner,
        "build_market_edge_adversarial_artifact",
        lambda **kwargs: SimpleNamespace(
            artifact_sha256="b" * 64,
            to_dict=lambda: {"experiment_id": "MARKET-EDGE-ADV-001", "artifact_sha256": "b" * 64},
        ),
    )
    output = tmp_path / "out"
    ledger = runner.run_confirmatory_validation(
        preoutcome_seal=seal_path,
        source_manifest=paths["source_manifest"],
        market_hist_records=paths["market_hist_records"],
        market_hist_qa=paths["market_hist_qa"],
        power_mde=paths["power_mde"],
        pre_match=paths["pre_match"],
        outcomes=paths["outcomes"],
        profile_gap_atp=paths["profile_gap_atp"],
        profile_gap_wta=paths["profile_gap_wta"],
        genome_atp=paths["genome_atp"],
        genome_wta=paths["genome_wta"],
        output_dir=output,
        created_at=datetime(2026, 9, 10, 14, tzinfo=timezone.utc),
    )
    assert ledger.outcomes_sha256 == _sha(paths["outcomes"])
    assert ledger.market_edge_adv_internal_artifact_sha256 == "b" * 64
    assert (output / "market_edge_001.json").exists()
    assert (output / "market_edge_adv_001.json").exists()
    assert (output / "market_validation_execution_ledger.json").exists()
