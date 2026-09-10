from __future__ import annotations

import hashlib
import inspect
import json
from dataclasses import dataclass
from pathlib import Path

import pytest

import tennis_genome.experiments.market_validation_run as module
from tennis_genome.experiments.market_validation_run import (
    create_outcome_unlock_seal,
    run_outcome_open_stage,
)
from tennis_genome.market.historical_manifest import (
    build_historical_source_manifest,
    write_historical_source_manifest,
)


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _payload_sha256(value: object) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


def _write_self_hashed(path: Path, payload: dict[str, object]) -> None:
    unsigned = dict(payload)
    unsigned["artifact_sha256"] = _payload_sha256(payload)
    _write_json(path, unsigned)


def _qa_gates(*, passed: bool = True) -> dict[str, bool]:
    return {
        "overall_close_coverage_at_least_60pct": passed,
        "every_recent_year_close_coverage_at_least_50pct": passed,
        "every_recent_year_at_least_100_rows": passed,
        "at_least_1000_prior_rows_before_first_evaluation_year": passed,
        "at_least_five_evaluation_years": passed,
        "all_2021_2025_years_in_evaluation_population": passed,
        "passed": passed,
    }


def _base_files(tmp_path: Path) -> dict[str, Path]:
    source_root = tmp_path / "source"
    source_root.mkdir()
    source_file = source_root / "bundle.jsonl"
    source_file.write_text("synthetic-betfair-source\n", encoding="utf-8")
    manifest = build_historical_source_manifest(
        root=source_root,
        data_package="ADVANCED",
        requested_start_date="2020-01-01",
        requested_end_date="2025-12-31",
    )
    source_manifest = tmp_path / "source_manifest.json"
    write_historical_source_manifest(manifest, source_manifest)

    result: dict[str, Path] = {"source_manifest": source_manifest}
    for index, name in enumerate(
        (
            "market_hist_records",
            "pre_match",
            "outcomes",
            "profile_gap_atp",
            "profile_gap_wta",
            "genome_atp",
            "genome_wta",
        )
    ):
        path = tmp_path / f"{name}.dat"
        path.write_text(f"{name}-{index}\n", encoding="utf-8")
        result[name] = path
    return result


def _qa_payload(
    files: dict[str, Path],
    *,
    wta_status: str = "ELIGIBLE_CONFIRMATORY",
    overall_status: str = "ELIGIBLE_CONFIRMATORY",
    wta_gates_passed: bool = True,
) -> dict[str, object]:
    return {
        "experiment_id": "MARKET-HIST-QA-001",
        "effective_overall_status": overall_status,
        "qa_report": {
            "overall_status": overall_status,
            "tours": [
                {
                    "tour": "ATP",
                    "status": "ELIGIBLE_CONFIRMATORY",
                    "gates": _qa_gates(),
                },
                {
                    "tour": "WTA",
                    "status": wta_status,
                    "gates": _qa_gates(passed=wta_gates_passed),
                },
            ],
        },
        "checkpoint_coverage": [],
        "companion_structural_errors": [],
        "input_sha256": {
            "source_manifest": _file_sha256(files["source_manifest"]),
            "market_hist_records": _file_sha256(files["market_hist_records"]),
            "pre_match": _file_sha256(files["pre_match"]),
            "outcomes": _file_sha256(files["outcomes"]),
        },
    }


def _power_payload(
    files: dict[str, Path],
    *,
    outcome_blind: bool = True,
    missing_recent_year: int | None = None,
    family_size: int = 4,
) -> dict[str, object]:
    claims = []
    for tour, signal in (
        ("ATP", "profile_gap"),
        ("WTA", "profile_gap"),
        ("ATP", "genome"),
        ("WTA", "genome"),
    ):
        plans = [
            {"evaluation_year": year, "identifiable": year != missing_recent_year}
            for year in range(2020, 2026)
        ]
        claims.append(
            {
                "experiment_id": "POWER-MDE-001",
                "tour": tour,
                "signal_name": signal,
                "min_prior_rows": 1000,
                "family_alpha": 0.05,
                "family_size": 4,
                "conservative_planning_alpha": 0.0125,
                "year_plans": plans,
            }
        )
    return {
        "experiment_id": "POWER-MDE-001",
        "outcome_blind": outcome_blind,
        "method": "synthetic",
        "family_alpha": 0.05,
        "family_size": family_size,
        "conservative_planning_alpha": 0.0125,
        "claims": claims,
        "input_sha256": {
            name: _file_sha256(files[name])
            for name in (
                "market_hist_records",
                "pre_match",
                "profile_gap_atp",
                "profile_gap_wta",
                "genome_atp",
                "genome_wta",
            )
        },
    }


def _fixture(tmp_path: Path):
    files = _base_files(tmp_path)
    qa = tmp_path / "qa.json"
    power = tmp_path / "power.json"
    _write_self_hashed(qa, _qa_payload(files))
    _write_self_hashed(power, _power_payload(files))
    return files, qa, power


