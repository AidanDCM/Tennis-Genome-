# PR #461 exact-head diagnostic artifact verification — 2026-11-12

## Predeclared hypothesis and acceptance
Hypothesis: CI diagnostic ZIP for PR #461's exact head contains successful Ruff and pytest results, and its SHA-256 equals the GitHub Actions recorded digest. Acceptance: exact digest match, readable ZIP, Ruff success, zero pytest failures. This checks CI execution only; it does not prove live acquisition-gate runtime behavior or model improvement.

## Sources and immutable identifiers
- Main WTA non-production scorecard: https://github.com/AidanDCM/Tennis-Genome-/blob/main/web-shadow/scorecard.json (retrieved this run; metrics eligible 85, correct 46, Brier 0.2514610585394295, log loss 0.6969082732945988, pending 16; production_eligible=false).
- PR #461: https://github.com/AidanDCM/Tennis-Genome-/pull/461 ; head f81832683826234e4e833782adcf6754dbeb7030.
- CI: https://github.com/AidanDCM/Tennis-Genome-/actions/runs/43185872429
- Artifact ID 13928955401; artifact name ci-diagnostics; archive size 653 bytes; GitHub digest sha256:69818500e13f6d442fbf5905fabdc849b60322577fe84fb74950fcf278462c01.
- Open PRs #428, #457, #458, #461, #462 confirmed via GitHub PR search. #428 blocks acquisition per prior log audit; this run did not execute acquisition.

## Executed reproduction
Downloaded artifact via GitHub Actions connector, then ran locally:

```bash
python - <<'PY'
import hashlib, zipfile
p='/mnt/data/github-actions-artifact-13928955401.zip'
b=open(p,'rb').read()
print(len(b), hashlib.sha256(b).hexdigest())
with zipfile.ZipFile(p) as z:
    for name in z.namelist():
        print(name, z.read(name).decode())
PY
```

Observed: 653 bytes, SHA-256 69818500e13f6d442fbf5905fabdc849b60322577fe84fb74950fcf278462c01 (exact match); ZIP members ruff.txt and pytest.txt. Ruff: `All checks passed!`. Pytest: `1312 passed, 2 warnings in 28.85s`. Warnings: invalid escape sequence in tests/test_full_slate_cutover.py:201 and tests/test_pattern_confirm_live.py:674. Hypothesis accepted.

## Negative results / limitations
Artifact has only lint/test logs; no settlement payload, gate-state runtime trace, or proof of new qualified prospective results. CI success is not an acquisition success signal. No predictive ablation was attempted. Champion checksum and production-forward qualified denominator were not independently refreshed. Existing Hong Kong mismatches remain excluded. No immutable predictions, outcomes, safety gates or champion modified.

## External research
- Burt, Shen & Broderick (2025), *Consistent Validation for Predictive Methods in Spatial Settings*, AISTATS/PMLR: https://proceedings.mlr.press/v258/burt25a.html . Evaluation-site mismatch may invalidate standard validation; analogous risk from unresolved tennis matches. Spatial evaluation, not tennis; method/code license not checked; no reproduction.
- Pic et al. (2025), *Proper scoring rules for multivariate probabilistic forecasts based on aggregation and transformation*, https://doi.org/10.5194/ascmo-11-23-2025 . Multiple complementary proper scores help characterize forecasts. Multivariate meteorology, not binary tennis; no code imported. Neither provides directly comparable tennis accuracy.

## Next executable queue
1. On isolated research branch, run an actual non-mutating GitHub Actions gate-state integration harness for success/allowed, success/blocked, failed, skipped, and empty output; assert no downstream writes in unsafe states. Preserve all gates.
2. Human-review #428 Chennai evidence; only after safe resolution verify real source fetch, matching, compilation, and dry-run results; count capture coverage and unresolved reasons.
3. Independently retrieve immutable champion checksum and qualified forward denominator. After new locked matches, prespecify paired chronological champion vs Elo vs fixed-probability Brier/log loss/calibration and uncertainty. Preserve untouched final holdout and record negative tests.
