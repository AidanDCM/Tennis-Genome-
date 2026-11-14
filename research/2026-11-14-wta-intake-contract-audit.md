# 2026-11-14 WTA intake coverage contract audit (read-only)

## Scope and falsifiable hypothesis
H0: the configured non-production WTA intake tournament IDs are inconsistent with the result source configuration, preventing downstream matching.
Comparison: exact (group_id, year) identity membership, uniqueness, production flags, and fixed-universe size. Success: all five source-contract assertions pass; failure: any assertion fails. This is an operational contract test, not a prediction model evaluation.

## Reproducible evidence
Default branch `main` source files (GitHub content blob SHA):
- [intake-config.json](https://github.com/AidanDCM/Tennis-Genome-/blob/main/web-shadow/intake-config.json) SHA `0431001e2cdf48a9742fba931344ac77a975562d`
- [result-config.json](https://github.com/AidanDCM/Tennis-Genome-/blob/main/web-shadow/result-config.json) SHA `c9c443e6c84e40549e089a9a5c26b46e96b66a22`

Reproduce with:
```bash
python - <<'PY'
import json
from pathlib import Path
a=json.loads(Path('web-shadow/intake-config.json').read_text())
b=json.loads(Path('web-shadow/result-config.json').read_text())
keys=lambda x:[(t['group_id'],t['year']) for t in x['tournaments']]
x=keys(a); y=set(keys(b))
checks={
 'nonproduction': a['production_eligible'] is False and b['production_eligible'] is False,
 'unique_intake': len(x)==len(set(x)),
 'covered_by_results': all(z in y for z in x),
 'same_year': all(t['year']==2026 for t in a['tournaments']),
 'finite_four': len(x)==4,
}
print(checks)
assert all(checks.values())
PY
```

## Observed execution
All **5/5** deterministic checks passed in an independent JS reproduction against the two fetched GitHub blobs. Intake IDs: `(1023,2026), (1056,2026), (1074,2026), (1148,2026)`; result source covers 10 tournaments. Intake rule: minimum 8 hours, maximum 48 hours, max 8 matches per slate.

**Negative finding:** configuration mismatch is not supported. **Positive bottleneck:** intake coverage remains exactly four fixed 2026 tournaments; earlier [PR #500](https://github.com/AidanDCM/Tennis-Genome-/pull/500) audited 243/243 final records in its retained Nov 13 fixture snapshot. This run did not fetch a new official tournament index or establish a new upcoming event. No claim that widening the config alone would create qualified observations.

## Research and contrary evidence
- Bunker et al. (first published 2023), [chronological tennis Elo/ML comparison](https://doi.org/10.1177/17543371231212235): expanding annual training windows, 2007–2020 ATP evaluation. Adapt its strict chronology and simple baselines; ATP population and feature coverage are not directly comparable to this WTA shadow. The paper also discusses external information not permitted in this project; **do not import such features**.
- Buhamra and Groll (2025), [statistically enhanced tennis modeling](https://arxiv.org/abs/2502.01613): ablations of Elo/age features with rolling and expanding windows, external test evaluation; promising comparison design, but Grand Slam men's coverage differs and no transferable performance claim is justified.
- Contrarian lesson: more features may not solve missing, unqualified prospective samples; first validate coverage, provenance and calibration.

## Trust and performance
No model change or production promotion. Immutable champion and qualified prospective forward denominator were not independently verified in this iteration. Main WTA Web Shadow scorecard read: **47/86 correct (54.65%), Brier 0.2513224, log loss 0.6966212, 15 pending, production_eligible=false**. Those are not champion forward metrics. Pending identities remain unresolved and must not be backfilled.

## Prioritized executable queue
1. Retrieve the **official current** WTA tournament index and fixture schedule, independently verify future tournament IDs, dates, pre-start timestamps and provider licenses before any proposed forward-only coverage PR. Preserve fixed lead-time and identity gates.
2. Compare newly fetched candidates to existing IDs in intake/result configs, generate a dry-run report with rejected/eligible counts; do not write predictions.
3. Independently adjudicate 15 pending WTA shadow identities from pinned official sources without auto-settlement.
4. Verify frozen champion and qualified forward receipts, then preregister a paired prospective shrinkage-vs-champion comparison (Brier/log loss, calibration, confidence intervals) on newly locked pre-start samples.

No historical prediction, settlement, trust gate or production file changed.