def _seal_kwargs(files: dict[str, Path], qa: Path, power: Path):
    return {
        "source_manifest": files["source_manifest"],
        "market_hist_records": files["market_hist_records"],
        "pre_match": files["pre_match"],
        "market_hist_qa": qa,
        "power_mde": power,
        "profile_gap_atp": files["profile_gap_atp"],
        "profile_gap_wta": files["profile_gap_wta"],
        "genome_atp": files["genome_atp"],
        "genome_wta": files["genome_wta"],
    }


def test_stage_a_has_no_outcomes_argument():
    parameters = inspect.signature(create_outcome_unlock_seal).parameters
    assert "outcomes" not in parameters
    assert "outcomes_path" not in parameters


def test_stage_a_is_deterministic_and_binds_qa_outcome_hash(tmp_path: Path):
    files, qa, power = _fixture(tmp_path)
    first = create_outcome_unlock_seal(**_seal_kwargs(files, qa, power))
    second = create_outcome_unlock_seal(**_seal_kwargs(files, qa, power))
    assert first == second
    assert first.stage == "OUTCOME_LOCKED_COMPLETE"
    assert first.winner_outcomes_permitted_for_stage_b is True
    assert first.qa_outcomes_sha256 == _file_sha256(files["outcomes"])
    assert len(first.power_claims) == 4
    assert all(
        set(range(2021, 2026)).issubset(claim.identifiable_evaluation_years)
        for claim in first.power_claims
    )


def test_stage_a_rejects_nonconfirmatory_tour(tmp_path: Path):
    files = _base_files(tmp_path)
    qa = tmp_path / "qa.json"
    power = tmp_path / "power.json"
    _write_self_hashed(
        qa,
        _qa_payload(files, wta_status="EXPLORATORY_ONLY_COVERAGE"),
    )
    _write_self_hashed(power, _power_payload(files))
    with pytest.raises(ValueError, match="blocked=.*WTA"):
        create_outcome_unlock_seal(**_seal_kwargs(files, qa, power))


def test_stage_a_rejects_inconsistent_qa_gate(tmp_path: Path):
    files = _base_files(tmp_path)
    qa = tmp_path / "qa.json"
    power = tmp_path / "power.json"
    _write_self_hashed(qa, _qa_payload(files, wta_gates_passed=False))
    _write_self_hashed(power, _power_payload(files))
    with pytest.raises(ValueError, match="failed frozen coverage gate"):
        create_outcome_unlock_seal(**_seal_kwargs(files, qa, power))


def test_stage_a_rejects_invalid_source_manifest_semantics(tmp_path: Path):
    files, qa, power = _fixture(tmp_path)
    payload = json.loads(files["source_manifest"].read_text(encoding="utf-8"))
    payload["provider"] = "NOT_BETFAIR"
    _write_json(files["source_manifest"], payload)
    with pytest.raises(ValueError, match="provider or sport"):
        create_outcome_unlock_seal(**_seal_kwargs(files, qa, power))


def test_stage_a_rejects_non_outcome_blind_power(tmp_path: Path):
    files = _base_files(tmp_path)
    qa = tmp_path / "qa.json"
    power = tmp_path / "power.json"
    _write_self_hashed(qa, _qa_payload(files))
    _write_self_hashed(power, _power_payload(files, outcome_blind=False))
    with pytest.raises(ValueError, match="outcome_blind=true"):
        create_outcome_unlock_seal(**_seal_kwargs(files, qa, power))


def test_stage_a_rejects_wrong_power_family_settings(tmp_path: Path):
    files = _base_files(tmp_path)
    qa = tmp_path / "qa.json"
    power = tmp_path / "power.json"
    _write_self_hashed(qa, _qa_payload(files))
    _write_self_hashed(power, _power_payload(files, family_size=3))
    with pytest.raises(ValueError, match="family_size differs"):
        create_outcome_unlock_seal(**_seal_kwargs(files, qa, power))


def test_stage_a_rejects_missing_identifiable_recent_power_year(tmp_path: Path):
    files = _base_files(tmp_path)
    qa = tmp_path / "qa.json"
    power = tmp_path / "power.json"
    _write_self_hashed(qa, _qa_payload(files))
    _write_self_hashed(power, _power_payload(files, missing_recent_year=2023))
    with pytest.raises(ValueError, match="2023"):
        create_outcome_unlock_seal(**_seal_kwargs(files, qa, power))


def test_stage_a_rejects_tampered_self_digest(tmp_path: Path):
    files, qa, power = _fixture(tmp_path)
    payload = json.loads(power.read_text(encoding="utf-8"))
    payload["method"] = "tampered"
    _write_json(power, payload)
    with pytest.raises(ValueError, match="artifact_sha256 mismatch"):
        create_outcome_unlock_seal(**_seal_kwargs(files, qa, power))


@dataclass(frozen=True)
class _DummyArtifact:
    experiment_id: str

    def to_dict(self) -> dict[str, object]:
        return {"experiment_id": self.experiment_id, "synthetic": True}


