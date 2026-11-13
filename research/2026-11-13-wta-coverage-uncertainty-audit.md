# 2026-11-13 WTA capture coverage and uncertainty audit (read-only)

## Pinned sources and operational status
Main baseline `40bb697ec786527b7ed1a4c67d6d0a92aea17782`. Compiler `scripts/web_shadow_wta_result_core.py` fetched directly from main: numeric source RoundID 1->F, 2->SF, 3->QF, 4->R16, 5->R32. PR #479 remains open/draft, head `4a687c023b272496999dc45f95eaded0fb32d8a6`, mergeable true; its preceding code SHA `0db0353972244b6cf17e83e37465a2f713267140` passed Ruff and pytest in Actions #43367599685 (previously inspected). This iteration did **not** run exact-head CI. Open research PRs #475–#479 are not production evidence. Workflow path verified in main research source: `.github/workflows/wta_web_shadow_results.yml`; workflow execution/scheduling and production champion manifest not independently refreshed in this iteration.

## Falsifiable operational hypothesis and actual numerical execution
Hypothesis: the 86 scored non-production shadow observations provide a sufficiently narrow winner-accuracy uncertainty interval (95% Wilson width <= 0.15) to support a strong stand-alone accuracy claim. Prespecified failure: width >0.15. Comparison is the fixed 0.5 probability baseline; reported proper-score comparison is descriptive, **not paired inference**.

Executed Python standard-library calculation from previously verified aggregate scorecard values, not newly fetched scorecard rows:
```python
import math
n,k,z=86,47,1.95996398454
p=k/n
d=1+z*z/n
c=(p+z*z/(2*n))/d
h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
print(p,c-h,c+h,2*h,.251322-.25,.696621-math.log(2))
```
Observed: accuracy 0.5465116279069767, Wilson interval [0.4415616959142977, 0.6474840531754008], width 0.2059223572611031; Brier difference +0.001322; log-loss difference +0.00347381944 versus fixed 0.5. Hypothesis **rejected**. No per-match paired intervals, tour/surface strata, drift, calibration fit, or prospective challenger evidence computed because raw qualified per-match samples were not retrieved. The 86 scored/15 pending are **non-production WTA Web Shadow**, not production forward sample. Selection bias from unresolved capture remains possible.

## Operational negative evidence
Prior retained-source audit PR #478 found 12/13 legacy pending with unique player pairs but mismatched numeric round interpretation; one absent pair. Two separate exact-ID player conflicts remained unresolved. These are diagnostic findings, not authorized settlements. Never change locked predictions, reassign historical outcomes, or relax provenance gates. Main scorecard/champion SHA and qualified forward denominator were not independently verified in this run.

## Research and contrary evidence
- Bunker et al. (online 2023, journal 2024), https://doi.org/10.1177/17543371231212235 : ATP 2007–2020 expanding yearly chronological evaluation compared Elo with simpler logistic and more complex tree models. Transfer: enforce chronological splits and a strong simple baseline; published population is not WTA Web Shadow, external accuracy cannot be transferred. No code imported; publisher reuse terms require separate review.
- Buhamra & Groll (2025), https://arxiv.org/abs/2502.01613 : compare enhanced Elo/age features with and without augmentation using rolling/expanding windows, Bernoulli likelihood and Brier. Transfer: preregister feature ablation only after qualified prospective capture. Preprint; software license not checked.
- Tang, Wang & Jin (2025), https://arxiv.org/abs/2502.10985 : Elo can outperform richer alternatives under sparse nonstationary comparison data; contrary to complexity-first assumptions. Different domains and simulations; no tennis outcome claim imported. No external code used.
No prohibited market-derived inputs or external code used.

## Prioritized executable queue
1. Fetch current main scorecard and immutable production champion/verified-forward manifests; report exact SHAs, eligibility denominators and source chronology.
2. Review actual workflow schedule/gates and run diagnostics; audit missing capture before changing model.
3. Build **read-only** mismatch reason report with negative identity controls; adjudicate 12 candidates against retained source and independent pre-start evidence, never auto-settle.
4. Run qualified prospective champion vs simple 0.5/Elo baseline using paired Brier/log-loss and Wilson intervals, with chronological cohorts and untouched final holdout.
5. Only then preregister one simplification or calibration challenger; keep frozen champion intact.
