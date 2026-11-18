# WTA Web Shadow intake cadence/window audit — 2026-11-17

Status: non-production research only. No prediction, settlement, champion, or evidence-gate changes.

## Frozen source evidence
- Configuration: https://github.com/AidanDCM/Tennis-Genome-/blob/0431001e2cdf48a9742fba931344ac77a975562d/web-shadow/intake-config.json (Git blob SHA `0431001e2cdf48a9742fba931344ac77a975562d`)
- Workflow: https://github.com/AidanDCM/Tennis-Genome-/blob/main/.github/workflows/wta_web_shadow_intake.yml (schedule `23 */6 * * *`).
- Historical 2026-11-17 acquisition: https://github.com/AidanDCM/Tennis-Genome-/actions/runs/44043231031 ; artifact `14309603977`. Prior inspection reported 243 raw matches from four ended tournaments; this run did **not** re-download that artifact.

## Prespecified hypothesis and method
H0: For a fixture known to the source and remaining unchanged, the 8–48-hour pre-start eligibility window plus six-hour sampling cadence itself creates a sampling blind spot.
H1: The cadence covers every match with at least one scheduled scan 8–48 hours before start, assuming a functioning acquisition, sufficiently timely fixture publication, and no execution delay.

Synthetic population: integer start offsets 0 through 71 hours relative to a fixed scan at hour zero; scans at hours 0,6,...,60. No real matches or post-start data used.

Reproduce with Node.js:

```js
const scans = Array.from({length:11}, (_,i)=>6*i);
const count = Array.from({length:72}, (_,t)=>scans.filter(h=>t-h>=8 && t-h<=48).length);
const checks = [
  count.slice(0,8).every(n=>n===0),
  count[8]===1,
  count.slice(8,61).every(n=>n>0),
  count.every(n=>n<=7)
];
if(!checks.every(Boolean)) process.exit(1);
console.log(count.reduce((o,n)=>(o[n]=(o[n]||0)+1,o),{}));
```

## Executed result
Four of four assertions passed in an independent JavaScript execution. Counts of scan opportunities over 72 synthetic fixture start offsets: 0 opportunities: 8; 1: 6; 2: 6; 3: 6; 4: 6; 5: 6; 6: 10; 7: 24. The 8 earliest starts cannot qualify when observation begins at time zero; all starts from hour 8 through hour 60 have at least one qualifying scan.

**Interpretation:** Under ideal source freshness and uninterrupted six-hour runs, cadence alone is not the reason for missing fixtures whose starts are at least eight hours ahead. This does not establish real-world coverage: stale configured tournaments, source publication delays, missing identities, cancelled runs, or run timing can still eliminate observations.

## Research connection / contrary evidence
Strictly proper scoring rules reward calibrated probabilistic forecasts: Gneiting & Raftery (2007), https://doi.org/10.1198/016214506000001437 . This synthetic test measures capture opportunity, **not** forecast quality. Do not compare its 72 synthetic offsets to a real accuracy denominator.

## Next prioritized executable work
1. Inspect current official index schema and build read-only event discovery with explicit ended-event rejection and provenance, without broadening production authorization.
2. Test with frozen index fixtures plus invalid dates/identities and exact-head CI; compare selected fixtures against current static config.
3. Reconcile actual shadow intake proposals and qualified forward settlements before any model challenger assessment.

Negative result: No cadence-only blind spot under the stated idealized assumptions. Limitations: artificial offsets, no actual fixture schedules, no current prospective qualified N. Frozen champion untouched.
