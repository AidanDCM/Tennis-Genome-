# Cohort-denominator and paired-baseline audit — 2026-11-12

## Sources and question
Read main [WTA shadow scorecard](https://github.com/AidanDCM/Tennis-Genome-/blob/main/web-shadow/scorecard.json), blob `60082a6292087e2b6e902faca79f2f4c847d8fdb`, and [WTA acquisition workflow](https://github.com/AidanDCM/Tennis-Genome-/blob/main/.github/workflows/wta_web_shadow_results.yml), blob `2a698a6f56297aee054a94dc49a28fefaaff2d35`. At inspection [result proposal #428](https://github.com/AidanDCM/Tennis-Genome-/pull/428) and safety chain [#457](https://github.com/AidanDCM/Tennis-Genome-/pull/457), [#458](https://github.com/AidanDCM/Tennis-Genome-/pull/458), [#461](https://github.com/AidanDCM/Tennis-Genome-/pull/461) remain open. No new verified qualified production-forward sample established.

**Prespecified audit question:** Do the main scorecard's Elo and fixed-0.5 comparisons use the same eligible cohort? Success = matching N; failure = mismatched N. This is an audit, not a newly fitted model or a claim of prospective advantage.

## Reproduction (Python 3, standard library)
```python
import json, math
from pathlib import Path
s=json.loads(Path("web-shadow/scorecard.json").read_text())
m=s["metrics"]; c=s["baseline_comparison"]
assert m["settled_match_count"]==85
assert c["settled_match_count"]==78
print("Elo cohort N",c["settled_match_count"])
print("Elo minus genome Brier",c["baseline"]["brier_score"]-c["genome"]["brier_score"])
print("Elo minus genome log loss",c["baseline"]["log_loss"]-c["genome"]["log_loss"])
print("full shadow N",m["settled_match_count"])
print("fixed 0.5 minus shadow Brier",0.25-m["brier_score"])
print("fixed 0.5 minus shadow log loss",math.log(2)-m["log_loss"])
print("paired Elo cohort fraction of scored",c["settled_match_count"]/m["settled_match_count"])
```

## Executed numerical result
- Elo paired cohort N=78, 41/78 Genome correct vs 42/78 Elo correct; Brier Elo-minus-Genome **+0.0073123630**, log-loss **+0.0240368962** (positive favors Genome on this cohort).
- All scored WTA shadow N=85, 46/85 correct; fixed-0.5-minus-Genome Brier **-0.0014610585**, log-loss **-0.0037610927** (negative favors fixed 0.5 on this different cohort).
- Elo-paired coverage is 78/85 = **91.76%** of scored shadow observations; seven are not in the baseline comparison. Scorecard separately lists 88 settled and 16 pending; neither is the denominator of the 78-match comparison.
- **Hypothesis rejected:** the two comparisons do not share a denominator. They are not mutually contradictory, but cannot be used to rank Elo versus fixed-0.5 or claim generalized improvement without matching exact match IDs and paired losses.
- Only aggregates were used. No chronological per-match paired confidence interval, statistical test, calibration fit, or production result was computed. No label was backfilled.

## Operational finding
Main workflow still gates downstream steps with `steps.pr_gate.outputs.blocked != 'true'`; a failed/skipped gate can leave an empty output and thus satisfy that expression. An open result proposal can cause a successful job with acquisition steps skipped. Existing proposal protection must remain intact; review the already-tested fail-closed chain, not bypass it.

## Research and contrary evidence
- Diebold and Mariano (1995), [Comparing Predictive Accuracy](https://doi.org/10.1080/07350015.1995.10524599), studies paired loss differentials with serial dependence; inference needs actual paired chronological observations, not just aggregate score differences. Journal article, no software imported; implementation license not applicable.
- Pohle, Zahn and Lerch (2026), [Uncertainty Quantification in Forecast Comparisons](https://arxiv.org/abs/2605.03997), examines simultaneous uncertainty across multiple comparisons, contrary to treating repeated single-score improvements as decisive. Preprint; implementation reproducibility/license not verified. Neither study is a WTA replication.

## Next executable queue
1. Review [#428](https://github.com/AidanDCM/Tennis-Genome-/pull/428) against immutable identity and provenance; preserve two Hong Kong exclusions and do not merge automatically.
2. Execute isolated no-write GitHub Actions gate-state tests and review dependent [#457](https://github.com/AidanDCM/Tennis-Genome-/pull/457), [#458](https://github.com/AidanDCM/Tennis-Genome-/pull/458), [#461](https://github.com/AidanDCM/Tennis-Genome-/pull/461).
3. On newly locked, qualified predictions, align exact match IDs for Genome, Elo, and 0.5; report missingness, chronological paired Brier/log loss, uncertainty and surface/tour splits; retain final holdout.

No model, champion, result, settlement, or safety gate changed. No market-derived data used.
