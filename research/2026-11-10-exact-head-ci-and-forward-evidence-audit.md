# Iteration 27 — exact-head CI and acquisition trust audit (2026-11-10)

Scope: research-only audit of draft PR #430; no model, result, identity or champion mutation.

## Fresh repository evidence
- Repo default branch main, writable GitHub connector. Open PRs #428 (result proposal), #429 (calibration research), #430 (blocked receipt).
- PR #430 exact head `95d6357cf7d90cddbd8bc5aefe54e75f0e44fda6`; CI run https://github.com/AidanDCM/Tennis-Genome-/actions/runs/42877780311 **completed success**. Job 130045593527 reports Ruff success, Pytest success, CI diagnostic artifact step success. This is PR CI, NOT an acquisition-workflow execution.
- Branch workflow inspected at `.github/workflows/wta_web_shadow_results.yml`: checkout explicitly uses `ref: main`, and its schedule/push trigger runs from main. Therefore PR-only changes cannot produce a real blocked acquisition receipt on scheduled main before review/merge. The receipt is gated by `steps.pr_gate.outputs.blocked == 'true'`; open PR reason `OPEN_RESULT_PR`, orphan branch reason `ORPHAN_RESULT_BRANCH`. The acquisition steps retain `blocked != 'true'` conditions.
- PR #428 remains open/unmerged: 16 pending, one finished captured, 13 unresolved, two identity conflicts. Main `web-shadow/active-results.json` blob `52d8645a3389c9b2d8ba5a6c87e520e23ab80a25` still selects the earlier Hong Kong result, not proposed Chennai.
- Last independently verified forward aggregate from previous audit: run https://github.com/AidanDCM/Tennis-Genome-/actions/runs/42839698243 reported `NO_SETTLED_FORWARD_OBSERVATIONS` (0 qualified); **not refreshed here**. Prior non-production WTA Web Shadow scorecard 46/85, Brier .251461, log loss .696908; not refreshed here.

## Executed numerical falsification / negative result
Hypothesis: 46 correct out of 85 historical non-production matches is distinguishable from 50% under a simple independent Bernoulli null. Prespecified two-sided exact binomial test at alpha 0.05. Run:
```bash
python - <<'PY'
from scipy.stats import binomtest
r=binomtest(46,85,0.5)
print(r.pvalue, r.proportion_ci(confidence_level=0.95))
assert r.proportion_ci().low < .5 < r.proportion_ci().high
PY
```
Observed p=0.5154257318839004; exact 95% CI [0.4295709843441571,0.64982986098217]; test assertion PASSED. This does **not** establish model skill or no skill; 50% is not a population-matched champion comparator, and independence and sample selection are unverified. No historical re-fitting or new challenger tested.

## Research comparison / contrary evidence
- Ferro (2017), https://doi.org/10.1002/qj.3115 — observational errors distort forecast evaluation; directly motivates strict identity exclusions; no tennis population, no code copied, licensing not audited.
- Gneiting & Raftery (2007), https://doi.org/10.1198/016214506000001437 — proper scores, Brier/log loss preferable to accuracy alone for probability quality; theoretical, not a tennis benchmark; license/code not audited.
- Roberts & Leutbecher (2024), https://arxiv.org/abs/2410.06162 — calibration/evaluation uncertainty in weather forecasting; adapt uncertainty caution, not performance claims; preprint, implementation/license not audited.
No external accuracy numbers are compared with Tennis Genome without matched populations/horizons.

## Negative findings and operational blocker
- Exact-head CI is now green, but **actual blocked receipt artifact still not verified**: acquisition workflow checks out main and #430 is unmerged. A PR CI pass is insufficient.
- Existing immutable result proposal #428 still prevents new acquisition. Do not delete/merge without human provenance review.
- Two mismatched identities LS031/LS020 remain excluded. No new qualified forward observations established.

## Priority queue
1. Human review of #430 and #428. After safe review/merge, inspect first actual scheduled blocked-acquisition run's receipt, status, timestamp, artifact and absence of mutations; correct defects if observed.
2. Review #428 source hashes and one finished result, then safely resolve open proposal to restore new acquisition; do not waive identity/time gates.
3. Diagnose 13 unresolved IDs and match against retained provider bytes; report denominator, timestamps and failures.
4. With new locked qualified prospective observations, paired champion vs fixed 0.5 calibration Brier/log-loss with chronological slices and predeclared uncertainty; untouched final holdout.

No production promotion or unsafe merge.
