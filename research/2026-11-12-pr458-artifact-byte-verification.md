# PR #458 diagnostic artifact byte verification — 2026-11-12

## Prespecified operational hypothesis
The exact-head CI diagnostics artifact for PR #458 is intact and independently proves Ruff success and pytest success. Baseline: previous research PR #459 established successful job-step statuses but had not inspected the diagnostic ZIP. Acceptance: downloaded ZIP SHA-256 matches GitHub's recorded digest, ZIP entries are readable, Ruff states all checks passed, pytest reports no failed tests. Failure: any mismatch, unreadable archive, or test failure. This is **not** a forecasting model comparison.

## Sources and fixed sample IDs
- Main baseline: `8af76720a6291b166263fa1cd8191504f84ed6b6`.
- PR #458 head: `f5ca0cdc5333bb3242b024c55b867c6aa7bf5087`, https://github.com/AidanDCM/Tennis-Genome-/pull/458
- Exact-head workflow run: https://github.com/AidanDCM/Tennis-Genome-/actions/runs/43163081105
- Artifact ID `13918178857`, `ci-diagnostics`, 654 bytes, SHA-256 `9997240a2b69073d652bae6572b546ea45bbc3dd734011c40a34035c31daeca9`.
- Main WTA scorecard blob `60082a6292087e2b6e902faca79f2f4c847d8fdb`; main acquisition workflow blob `2a698a6f56297aee054a94dc49a28fefaaff2d35`.
- Acquisition result proposal https://github.com/AidanDCM/Tennis-Genome-/pull/428 (open, one proposed Chennai result, 13 unresolved, two identity conflicts).

## Actual execution and reproduction
Downloaded artifact 13918178857 through connected GitHub and inspected the returned local ZIP bytes. Exact command:

```bash
python - <<'PY'
import hashlib, zipfile
p='pr458-ci-diagnostics.zip'
b=open(p,'rb').read()
print(len(b), hashlib.sha256(b).hexdigest())
with zipfile.ZipFile(p) as z:
    for name in z.namelist():
        print(name, z.read(name).decode())
PY
```

Observed: 654 bytes; SHA-256 exactly equals GitHub digest; entries `ruff.txt` and `pytest.txt` readable. Ruff: `All checks passed!`. Pytest: **1310 passed, 2 warnings in 21.77s**. Warnings are invalid escape sequences in `tests/test_full_slate_cutover.py:201` and `tests/test_pattern_confirm_live.py:674`. No failed tests. Artifact verification hypothesis **accepted**. The archive contains no settlement payload, no prospective observation receipt, and no actual simulation of failure/blocked/allowed gate execution.

## Operational evidence and negative results
Main still uses the original `blocked != 'true'` workflow guard; fail-closed change remains unmerged in draft PR #458, which depends on draft PR #457. Main active-results manifest still selects the older Hong Kong result. Main scorecard is explicitly non-production: 85 eligible, 46 correct, Brier 0.2514610585, log loss 0.6969082733, 16 pending. Historical fixed 0.5 Brier 0.25 and log loss ln(2) ~0.693147 are slightly better; no paired chronological improvement claimed. Qualified production-forward N, champion SHA and new prospective settlement not independently established in this iteration. CI success is **not** evidence acquisition resumed.

## Research and limitations
- Ferro (2017), https://doi.org/10.1002/qj.3115, shows observation error can change proper-score rankings; theoretical weather examples, not tennis. No code adopted; license for implementation not verified.
- Burt, Shen and Broderick (2025), https://proceedings.mlr.press/v258/burt25a.html, demonstrates validation failures when available verification locations differ from target locations; spatial rather than chronological tennis setting. Published PMLR, reproducible paper URL; implementation license not checked. This is a caution about missing-label selection bias, not a proposed correction fitted to Tennis Genome.
No external performance claims were treated as comparable; no external code imported.

## Prioritized next executable queue
1. Add a **behavioral**, isolated workflow test for gate success/blocked, success/allowed, failure/no-output, and skipped/no-output; verify actual step execution, not just source strings. Keep immutable evidence and result gates.
2. Review PR #428's Chennai evidence with human approval before any result publication; resolve proposal blockage safely and inspect a fresh acquisition workflow's actual fetch/compile/settlement logs.
3. Refresh immutable champion SHA and qualified forward ledger; only then preregister paired chronological champion–Elo–fixed-0.5 comparisons with proper scoring and uncertainty, untouched final holdout.

No model, production prediction, evidence, or settlement files changed. No automatic merge or promotion.
