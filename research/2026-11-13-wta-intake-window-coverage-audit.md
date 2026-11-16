# WTA acquisition intake-window coverage audit — 2026-11-13

Evidence tier: **read-only operational diagnostic, non-production**. No new predictions, settlements, or champion updates.

## Falsifiable hypothesis and baseline
H0: a broken source-fetch or missing zero-selection guard is necessary to explain no new WTA intake.
Alternative: the configured intake universe and fixed 8–48 hour lead window can yield an empty eligible set even with successful source fetch. Operational baseline is a successful fetch with zero selected, not a winner probability model.

## Pinned source and runs
- main checkout SHA in both runs: `40bb697ec786527b7ed1a4c67d6d0a92aea17782`
- intake config blob `0431001e2cdf48a9742fba931344ac77a975562d`
- result config blob `c9c443e6c84e40549e089a9a5c26b46e96b66a22`
- intake core blob `ee882869f857c403beea793d639f9689d05793a1`
- [Intake job](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/43495625075): source_count=4, 'No eligible unseen matches in the frozen intake window', no proposal; [retained artifact #14071382847](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/43495625075/artifacts/14071382847).
- [Result job](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/43472171946): source_count=10, 15 pending, 13 unresolved, 2 identity conflicts, 0 selected; [artifact #14060013326](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/43472171946/artifacts/14060013326).

## Executed deterministic source-contract check
Fetched three raw GitHub files using the GitHub connector; parsed both JSON configs and inspected the actual core function. Six of six assertions passed: 4 intake tournaments, all year 2026, intake subset of result config, 8–48h window, actual core computes lower and upper times from observed timestamp, and both configs prohibit production eligibility. Input observed-at `2026-11-13T19:48:25Z` yields selection window `2026-11-14T03:48:25Z` through `2026-11-15T19:48:25Z`. Intake events: guangzhou, tokyo, hong-kong, chennai.

Reproduce with:
```python
import json, datetime
from pathlib import Path
i=json.loads(Path("web-shadow/intake-config.json").read_text())
r=json.loads(Path("web-shadow/result-config.json").read_text())
t=datetime.datetime.fromisoformat("2026-11-13T19:48:25+00:00")
assert len(i["tournaments"]) == 4
assert all(x["year"] == 2026 for x in i["tournaments"])
assert all(any(x["group_id"]==y["group_id"] and x["year"]==y["year"] for y in r["tournaments"]) for x in i["tournaments"])
assert i["selection_rule"]["minimum_lead_hours"]==8 and i["selection_rule"]["maximum_horizon_hours"]==48
assert i["production_eligible"] is False and r["production_eligible"] is False
print(t+datetime.timedelta(hours=8), t+datetime.timedelta(hours=48))
```

## Interpretation / negative result
The source-failure hypothesis is not supported by these logs. An empty candidate set is consistent with the finite four-event 2026 configuration and November 14–15 intake window; **not proven solely by config**: retained raw fixture timestamps and per-row rejection reasons must be inspected before attributing every exclusion to stale tournament coverage. No claim that the 15 pending matches are unfinished or safely settleable. No forward champion denominator independently certified.

## Literature and adaptation
- Ferro (2017), [Measuring forecast performance in the presence of observation error](https://doi.org/10.1002/qj.3115): observational identity errors can alter scoring comparisons; independent outcome corroboration is required. Weather-forecast methods are not tennis performance estimates.
- Kleen (2024), [Scaling and measurement error sensitivity of scoring rules for distribution forecasts](https://doi.org/10.1002/jae.3056): proper scores respond differently to label error. Do not replace provenance checks with statistical correction. Published 2024, open-access article; no tennis-specific licensing or data coverage asserted.

## Prioritized next executable experiments
1. Download both retained source ZIPs; verify artifact digests, inspect each fixture timestamp, and count rejection reasons by tournament and gate; retain sample IDs and raw source SHA.
2. Verify whether a reviewed, forward-only next-event configuration can expand intake without weakening the pre-start lead and identity gates. Do not retroactively add events or predictions.
3. Independently crosswalk 13 unresolved and 2 conflicting identities against official evidence; no automatic settlements.
4. Reconcile frozen champion, qualified forward N, CI status, and prospective capture before one preregistered challenger; compare paired Brier/log loss with uncertainty and untouched final holdout.

No market, gambling, or wagering inputs used.
