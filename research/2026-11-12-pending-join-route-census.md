# WTA Web Shadow pending join-route census — 2026-11-12

Status: **read-only, non-production; no settlements or predictions modified**.

## Hypothesis and preregistered classification

Hypothesis H1: all 15 pending predictions use source-MatchID keyed joins. Baseline: current `_match_row` in `scripts/web_shadow_wta_result_core.py`; exact source ID route requires `web:wta:<numeric group>:<year>:<MatchID>`, otherwise a legacy player-pair + round join. Success: 15/15 exact source-ID routes; failure: any legacy route. This tests join-route coverage, **not** whether a retained source row actually exists or a result can be settled.

Main scorecard blob: `c9636ac9d86c256ccf241e652b9456034c451fc3`; result core blob: `e4785a6d0b9b07c4fd4a52d2b44927211e5f7172`.

## Executed method and results

Fetched the raw `web-shadow/scorecard.json` and `scripts/web_shadow_wta_result_core.py` through the connected GitHub repository. Parsed all slate predictions and filtered `status == "PENDING"`. Classified each ID using `/^web:wta:\\d+:\\d+:[^:]+$/`, which reproduces the source-ID shape accepted in `_pending_predictions`.

- **15 pending**: **2** exact source-MatchID-route predictions (`web:wta:1074:2026:LS031`, `web:wta:1074:2026:LS020`); **13** legacy player-pair/round-route predictions.
- Legacy breakdown: **9 Seoul** and **4 Singapore**, all scheduled 2026-09-22 or 2026-09-23.
- Exact source-ID breakdown: **2 Hong Kong**, scheduled 2026-11-03 and 2026-11-04. Prior [artifact integrity audit PR #473](https://github.com/AidanDCM/Tennis-Genome-/pull/473) identified both as **player-pair conflicts**; they remain excluded.
- **15/15 have baseline_path** in the scorecard. This is a baseline-file reference, not proof of valid settlement.
- H1 **rejected**: only 2/15 have the exact ID route. The earlier acquisition compiler reported 13 unresolved and 2 identity conflicts; this census aligns with that partition, but does **not** independently inspect all 745 source rows or prove why each legacy join fails.

Reproduction (read-only after fetching the pinned scorecard):
```python
import json, re
d=json.load(open("web-shadow/scorecard.json"))
p=[x for s in d["slates"] for x in s["predictions"] if x["status"]=="PENDING"]
exact=[x for x in p if re.fullmatch(r"web:wta:[0-9]+:[0-9]+:[^:]+", x["match_id"])]
legacy=[x for x in p if x not in exact]
assert (len(p),len(exact),len(legacy)) == (15,2,13)
assert all(x.get("baseline_path") for x in p)
print("pending",len(p),"exact",len(exact),"legacy",len(legacy))
```

## Research and contrary evidence

- Nanayakkara, Christen & Christen (2025), *Unsupervised Evaluation of Entity Resolution*, https://doi.org/10.1145/3721985. Explains how missing/incomplete ground truth makes linkage precision and recall difficult to estimate; its multi-domain benchmarks are not tennis result feeds. Do not infer join correctness from mere name similarity. Implementation license not checked; no code imported.
- Papadakis et al. (2024), *A Critical Re-evaluation of Record Linkage Benchmarks*, https://openresearch-repository.anu.edu.au/entities/publication/07b8afae-b60f-4b2b-93c0-179f5ca4d5c9. Shows benchmark difficulty and selection matter; no tennis replication. Implementation license not checked.

## Forecast evidence and safeguards

Main's distinctly **non-production** shadow scorecard: 86 completed scored, 47 correct (54.65%), Brier 0.251322, log loss 0.696621; 89 terminal settlements and 79 Elo-paired comparisons; 15 pending. Fixed 0.5 gives Brier 0.25 and log loss approximately 0.693147. The frozen production champion and qualified independent forward N were not reverified. No forecast ablation, prospective settlement, model improvement, or source-row matching claim.

## Prioritized next executable queue

1. Download and independently classify each of the 13 legacy pending fixtures against the exact retained artifact #13967128659 (including source row availability, player pair, round, and tournament) **without auto-settlement**. Distinguish absent match rows, changed round labels, and player-pair mismatches.
2. On a separate research branch, add read-only diagnostic categories and fixture tests; fail closed, preserve identity and chronology gates; run pytest/Ruff and exact-head CI.
3. Test failed/skipped/blocked acquisition workflow states in a non-mutating harness.
4. After new qualified locked observations, paired chronological champion-vs-simple-baseline scoring with untouched holdout and uncertainty intervals.

No restricted data or outcome backfill, no champion change, no promotion or merge.