def test_stage_b_rejects_changed_file_before_scoring(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    files, qa, power = _fixture(tmp_path)
    seal = create_outcome_unlock_seal(**_seal_kwargs(files, qa, power))
    seal_path = tmp_path / "seal.json"
    _write_json(seal_path, seal.to_dict())
    files["genome_atp"].write_text("changed-after-seal\n", encoding="utf-8")

    called = False

    def _must_not_run(**kwargs):
        nonlocal called
        called = True
        raise AssertionError("outcome-scoring builder ran before seal verification")

    monkeypatch.setattr(module, "build_market_edge_artifact", _must_not_run)
    monkeypatch.setattr(module, "build_market_edge_adversarial_artifact", _must_not_run)
    with pytest.raises(ValueError, match="changed before Stage B: genome_atp"):
        run_outcome_open_stage(
            seal_path=seal_path,
            outcomes=files["outcomes"],
            **_seal_kwargs(files, qa, power),
        )
    assert called is False


def test_stage_b_rejects_different_outcome_file_before_scoring(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    files, qa, power = _fixture(tmp_path)
    seal = create_outcome_unlock_seal(**_seal_kwargs(files, qa, power))
    seal_path = tmp_path / "seal.json"
    _write_json(seal_path, seal.to_dict())
    different = tmp_path / "different_outcomes.dat"
    different.write_text("different-outcomes\n", encoding="utf-8")

    called = False

    def _must_not_run(**kwargs):
        nonlocal called
        called = True
        raise AssertionError("outcome-scoring builder ran before outcome hash check")

    monkeypatch.setattr(module, "build_market_edge_artifact", _must_not_run)
    monkeypatch.setattr(module, "build_market_edge_adversarial_artifact", _must_not_run)
    with pytest.raises(ValueError, match="file frozen by MARKET-HIST-QA"):
        run_outcome_open_stage(
            seal_path=seal_path,
            outcomes=different,
            **_seal_kwargs(files, qa, power),
        )
    assert called is False


def test_stage_b_rejects_nonfrozen_min_prior_rows_before_scoring(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    files, qa, power = _fixture(tmp_path)
    seal = create_outcome_unlock_seal(**_seal_kwargs(files, qa, power))
    seal_path = tmp_path / "seal.json"
    _write_json(seal_path, seal.to_dict())

    called = False

    def _must_not_run(**kwargs):
        nonlocal called
        called = True
        raise AssertionError("outcome-scoring builder ran with altered frozen threshold")

    monkeypatch.setattr(module, "build_market_edge_artifact", _must_not_run)
    monkeypatch.setattr(module, "build_market_edge_adversarial_artifact", _must_not_run)
    with pytest.raises(ValueError, match="frozen at 1000"):
        run_outcome_open_stage(
            seal_path=seal_path,
            outcomes=files["outcomes"],
            min_prior_rows=24,
            **_seal_kwargs(files, qa, power),
        )
    assert called is False


def test_stage_b_runs_both_frozen_experiments_after_verification(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    files, qa, power = _fixture(tmp_path)
    seal = create_outcome_unlock_seal(**_seal_kwargs(files, qa, power))
    seal_path = tmp_path / "seal.json"
    _write_json(seal_path, seal.to_dict())

    calls: list[str] = []

    def _edge(**kwargs):
        calls.append("edge")
        assert kwargs["outcomes_path"] == files["outcomes"]
        assert kwargs["min_prior_rows"] == 1000
        return _DummyArtifact("MARKET-EDGE-001")

    def _edge_adv(**kwargs):
        calls.append("edge_adv")
        assert kwargs["outcomes_path"] == files["outcomes"]
        assert kwargs["min_prior_rows"] == 1000
        return _DummyArtifact("MARKET-EDGE-ADV-001")

    monkeypatch.setattr(module, "build_market_edge_artifact", _edge)
    monkeypatch.setattr(module, "build_market_edge_adversarial_artifact", _edge_adv)
    result = run_outcome_open_stage(
        seal_path=seal_path,
        outcomes=files["outcomes"],
        **_seal_kwargs(files, qa, power),
    )
    assert calls == ["edge", "edge_adv"]
    assert result.stage == "OUTCOME_OPEN_COMPLETE"
    assert result.outcomes_sha256 == _file_sha256(files["outcomes"])
    assert result.market_edge_001["experiment_id"] == "MARKET-EDGE-001"
    assert result.market_edge_adv_001["experiment_id"] == "MARKET-EDGE-ADV-001"


def test_stage_b_rejects_tampered_seal(tmp_path: Path):
    files, qa, power = _fixture(tmp_path)
    seal = create_outcome_unlock_seal(**_seal_kwargs(files, qa, power)).to_dict()
    seal["qa_effective_overall_status"] = "tampered"
    seal_path = tmp_path / "seal.json"
    _write_json(seal_path, seal)
    with pytest.raises(ValueError, match="seal digest mismatch"):
        run_outcome_open_stage(
            seal_path=seal_path,
            outcomes=files["outcomes"],
            **_seal_kwargs(files, qa, power),
        )
