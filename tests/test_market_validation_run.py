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


def _base_files(tmp_path: Path) -> dict[str, Path]:
    names = (
        "source_manifest",
        "market_hist_records",
        "pre_match",
        "profile_gap_atp",
        "profile_gap_wta",
        "genome_atp",
        "genome_wta",
    )
    result: dict[str, Path] = {}
    for index, name in enumerate(names):
        path = tmp_path / f"{name}.dat"
        path.write_text(f"{name}-{index}\n", encoding="utf-8")
        result[name] = path
    return result


def _qa_payload(
    files: dict[str, Path],
    *,
    wta_status: str = "ELIGIBLE_CONFIRMATORY",
) -> dict[str, object]:
    return {
        "experiment_id": "MARKET-HIST-QA-001",
        "effective_overall_status": "ELIGIBLE_CONFIRMATORY",
        "qa_report": {
            "tours": [
                {"tour": "ATP", "status": "ELIGIBLE_CONFIRMATORY"},
                {"tour": "WTA", "status": wta_status},
            ]
        },
        "checkpoint_coverage": [],
        "companion_structural_errors": [],
        "input_sha256": {
            "source_manifest": _file_sha256(files["source_manifest"]),
            "market_hist_records": _file_sha256(files["market_hist_records"]),
            "pre_match": _file_sha256(files["pre_match"]),
            "outcomes": "0" * 64,
        },
    }


def _power_payload(
    files: dict[str, Path],
    *,
    outcome_blind: bool = True,
    missing_recent_year: int | None = None,
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
                "year_plans": plans,
            }
        )
    return {
        "experiment_id": "POWER-MDE-001",
        "outcome_blind": outcome_blind,
        "method": "synthetic",
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


def test_stage_a_is_deterministic(tmp_path: Path):
    files, qa, power = _fixture(tmp_path)
    first = create_outcome_unlock_seal(**_seal_kwargs(files, qa, power))
    second = create_outcome_unlock_seal(**_seal_kwargs(files, qa, power))
    assert first == second
    assert first.stage == "OUTCOME_LOCKED_COMPLETE"
    assert first.winner_outcomes_permitted_for_stage_b is True
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


def test_stage_a_rejects_non_outcome_blind_power(tmp_path: Path):
    files = _base_files(tmp_path)
    qa = tmp_path / "qa.json"
    power = tmp_path / "power.json"
    _write_self_hashed(qa, _qa_payload(files))
    _write_self_hashed(power, _power_payload(files, outcome_blind=False))
    with pytest.raises(ValueError, match="outcome_blind=true"):
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
            outcomes=tmp_path / "does-not-need-to-exist.parquet",
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
    outcomes = tmp_path / "outcomes.parquet"
    outcomes.write_text("winner-outcomes-open-only-in-stage-b\n", encoding="utf-8")

    calls: list[str] = []

    def _edge(**kwargs):
        calls.append("edge")
        assert kwargs["outcomes_path"] == outcomes
        return _DummyArtifact("MARKET-EDGE-001")

    def _edge_adv(**kwargs):
        calls.append("edge_adv")
        assert kwargs["outcomes_path"] == outcomes
        return _DummyArtifact("MARKET-EDGE-ADV-001")

    monkeypatch.setattr(module, "build_market_edge_artifact", _edge)
    monkeypatch.setattr(module, "build_market_edge_adversarial_artifact", _edge_adv)
    result = run_outcome_open_stage(
        seal_path=seal_path,
        outcomes=outcomes,
        min_prior_rows=24,
        **_seal_kwargs(files, qa, power),
    )
    assert calls == ["edge", "edge_adv"]
    assert result.stage == "OUTCOME_OPEN_COMPLETE"
    assert result.outcomes_sha256 == _file_sha256(outcomes)
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
            outcomes=tmp_path / "outcomes.parquet",
            min_prior_rows=24,
            **_seal_kwargs(files, qa, power),
        )
