# WTA discovery provider-shaped regression — 2026-11-17

Tier: research-only, non-production. PR #518, isolated branch.

## Preregistered hypothesis and acceptance
A provider-shaped nine-row fixture reconstructed from the retained November 17 WTA index audit should classify the five non-ended group/year IDs as candidates and all four formerly configured tournaments as ended, with production eligibility always false. Reject on any ID/count mismatch, exception, or production eligibility.

## Source and sample provenance
- Main intake configuration: https://github.com/AidanDCM/Tennis-Genome-/blob/main/web-shadow/intake-config.json (blob 0431001e2cdf48a9742fba931344ac77a975562d).
- Prototype source: research/wta_index_discovery_prototype.py (blob 72b70f2f0a606dc726a7f4d8395a4435a5acbcb6).
- Prior retained-source audit: research/ledger/2026-11-17-wta-provider-index-replay.md; GitHub Actions run https://github.com/AidanDCM/Tennis-Genome-/actions/runs/44043231031 artifact 14309603977.
- Observation timestamp: 2026-11-17T08:01:39Z. Candidate IDs 2076,2052,1118,2056,1072; ended configured IDs 1023,1056,1074,1148.
- **This fixture is reconstructed from the committed audit, not raw provider bytes**; it must not be represented as a full 124-row independent replay.

## Execution and results
A locally equivalent Python prototype and nine-row fixture were run with `python -m pytest -q tests/test_provider_shape.py` in an isolated local directory: **1 passed in 0.05s**. The committed GitHub test `tests/test_wta_index_provider_shape_replay.py` uses the same ID/ended/non-production assertions, but exact-head CI must be verified separately; local success is not a claim of CI success.

## Negative result / limits
The four authorized tournaments are all ended at the observation timestamp, while five other tournaments remain candidates. No actual fixture times, identities, source match SHA, forward predictions, settlements or model gains have been established. This does not establish a qualified coverage improvement. No champion or gate changes.

## Methodology countercheck
Gneiting & Raftery (2007), https://doi.org/10.1198/016214506000001437 : evaluate probability forecasts using proper scores on clearly defined populations. An expanded tournament discovery cohort cannot be compared to the historical shadow scorecard as though samples were paired.

## Next executable queue
1. Run exact-head CI for PR #518 and inspect Ruff/Pytest outputs; fix lint/test failures without merging.
2. Capture complete official index bytes in a frozen test fixture with hashes and source license review, or use an artifact-backed test runner.
3. Audit actual upcoming match start times and identity/provenance; quantify eligible shadow coverage without altering trust gates.
4. Only after qualified forward data, preregister paired chronological surface-Elo vs frozen champion comparisons.
