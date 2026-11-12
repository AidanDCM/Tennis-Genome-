# Pending WTA shadow aging and selection audit — 2026-11-12

**Non-production, read-only.** Source: [main scorecard](https://github.com/AidanDCM/Tennis-Genome-/blob/40bb697ec786527b7ed1a4c67d6d0a92aea17782/web-shadow/scorecard.json), blob `c9636ac9d86c256ccf241e652b9456034c451fc3`. Compiler: [result core](https://github.com/AidanDCM/Tennis-Genome-/blob/40bb697ec786527b7ed1a4c67d6d0a92aea17782/scripts/web_shadow_wta_result_core.py), blob `e4785a6d0b9b07c4fd4a52d2b44927211e5f7172`. Evaluation timestamp fixed **2026-11-12T21:46:06Z**.

## Prespecified falsifiable question
Hypothesis: fewer than half of pending predictions are over 30 days past their recorded scheduled start. Baseline: all 15 PENDING entries in the immutable scorecard, not only matches with outcomes. Failure if >= 8 are over 30 days. Age is an operational latency measure **not proof that a match occurred or should be settled**.

## Actual experiment
Parsed complete scorecard via connected GitHub; flattened PENDING entries; computed UTC differences from scheduled_start, grouping by match ID tournament component. **15/15 have scheduled start before evaluation time; 13/15 are over 30 days (also over 45 days); age range 8.657–51.782 days.** Hypothesis rejected. Nine Seoul and four Singapore entries are September legacy identifiers; two Hong Kong official-ID entries are November fixtures with independently documented player-identity conflicts ([PR #473](https://github.com/AidanDCM/Tennis-Genome-/pull/473)). The 13 legacy entries remain unresolved, not newly scored. No missing outcome was imputed.

Sample IDs (legacy): `web:wta:seoul:2026:r32:sakatsume-preston`, `ruse-lys`, `montgomery-park`, `zarazua-bondar`, `ma-jones`, `ku-ibragimova`, `birrell-zidansek`, `zakharova-ostapenko`, `kenin-charaeva`; Singapore `r32:oliynykova-wolff`, `r32:parks-yamaguchi`, `r16:sasnovich-andreeva`, `r16:anisimova-gibson` (each prefixed `web:wta:singapore:2026:`). Exact ID cases: `web:wta:1074:2026:LS031`, `web:wta:1074:2026:LS020`.

### Reproduction (Node.js or browser JS with supplied scorecard JSON)
```javascript
const d=JSON.parse(require('fs').readFileSync('web-shadow/scorecard.json','utf8'));
const now=Date.parse('2026-11-12T21:46:06Z');
const pending=d.slates.flatMap(s=>s.predictions.filter(p=>p.status==='PENDING'));
const days=pending.map(p=>(now-Date.parse(p.scheduled_start))/86400000);
console.log({pending:pending.length,older30:days.filter(x=>x>30).length,
  older45:days.filter(x=>x>45).length,min:Math.min(...days),max:Math.max(...days)});
if(pending.length!==15 || days.filter(x=>x>30).length!==13)throw Error('unexpected cohort');
```

## Forecast evidence and caveats
Scorecard non-production: 47/86 = 54.65% winner accuracy, Brier 0.251322418, log loss 0.696621201; fixed 0.5: Brier 0.25, log loss 0.693147181. 89 terminal settlements, 86 completed scored, 79 Elo-paired. No independently reverified production champion checksum or qualified forward N. Missingness may depend on tournament, identity route and source availability; observed-only accuracy is not automatically representative of all locked forecasts. No causal explanation established for 13 legacy failures.

## Research comparison
- Pagano et al. (2024), [Challenges of Operational Weather Forecast Verification and Evaluation](https://doi.org/10.1175/BAMS-D-22-0257.1): operational coverage, verification data and monitoring can be bottlenecks; weather rather than tennis, no code imported, article reuse license not checked.
- Dominitz & Manski (2024), [Comprehensive OOS Evaluation](https://www.nber.org/papers/w32269): evaluate across populations and distribution shift; theoretical/illustrative setting, not a direct tennis implementation, working paper access, implementation license not established.
- Webster-Clark & Ross (2024), [Validity of Complete Case Analysis Depends on the Target Population](https://arxiv.org/abs/2401.15514): contrary caution on generalizing complete-case results; causal epidemiology rather than sports, do not mechanically apply its estimators.

## Negative findings, boundaries and next executable queue
1. **Priority:** inspect all 13 legacy prediction identities against retained 745 source rows, distinguishing absent match, event/round mismatch, player pair mismatch and incomplete state; no automatic settlement or historical identity rewrite.
2. Add diagnostic-only mismatch categories with regression tests on an isolated branch; run pytest, Ruff, exact-head CI, and inspect output.
3. Test acquisition blocked/failed/skipped gate states in isolation, with writes disabled.
4. Only after genuinely new locked, qualified outcomes, run prespecified chronological paired Brier/log-loss comparisons, calibration and selective coverage, preserve final holdout.

No model ablation fitted this run; the falsifiable test concerns evidence capture latency and selection. No model, champion, predictions, settlements or gates changed.