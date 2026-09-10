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


def _canonical_sha(payload: object) -> str:
    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _write(path: Path, content: bytes) -> None:
    path.write_bytes(content)


def _json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


def _with_artifact_hash(payload: dict[str, object]) -> dict[str, object]:
    return {**payload, "artifact_sha256": _canonical_sha(payload)}


def _source_manifest() -> dict[str, object]:
    payload: dict[str, object] = {
        "manifest_version": "betfair-historical-bundle-v1",
        "provider": "BETFAIR_HISTORICAL",
        "sport": "TENNIS",
        "market_type": "MATCH_ODDS",
        "data_package": "ADVANCED",
        "requested_start_date": "2019-01-01",
        "requested_end_date": "2025-12-31",
        "file_count": 1,
        "total_bytes": 1,
        "files": [
            {
                "relative_path": "synthetic.bz2",
                "size_bytes": 1,
                "sha256": "c" * 64,
            }
        ],
    }
    return {**payload, "bundle_sha256": _canonical_sha(payload)}


def _power_claim(tour: str, signal_name: str) -> dict[str, object]:
    return {
        "experiment_id": "POWER-MDE-001",
        "tour": tour,
        "signal_name": signal_name,
        "min_prior_rows": 1000,
        "family_alpha": 0.05,
        "family_size": 4,
        "conservative_planning_alpha": 0.0125,
    }


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

    _json(paths["source_manifest"], _source_manifest())
    qa_payload: dict[str, object] = {
        "experiment_id": "MARKET-HIST-QA-001",
        "effective_overall_status": "ELIGIBLE_CONFIRMATORY",
        "qa_report": {
            "tours": [
                {"tour": "ATP", "status": "ELIGIBLE_CONFIRMATORY"},
                {"tour": "WTA", "status": "ELIGIBLE_CONFIRMATORY"},
            ]
        },
        "checkpoint_coverage": [],
        "companion_structural_errors": [],
        "input_sha256": {
            "source_manifest": _sha(paths["source_manifest"]),
            "market_hist_records": _sha(paths["market_hist_records"]),
            "pre_match": _sha(paths["pre_match"]),
            "outcomes": _sha(paths["outcomes"]),
        },
    }
    _json(paths["market_hist_qa"], _with_artifact_hash(qa_payload))

    power_payload: dict[str, object] = {
        "experiment_id": "POWER-MDE-001",
        "outcome_blind": True,
        "method": "null_fisher_information_wald_planning_v1",
        "family_alpha": 0.05,
        "family_size": 4,
        "conservative_planning_alpha": 0.0125,
        "beta_grid": [0.02, 0.05, 0.10, 0.15, 0.20],
        "reference_market_probabilities": [0.50, 0.65, 0.80],
        "input_sha256": {
            "market_hist_records": _sha(paths["market_hist_records"]),
            "pre_match": _sha(paths["pre_match"]),
            "profile_gap_atp": _sha(paths["profile_gap_atp"]),
            "profile_gap_wta": _sha(paths["profile_gap_wta"]),
            "genome_atp": _sha(paths["genome_atp"]),
            "genome_wta": _sha(paths["genome_wta"]),
        },
        "claims": [
            _power_claim("ATP", "profile_gap"),
            _power_claim("WTA", "profile_gap"),
            _power_claim("ATP", "genome"),
            _power_claim("WTA", "genome"),
        ],
    }
    _json(paths["power_mde"], _with_artifact_hash(power_payload))
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


def test_seal_rejects_naive_runtime_timestamp(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    with pytest.raises(ValueError, match="timezone-aware"):
        _seal(paths, datetime(2026, 9, 10, 12))


def test_seal_rejects_nonconfirmatory_tour(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    qa = json.loads(paths["market_hist_qa"].read_text())
    qa.pop("artifact_sha256")
    qa["qa_report"]["tours"][1]["status"] = "EXPLORATORY_ONLY_COVERAGE"
    _json(paths["market_hist_qa"], _with_artifact_hash(qa))
    with pytest.raises(ValueError, match="QA-eligible ATP and WTA"):
        _seal(paths, datetime(2026, 9, 10, 12, tzinfo=timezone.utc))


def test_seal_rejects_tampered_qa_artifact(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    qa = json.loads(paths["market_hist_qa"].read_text())
    qa["qa_report"]["tours"][0]["status"] = "EXPLORATORY_ONLY_COVERAGE"
    _json(paths["market_hist_qa"], qa)
    with pytest.raises(ValueError, match="MARKET-HIST-QA artifact SHA-256 mismatch"):
        _seal(paths, datetime(2026, 9, 10, 12, tzinfo=timezone.utc))


def test_seal_rejects_wrong_power_family(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    power = json.loads(paths["power_mde"].read_text())
    power.pop("artifact_sha256")
    power["claims"][3]["signal_name"] = "profile_gap"
    _json(paths["power_mde"], _with_artifact_hash(power))
    with pytest.raises(ValueError, match="duplicate claim|claim family differs"):
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
        lambda **kwargs: SimpleNamespace(
            to_dict=lambda: {"experiment_id": "MARKET-EDGE-001"}
        ),
    )
    monkeypatch.setattr(
        runner,
        "build_market_edge_adversarial_artifact",
        lambda **kwargs: SimpleNamespace(
            artifact_sha256="b" * 64,
            to_dict=lambda: {
                "experiment_id": "MARKET-EDGE-ADV-001",
                "artifact_sha256": "b" * 64,
            },
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
