# 2026-11-14 WTA acquisition discovery/eligibility boundary audit

## Hypothesis, baseline, and decision
H0: The official WTA index automatically expands the configured prospective intake universe. H1: Index is discovery/audit only and only explicitly configured tournaments are fetched and considered. Prespecified success for H1: index_role audit_and_discovery_only, configured target iteration, fixed 4-target config, no relaxation of prestart or identity checks. Result: **H1 supported by source-contract inspection (8/8 assertions passed)**. This is a static source audit, **not** a live fixture replay or predictive improvement.

## Exact evidence
Default branch source blob IDs at inspection:
- [intake-config.json](https://github.com/AidanDCM/Tennis-Genome-/blob/main/web-shadow/intake-config.json) `0431001e2cdf48a9742fba931344ac77a975562d`
- [intake core](https://github.com/AidanDCM/Tennis-Genome-/blob/main/scripts/web_shadow_wta_intake_core.py) `ee882869f857c403beea793d639f9689d05793a1`
- [acquisition core](https://github.com/AidanDCM/Tennis-Genome-/blob/main/scripts/web_shadow_wta_acquisition_core.py) `2400d69e99203a7acbf66ae6316bd0167fda5396`

The index is fetched and validated, but the manifest labels it `index_role: audit_and_discovery_only`. The actual tournament detail/match requests iterate over the four configured targets: Guangzhou, Tokyo, Hong Kong and Chennai (2026). An index refresh alone **cannot** expand the prediction population. This is an explicit trust boundary, not necessarily a bug.

## Reproduction (read-only)
```bash
python - <<'PY'
import json
from datetime import datetime,timedelta,timezone
from pathlib import Path
c=json.loads(Path('web-shadow/intake-config.json').read_text())
a=Path('scripts/web_shadow_wta_acquisition_core.py').read_text()
i=Path('scripts/web_shadow_wta_intake_core.py').read_text()
checks={
 'nonproduction': c['production_eligible'] is False,
 'unique': len({(t['group_id'],t['year']) for t in c['tournaments']})==len(c['tournaments']),
 'lead_window': (c['selection_rule']['minimum_lead_hours'],c['selection_rule']['maximum_horizon_hours'])==(8,48),
 'discovery_only': '"index_role": "audit_and_discovery_only"' in a,
 'configured_ids': 'configured_ids =' in a,
 'prestart': 'if start < minimum_start:' in i and 'if start > maximum_start:' in i,
 'upcoming': 'if match.get("MatchState") != "U":' in i,
 'identity': 'already_consumed' in i,
}
print(checks)
assert all(checks.values())
now=datetime.fromisoformat('2026-11-14T08:40:39+00:00')
print(now+timedelta(hours=8),now+timedelta(hours=48))
PY
```
Observed output: eight checks true; eligibility interval **2026-11-14 16:40:39 UTC to 2026-11-16 08:40:39 UTC** (observation time used for deterministic reproduction, not a verified provider snapshot).

## External methodological countercheck
- [Buhamra and Groll (2025)](https://arxiv.org/abs/2502.01613): rolling/expanding-window tennis models with Elo/age feature ablations and Brier evaluation; ATP Grand Slam population, not comparable to WTA prospective cohort; verify feature availability at forecast time.
- [Clegg and Cartlidge (2025)](https://research-information.bris.ac.uk/en/publications/tennis-match-outcome-prediction-using-temporal-directed-graph-neu/): temporal directed graph model reportedly comparable to weighted Elo, rather than a large guaranteed gain. ATP-focused and different tournament coverage; do not import claimed accuracy.
- [Unified Benchmark preprint (2026)](https://doi.org/10.20944/preprints202605.2002.v1): reports narrow improvements above Elo on a chronological ATP benchmark. Preprint, not independently reproduced here; sample composition and leakage controls need inspection.
No market inputs or restricted data are adopted. License of external implementation not audited, so no code copied.

## Negative results and evidence tiers
No new eligible prospective fixtures demonstrated. No model fit, calibration gain, settled sample increment, production champion modification, or CI result claimed. Prior repository WTA Web Shadow scorecard is non-production (47/86 accuracy; Brier 0.25132; log loss 0.69662; 15 pending); this iteration did not independently revalidate individual predictions or production-forward receipts.

## Prioritized executable queue
1. Fetch current official WTA index raw bytes with timestamp/hash; list upcoming tournaments with independently verified (group_id,year), date, surface and source evidence. Never auto-admit an index row.
2. On isolated branch add one verified tournament to nonproduction intake config, and run retained-source dry-run with exclusion reasons versus unchanged four-target baseline, including source hashes and time-of-observation.
3. Verify exact-head CI and review identity, cutoff, provenance and scorecard invariants before any operational activation.
4. Audit production frozen champion and prospective settlement receipts; only then preregister a single paired calibration/simplification challenger with chronological evaluation and untouched final holdout.
