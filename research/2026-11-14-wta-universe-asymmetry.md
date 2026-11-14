# WTA intake/result universe asymmetry — 2026-11-14 02:44 UTC

## Hypothesis, preregistered comparison, and decision
H0 (operational): every tournament already configured for result retrieval is also eligible for prospective intake. Compare the **sets of (year, group_id)** in the two immutable `main` configuration blobs. Reject H0 if the result-only set is nonempty; do not infer that adding old events would produce new pre-start predictions.

**Observed: reject H0.** Intake has 4 unique events; results has 10; all 4 intake IDs are in results, but 6/10 (60%) result IDs are absent from intake: singapore, seoul, beijing, wuhan, osaka, ningbo. No mismatch in the intake-to-result direction. This is a *directional universe asymmetry*, not evidence of a broken settlement join or six available upcoming events. No probability model was trained or changed.

## Immutable sources
- Main commit: [6b2b6855054fadf3801fd10ea0cf5290a965f067](https://github.com/AidanDCM/Tennis-Genome-/commit/6b2b6855054fadf3801fd10ea0cf5290a965f067)
- [Intake configuration](https://github.com/AidanDCM/Tennis-Genome-/blob/6b2b6855054fadf3801fd10ea0cf5290a965f067/web-shadow/intake-config.json), Git blob `0431001e2cdf48a9742fba931344ac77a975562d`
- [Result configuration](https://github.com/AidanDCM/Tennis-Genome-/blob/6b2b6855054fadf3801fd10ea0cf5290a965f067/web-shadow/result-config.json), Git blob `c9c443e6c84e40549e089a9a5c26b46e96b66a22`
- [Non-production WTA scorecard](https://github.com/AidanDCM/Tennis-Genome-/blob/6b2b6855054fadf3801fd10ea0cf5290a965f067/web-shadow/scorecard.json), Git blob `c9636ac9d86c256ccf241e652b9456034c451fc3`
- [Main's pre-start coverage note](https://github.com/AidanDCM/Tennis-Genome-/blob/6b2b6855054fadf3801fd10ea0cf5290a965f067/docs/notes/2026-11-14-prestart-coverage-001.md): 3 future singles slots, 1 fully identified pairing, **0** supported with legal calculator state. Source observation was 2026-11-13 22:56 UTC.
- [Prior retained acquisition artifact](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/43495625075/artifacts/14071382847): prior audit reports 243/243 final, no upcoming fixtures in four-event intake universe. Not re-downloaded in this experiment.
- [PR #501 CI](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/43542218870) succeeded on PR merge ref; this is not proof of literal-head CI.

## Reproduction
```bash
python - <<'PY'
import json, urllib.request
sha='6b2b6855054fadf3801fd10ea0cf5290a965f067'
base=f'https://raw.githubusercontent.com/AidanDCM/Tennis-Genome-/{sha}/web-shadow/'
def read(name):
    with urllib.request.urlopen(base+name, timeout=20) as f: return json.load(f)
a=read('intake-config.json'); b=read('result-config.json')
key=lambda x:(x['year'],x['group_id'])
A={key(x) for x in a['tournaments']}
B={key(x) for x in b['tournaments']}
print('intake',len(A),'results',len(B),'intake_missing_in_results',sorted(A-B))
print('results_only',sorted((x['slug'],key(x)) for x in b['tournaments'] if key(x) not in A))
assert len(A)==4 and len(B)==10 and not A-B and len(B-A)==6
PY
```
Execution performed against fetched GitHub raw file contents using JavaScript JSON parsing and set arithmetic: intake 4; results 10; missing 0; results-only 6; result-only fraction 0.6. The command above is the independently reproducible Python equivalent, **not** claimed to have been executed.

## Model evidence, scope and negative results
Non-production WTA Web Shadow: 47/86 correct (54.65%), Brier 0.2513224181, log loss 0.6966212009, 15 pending. Constant 0.5 Brier 0.25, log loss 0.69314718. No qualified prospective champion denominator was independently re-established. The six result-only tournaments are historical; the result-only fraction is not forecast coverage or a performance metric. The prior identity audit has 12 round discrepancies, 1 absent pair, 2 conflicts, not newly adjudicated.

## Methodology / contrary evidence
- Gneiting & Raftery (2007), [Strictly Proper Scoring Rules](https://doi.org/10.1198/016214506000001437): proper probability evaluation rather than raw hit rate; does not solve missing pre-start capture.
- Choe & Ramdas (2023), [Comparing Sequential Forecasters](https://doi.org/10.1287/opre.2021.0792): sequential paired comparisons once locked forward data exists; no implied gain on this population.
- [pytest parameterization documentation](https://docs.pytest.org/en/stable/how-to/parametrize.html): reproducible CI collection auditing, not a tennis benchmark.
No external performance claims transferred; paper licenses/data access not independently audited this run. Contrary explanation: deliberate result retrieval for past settled events can be broader than future intake by design.

## Prioritized next executable queue
1. Obtain current *official* event index and fixture times; record source, capture timestamp, player identity and event format, and verify **future** fixtures within 8–48h before any forward-only config proposal. No automatic inclusion of historical result-only events.
2. Read live workflow run and selection rejection reasons; test candidate count before and after a proposed *future-only* intake extension in a dry-run, keeping all timing, identity, and provenance gates.
3. Audit frozen champion SHA and qualified forward receipt denominator independently. Preserve 15 pending WTA shadow identities without retrospective settlement.
4. After a fresh locked paired cohort exists, preregister one shrinkage challenger versus frozen champion and 0.5 reference, with paired Brier/log loss, Wilson accuracy interval, chronological slices, and untouched final holdout.

**Safety:** research-only ledger; no model, champion, prediction, settlement, gate, or production changes. Human review required.
