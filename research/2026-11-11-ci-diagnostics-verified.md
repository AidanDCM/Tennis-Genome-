# 2026-11-11 — Independently inspect CI diagnostic archive (iteration 53)

## Predeclared verification hypothesis
The artifact attached to exact-head integration run #43080766329 is intact and contains actual Ruff/pytest outcomes. Acceptance: downloaded ZIP SHA-256 equals artifact metadata digest; ZIP opens; Ruff reports success; pytest reports successful test count. Failure: any mismatch, corruption, or failed test. **This does not prove settlement output correctness or production eligibility.**

## Evidence and executed commands
- Main baseline: `8af76720a6291b166263fa1cd8191504f84ed6b6` (verified from PR #449 base); acquisition PR #428 remains open at `e676c961d674ffd32d254bb96f738ae7242e211f`.
- Integration branch PR #447, tested SHA `bff7013a3da3ecd133bac0310f7abd65066e9897`, CI https://github.com/AidanDCM/Tennis-Genome-/actions/runs/43080766329 .
- Artifact ID `13883129305`, `ci-diagnostics`, downloaded successfully using connected GitHub artifact endpoint. Local archive `/mnt/data/ci-diagnostics.zip`.
- Reproduction: `python -c "import hashlib,zipfile; p='ci-diagnostics.zip'; print(hashlib.sha256(open(p,'rb').read()).hexdigest()); z=zipfile.ZipFile(p); print(z.namelist()); [print(n,z.read(n).decode()) for n in z.namelist()]"`.
- **Observed**: 653 bytes, computed SHA-256 `799c485b8c505e7b240ef32df95ed58b67c8c72790d620fe60e8abbdcb8f45c2`, matches artifact metadata exactly. Members `ruff.txt`, `pytest.txt`.
- **Observed Ruff**: `All checks passed!`.
- **Observed pytest**: `1309 passed, 2 warnings in 22.49s`. Warnings: invalid escape sequences in `tests/test_full_slate_cutover.py:201` and `tests/test_pattern_confirm_live.py:674`; neither failed CI.
- **Negative finding**: ZIP contains **no settlement summary, provenance receipt or individual assertion-level output**. Test pass is evidence that assertions executed, not independently inspected settlement bytes. No canonical settlement published or qualified forward evidence added.

## Main scorecard / limitations
- Main `web-shadow/scorecard.json` verified: non-production WTA Web Shadow 88 settled records, 85 eligible, 46 correct (54.1176%), Brier 0.2514610585, log loss 0.6969082733, 16 pending, `production_eligible=false`.
- Historical paired overall Elo comparison: 78 common matches, Genome 41 correct vs Elo 42; Brier 0.2524328274 vs 0.2597451904. Not prospective superiority; paired uncertainty unavailable from aggregates.
- PR #428 reports 13 unresolved and 2 identity conflicts; exclude. Qualified production-forward N and frozen champion checksum not independently refreshed this iteration.

## Research (method and contrary evidence)
- Waghmare & Ziegel (2026), *Proper Scoring Rules for Estimation and Forecast Evaluation*, https://doi.org/10.1146/annurev-statistics-042424-050626 . Published review, CC BY 4.0; explains scoring rules for comparable probability forecasts. Adapt paired Brier/log loss; not tennis evidence.
- Dimitriadis, Gneiting & Jordan (2021), *Evaluating probabilistic classifiers: Reliability diagrams and score decompositions revisited*, https://arxiv.org/abs/2008.03033 . CORP/PAV offers reproducible calibration diagnostics; **do not fit on final holdout**; external code/license not verified.
- Loveday, Taggart & Khanarmuei (2024), https://doi.org/10.1175/WAF-D-23-0201.1 . Published weather verification shows why classification diagnostics alone can mislead; non-tennis sample, reuse/license unverified.
- Contrary hypothesis: simple Elo can match or outperform Genome on new locked matches. No ablation or fit attempted; evidence acquisition is higher priority.

## Prioritized next executable queue
1. Add isolated deterministic non-sensitive settlement-summary artifact to CI on an experiment branch; compare hashes/identities, fail closed, never publish or modify main.
2. Audit PR #428 acquisition and workflow freshness; human review, no auto-merge or gate relaxation.
3. Refresh immutable champion and qualified forward-settlement metrics with explicit sample IDs and timestamps.
4. Pre-register chronological paired champion–Elo Brier/log loss, uncertainty and coverage on newly locked matches; untouched final holdout.
