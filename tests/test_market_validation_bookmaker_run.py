from __future__ import annotations

import hashlib
import inspect
import json
from dataclasses import dataclass
from pathlib import Path

import pytest

import tennis_genome.experiments.market_validation_bookmaker_run as module
from tennis_genome.experiments.market_validation_bookmaker_run import (
    create_bookmaker_outcome_unlock_seal,
    run_bookmaker_outcome_open_stage,
)
from tennis_genome.market.bookmaker_manifest import (
    build_bookmaker_source_manifest,
    write_bookmaker_source_manifest,
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
    value = dict(payload)
    value["artifact_sha256"] = _payload_sha256(payload)
    _write_json(path, value)


def _qa_gates(*, passed: bool = True) -> dict[str, bool]:
    return {
        "overall_close_coverage_at_least_60pct": passed,
        "every_recent_year_close_coverage_at_least_50pct": passed,
        "every_recent_year_at_least_100_rows": passed,
        "at_least_1000_prior_rows_before_first_evaluation_year": passed,
        "all_2021_2025_years_in_evaluation_population": passed,
        "passed": passed,
    }


def _base_files(tmp_path: Path) -> dict[str, Path]:
    valuebet = tmp_path / "valuebet"
    atp = tmp_path / "atp"
    wta = tmp_path / "wta"
    valuebet.mkdir()
    atp.mkdir()
    wta.mkdir()
    (valuebet / "valuebet-2025.csv").write_text(
        "match_id;date;genre;joueur1;joueur2;cote1_cloture;cote2_cloture\n"
        "1;2025-01-01 00:00:00;atp;Alpha A;Beta B;1.8;2.1\n",
        encoding="utf-8",
    )
    manifest = build_bookmaker_source_manifest(
        valuebet_root=valuebet,
        tennis_data_atp_root=atp,
        tennis_data_wta_root=wta,
        requested_start_date="2020-01-01",
        requested_end_date="2025-12-31",
    )
    manifest_path = tmp_path / "source_manifest.json"
    write_bookmaker_source_manifest(manifest, manifest_path)

    result: dict[str, Path] = {"source_manifest": manifest_path}
    for index, name in enumerate(
        (
            "market_book_records",
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
    passed: bool = True,
) -> dict[str, object]:
    return {
        "experiment_id": "MARKET-BOOK-QA-001",
        "overall_status": "ELIGIBLE_CONFIRMATORY" if passed else "INSUFFICIENT_COVERAGE",
        "structural_pass": True,
        "tours": [
            {
                "tour": "ATP",
                "status": "ELIGIBLE_CONFIRMATORY" if passed else "INSUFFICIENT_COVERAGE",
                "gates": _qa_gates(passed=passed),
            },
            {
                "tour": "WTA",
                "status": wta_status,
                "gates": _qa_gates(passed=passed and wta_status == "ELIGIBLE_CONFIRMATORY"),
            },
        ],
        "input_sha256": {
            "source_manifest": _file_sha256(files["source_manifest"]),
            "market_book_records": _file_sha256(files["market_book_records"]),
            "pre_match": _file_sha256(files["pre_match"]),
            "outcomes": _file_sha256(files["outcomes"]),
        },
    }


def _power_payload(
    files: dict[str, Path],
    qa: Path,
    *,
    outcome_blind: bool = True,
    family_size: int = 4,
    missing_recent_year: int | None = None,
) -> dict[str, object]:
    claims = []
    for tour, signal in (
        ("ATP", "profile_gap"),
        ("WTA", "profile_gap"),
        ("ATP", "genome"),
        ("WTA", "genome"),
    ):
        claims.append(
            {
                "experiment_id": "POWER-MDE-001",
                "tour": tour,
                "signal_name": signal,
                "min_prior_rows": 1000,
                "family_alpha": 0.05,
                "family_size": 4,
                "conservative_planning_alpha": 0.0125,
                "year_plans": [
                    {
                        "evaluation_year": year,
                        "identifiable": year != missing_recent_year,
                    }
                    for year in range(2021, 2026)
                ],
            }
        )
    return {
        "experiment_id": "POWER-MDE-001",
        "outcome_blind": outcome_blind,
        "method": "null_fisher_information_wald_planning_v1",
        "family_alpha": 0.05,
        "family_size": family_size,
        "conservative_planning_alpha": 0.0125,
        "claims": claims,
        "input_sha256": {
            "market_book_qa": _file_sha256(qa),
            "market_book_records": _file_sha256(files["market_book_records"]),
            "pre_match": _file_sha256(files["pre_match"]),
            "profile_gap_atp": _file_sha256(files["profile_gap_atp"]),
            "profile_gap_wta": _file_sha256(files["profile_gap_wta"]),
            "genome_atp": _file_sha256(files["genome_atp"]),
            "genome_wta": _file_sha256(files["genome_wta"]),
        },
    }


def _fixture(tmp_path: Path):
    files = _base_files(tmp_path)
    qa = tmp_path / "qa.json"
    _write_self_hashed(qa, _qa_payload(files))
    power = tmp_path / "power.json"
    _write_self_hashed(power, _power_payload(files, qa))
    return files, qa, power


def _seal_kwargs(files: dict[str, Path], qa: Path, power: Path):
    return {
        "source_manifest": files["source_manifest"],
        "market_book_records": files["market_book_records"],
        "pre_match": files["pre_match"],
        "market_book_qa": qa,
        "power_mde": power,
        "profile_gap_atp": files["profile_gap_atp"],
        "profile_gap_wta": files["profile_gap_wta"],
        "genome_atp": files["genome_atp"],
        "genome_wta": files["genome_wta"],
    }


def test_stage_a_signature_has_no_outcomes_argument() -> None:
    parameters = inspect.signature(create_bookmaker_outcome_unlock_seal).parameters
    assert "outcomes" not in parameters
    assert "outcomes_path" not in parameters


def test_stage_a_is_deterministic_and_binds_qa_outcomes(tmp_path: Path) -> None:
    files, qa, power = _fixture(tmp_path)
    first = create_bookmaker_outcome_unlock_seal(**_seal_kwargs(files, qa, power))
    second = create_bookmaker_outcome_unlock_seal(**_seal_kwargs(files, qa, power))
    assert first == second
    assert first.market_policy == "BOOKMAKER_CLOSE_V1"
    assert first.qa_outcomes_sha256 == _file_sha256(files["outcomes"])
    assert len(first.power_claims) == 4


def test_stage_a_rejects_nonconfirmatory_qa(tmp_path: Path) -> None:
    files = _base_files(tmp_path)
    qa = tmp_path / "qa.json"
    _write_self_hashed(qa, _qa_payload(files, passed=False))
    power = tmp_path / "power.json"
    _write_self_hashed(power, _power_payload(files, qa))
    with pytest.raises(ValueError, match="overall status is not confirmatory"):
        create_bookmaker_outcome_unlock_seal(**_seal_kwargs(files, qa, power))


def test_stage_a_rejects_non_outcome_blind_power(tmp_path: Path) -> None:
    files = _base_files(tmp_path)
    qa = tmp_path / "qa.json"
    _write_self_hashed(qa, _qa_payload(files))
    power = tmp_path / "power.json"
    _write_self_hashed(power, _power_payload(files, qa, outcome_blind=False))
    with pytest.raises(ValueError, match="outcome_blind=true"):
        create_bookmaker_outcome_unlock_seal(**_seal_kwargs(files, qa, power))


def test_stage_a_rejects_wrong_power_family(tmp_path: Path) -> None:
    files = _base_files(tmp_path)
    qa = tmp_path / "qa.json"
    _write_self_hashed(qa, _qa_payload(files))
    power = tmp_path / "power.json"
    _write_self_hashed(power, _power_payload(files, qa, family_size=3))
    with pytest.raises(ValueError, match="family_size differs"):
        create_bookmaker_outcome_unlock_seal(**_seal_kwargs(files, qa, power))


def test_stage_a_rejects_missing_recent_power_year(tmp_path: Path) -> None:
    files = _base_files(tmp_path)
    qa = tmp_path / "qa.json"
    _write_self_hashed(qa, _qa_payload(files))
    power = tmp_path / "power.json"
    _write_self_hashed(power, _power_payload(files, qa, missing_recent_year=2024))
    with pytest.raises(ValueError, match="2024"):
        create_bookmaker_outcome_unlock_seal(**_seal_kwargs(files, qa, power))


@dataclass(frozen=True)
class _DummyArtifact:
    experiment_id: str

    def to_dict(self) -> dict[str, object]:
        return {"experiment_id": self.experiment_id, "synthetic": True}


def _seal_path(tmp_path: Path, files: dict[str, Path], qa: Path, power: Path) -> Path:
    seal = create_bookmaker_outcome_unlock_seal(**_seal_kwargs(files, qa, power))
    path = tmp_path / "seal.json"
    _write_json(path, seal.to_dict())
    return path


def test_stage_b_rejects_changed_sealed_file_before_scoring(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    files, qa, power = _fixture(tmp_path)
    seal = _seal_path(tmp_path, files, qa, power)
    files["genome_atp"].write_text("changed\n", encoding="utf-8")
    called = False

    def _must_not_run(**kwargs):
        nonlocal called
        called = True
        raise AssertionError("scorer ran before sealed-file verification")

    monkeypatch.setattr(module, "build_bookmaker_market_edge_artifact", _must_not_run)
    monkeypatch.setattr(
        module,
        "build_bookmaker_market_edge_adversarial_artifact",
        _must_not_run,
    )
    with pytest.raises(ValueError, match="changed before Stage B: genome_atp"):
        run_bookmaker_outcome_open_stage(
            seal_path=seal,
            outcomes=files["outcomes"],
            **_seal_kwargs(files, qa, power),
        )
    assert called is False


def test_stage_b_rejects_different_outcomes_before_scoring(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    files, qa, power = _fixture(tmp_path)
    seal = _seal_path(tmp_path, files, qa, power)
    different = tmp_path / "different-outcomes.dat"
    different.write_text("different\n", encoding="utf-8")
    called = False

    def _must_not_run(**kwargs):
        nonlocal called
        called = True
        raise AssertionError("scorer ran before outcome hash verification")

    monkeypatch.setattr(module, "build_bookmaker_market_edge_artifact", _must_not_run)
    monkeypatch.setattr(
        module,
        "build_bookmaker_market_edge_adversarial_artifact",
        _must_not_run,
    )
    with pytest.raises(ValueError, match="file frozen by MARKET-BOOK-QA"):
        run_bookmaker_outcome_open_stage(
            seal_path=seal,
            outcomes=different,
            **_seal_kwargs(files, qa, power),
        )
    assert called is False


def test_stage_b_rejects_changed_min_prior_before_scoring(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    files, qa, power = _fixture(tmp_path)
    seal = _seal_path(tmp_path, files, qa, power)
    called = False

    def _must_not_run(**kwargs):
        nonlocal called
        called = True
        raise AssertionError("scorer ran with changed min prior rows")

    monkeypatch.setattr(module, "build_bookmaker_market_edge_artifact", _must_not_run)
    monkeypatch.setattr(
        module,
        "build_bookmaker_market_edge_adversarial_artifact",
        _must_not_run,
    )
    with pytest.raises(ValueError, match="frozen at 1000"):
        run_bookmaker_outcome_open_stage(
            seal_path=seal,
            outcomes=files["outcomes"],
            min_prior_rows=999,
            **_seal_kwargs(files, qa, power),
        )
    assert called is False


def test_stage_b_runs_both_scorers_only_after_verification(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    files, qa, power = _fixture(tmp_path)
    seal = _seal_path(tmp_path, files, qa, power)
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

    monkeypatch.setattr(module, "build_bookmaker_market_edge_artifact", _edge)
    monkeypatch.setattr(
        module,
        "build_bookmaker_market_edge_adversarial_artifact",
        _edge_adv,
    )
    result = run_bookmaker_outcome_open_stage(
        seal_path=seal,
        outcomes=files["outcomes"],
        **_seal_kwargs(files, qa, power),
    )
    assert calls == ["edge", "edge_adv"]
    assert result.outcome_open is True
    assert result.outcomes_sha256 == _file_sha256(files["outcomes"])


def test_stage_b_rejects_tampered_seal(tmp_path: Path) -> None:
    files, qa, power = _fixture(tmp_path)
    seal = create_bookmaker_outcome_unlock_seal(**_seal_kwargs(files, qa, power)).to_dict()
    seal["qa_overall_status"] = "tampered"
    path = tmp_path / "seal.json"
    _write_json(path, seal)
    with pytest.raises(ValueError, match="seal digest mismatch"):
        run_bookmaker_outcome_open_stage(
            seal_path=path,
            outcomes=files["outcomes"],
            **_seal_kwargs(files, qa, power),
        )
