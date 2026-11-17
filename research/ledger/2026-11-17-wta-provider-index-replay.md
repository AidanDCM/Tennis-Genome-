# WTA retained provider index schema and discovery replay — 2026-11-17

**Tier:** research-only, non-production. No match predictions, settlements, or champion modifications.

## Frozen hypothesis and criteria
Hypothesis: the prototype's strict `endDate` ISO-date and integer identity assumptions match the retained official WTA index schema. Success requires every one of the 124 retained rows to be parseable, and candidate count to match the independently counted not-ended rows at the retained acquisition timestamp. Failure: any malformed/unknown identity/date, mismatch in counts, or prototype production eligibility.

## Reproducible source and sample
- PR branch prototype: `research/wta_index_discovery_prototype.py`, initial tested SHA `5b78a760b5c54c10f228c4be79ba2fc09546dd40` (https://github.com/AidanDCM/Tennis-Genome-/pull/518).
- Retained GitHub Actions run: https://github.com/AidanDCM/Tennis-Genome-/actions/runs/44043231031 ; artifact ID `14309603977`, ZIP files `tournament-index-2026-page-0.json` and `tournament-index-2026-page-1.json`.
- Timestamp used: `2026-11-17T08:01:39Z`. Records: 100 + 24 = 124.
- Exact reproduction: download artifact ZIP, import `discover` from `research.wta_index_discovery_prototype`, then:
```python
import json, zipfile
from research.wta_index_discovery_prototype import discover
with zipfile.ZipFile("github-actions-artifact-14309603977.zip") as z:
    pages = [json.loads(z.read(f"tournament-index-2026-page-{i}.json")) for i in (0,1)]
out = discover(pages, "2026-11-17T08:01:39Z")
print(out)
```

## Actual execution and result
Executed the prototype algorithm locally on all 124 actual retained index rows. Each row contained `tournamentGroup`, `year`, `startDate`, `endDate`, `status`. Both pages used ISO calendar `endDate` strings and integer group/year IDs. Result: **119 ended, 5 retained, 0 invalid, 0 duplicate**, `production_eligible=False`. Independent status tally: 119 `past`, 4 `future`, 1 `inProgress`. The retained candidates are:
- `2076/2026` Colina, ends 2026-11-22, inProgress
- `2052/2026` Buenos Aires, ends 2026-11-29, future
- `1118/2026` Quito, ends 2026-12-06, future
- `2056/2026` Angers, ends 2026-12-06, future
- `1072/2026` Limoges, ends 2026-12-20, future

The schema-mismatch hypothesis was **not supported** on this frozen sample; the strict prototype successfully parses these records. This does not demonstrate five playable or eligible matches: no individual fixture times, identity matching, or pre-start evidence has been established.

## Research cross-check and contrary evidence
Bunker et al., first published 2023-11-10, https://doi.org/10.1177/17543371231212235 uses expanding-year ATP evaluation; a 2025 comparison https://doi.org/10.1177/22150218251338954 finds expanding windows outperform other training strategies on its men's Grand Slam cohort. Both are evaluation design references, not transferable WTA performance claims; no restricted market inputs adopted. Real-time discovery changes cohort composition and must be evaluated on matched chronological prospective samples.

## Negative results, limits, queue
- No date-field mismatch or invalid identity observed on these 124 rows; this does not guarantee future provider schema stability.
- No new production-qualified N or model improvement; champion remains frozen.
- Next: add frozen provider-shaped regression fixture to PR #518 and rerun exact-head CI; validate future tournament status/date consistency and actual fixture capture; compare authorized four-event coverage with shadow discovery without modifying trust gates; only then test paired calibrated Elo on prospective matched observations.
