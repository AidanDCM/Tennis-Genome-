# CAL-SEL-001 — Pre-Result Implementation Amendment 001

Status: **frozen before real ATP/WTA CAL-SEL-001 results are inspected**.

This amendment resolves deterministic implementation details left implicit in the original pre-registration. It does not change the registered hypotheses, models, calibrators, coverage levels, or promotion rules.

## Selective-prediction coverage

For a registered coverage fraction `c` and eligible population size `N`:

`keep_n = ceil(N * c)`

with a minimum of one row and a maximum of `N`.

Rows are ordered by descending `abs(calibrated_probability - 0.5)`. Exact confidence ties are broken deterministically by `(year, match_id)` and never by outcome.

All four registered calibration methods receive their own full fixed coverage curve. A calibration method is not selected first and then given privileged selective-prediction reporting.

## Disagreement buckets

Raw model disagreement remains:

`max(p_elo, p_strict_core, p_a_plus_b) - min(...)`.

Disagreement and probability-confidence quintiles are equal-count rank buckets, numbered 1 through 5 from low to high. Deterministic index order breaks exact numerical ties. The joint confidence × disagreement table is diagnostic only.

Disagreement diagnostics use the raw chronological model probabilities, not post-hoc calibrated probabilities. This keeps the question focused on whether independently structured model views disagree, rather than whether a shared post-hoc map moves them.

## Common calibration population

All four calibration methods are evaluated on the same outer years: only years for which at least 1,000 earlier out-of-sample strict-Core predictions exist and contain both outcome classes.

For outer year `Y`, each calibrator is fit only on strict-Core out-of-sample predictions from years `< Y`. The year's own outcomes are appended to history only after that year's predictions have been produced and scored.

## 2026 remains spent

No 2026 match is downloaded or consumed by the CAL-SEL-001 research workflow. The previously opened partial-2026 Core-v1 holdout cannot provide independent validation for any result in this installment.
