# Iteration 38 — WTA active-results batch contract audit (2026-11-11 UTC)

## Hypothesis and prespecified checks
H1: pending PR #428 replaces the *active batch pointer*, rather than appending a new result to the existing pointer. Baseline main active-results.json; challenger PR #428 active-results.json. Success for a non-destructive append invariant would require old paths to be a subset of proposed paths. Negative result is recorded even if replacement is intentional. This is a **read-only, non-production workflow contract audit**, not a forecast-model experiment or a settlement decision.

## Inputs and source identities
- Main active-results.json Git blob: `52d8645a3389c9b2d8ba5a6c87e520e23ab80a25`.
- PR #428 proposed active-results.json Git blob: `3bd8dde18bc70f6c411bfc9a56151577b07340e7`; PR head `e676c961d674ffd32d254bb96f738ae7242e211f`.
- Main WTA result compiler: `scripts/web_shadow_wta_result_core.py` Git blob `e4785a6d0b9b07c4fd4a52d2b44927211e5f7172`, lines 667–733.
- Main non-production scorecard: `web-shadow/scorecard.json` Git blob `60082a6292087e2b6e902faca79f2f4c847d8fdb`.
- Main acquisition workflow: `.github/workflows/wta_web_shadow_results.yml` Git blob `2a698a6f56297aee054a94dc49a28fefaaff2d35`.
- Sample IDs: main `2026-11-08-hong-kong-2026-f-ls001-claire-liu-alexandra-eala-257608990b.json`; PR #428 `2026-11-09-chennai-2026-f-ls001-janice-tjen-magda-linette-42775ef387.json`.

## Reproducible experiment
Retrieve the two `web-shadow/active-results.json` files with GitHub contents API, at `main` and `automation/wta-web-shadow-results-wta-results-20261109t083951z`. Run:

```python
import json
from pathlib import Path
old=json.loads(Path("main-active-results.json").read_text())
new=json.loads(Path("pr428-active-results.json").read_text())
removed=set(old["result_paths"])-set(new["result_paths"])
added=set(new["result_paths"])-set(old["result_paths"])
checks={
 "schema_unchanged":old["schema_version"]==new["schema_version"],
 "old_nonempty":bool(old["result_paths"]),
 "proposed_nonempty":bool(new["result_paths"]),
 "prior_paths_preserved":not removed,
 "one_new_path":len(added)==1,
}
print(checks, sorted(removed), sorted(added))
assert checks["schema_unchanged"] and checks["one_new_path"]
assert not checks["prior_paths_preserved"]
```

## Observed output
The connector-backed JavaScript equivalent executed against raw GitHub file contents: `schema_unchanged=True`, `old_nonempty=True`, `proposed_nonempty=True`, `prior_paths_preserved=False`, `one_new_path=True`. One previous Hong Kong path is removed from the active pointer; one Chennai path is added. The code at lines 715–733 constructs `active_results` from only newly compiled `result_paths` and copies it over the existing pointer. **This is a confirmed batch-pointer replacement, not yet a proven data-loss bug**: prior result files and settled scorecard records can remain independently retained. No outcomes were changed or settled.

## Risk and negative findings
The append-preservation check FAILS. The replacement behavior is apparently deliberate in the compiler, so do **not** change to append without inspecting the settlement workflow's expected batch semantics, idempotency, and replay protection. PR #428 is still open, and the main acquisition workflow gate prevents new snapshots while it remains open. The current Web Shadow scorecard remains non-production: 46/85 correct (54.12%), Brier 0.251461, log loss 0.696908, pending 16. Current independently qualified forward N was **not refreshed** and must not be inferred from this historical scorecard. No champion modification, no model test, no prediction or settlement change.

## Research comparison (no external code imported)
- Pic et al. (2025), *Proper scoring rules for multivariate probabilistic forecasts based on aggregation and transformation*, https://doi.org/10.5194/ascmo-11-23-2025. Peer-reviewed, open access; numerical simulation and wind-speed forecasting evaluation. Transferable: audit evaluation target and multiple scoring perspectives, not tennis performance claims.
- Tennis API tournament draw documentation, https://docs.tennis-api.com/tournaments (accessed 2026-11-11). Third-party provider documentation; distinct IDs for editions, draw positions and match IDs. Transferable: separate edition and round identity; cannot prove official WTA RoundID semantics. No external code or licensed dataset used.

## Next executable queue
1. Read the actual WTA settlement workflow and tests to verify whether active-results is a transient batch pointer and whether prior settled results are durably retained. Add a synthetic replay/duplicate negative-control test if necessary.
2. Review PR #428 official source evidence and human disposition; never merge or bypass the existing acquisition gate autonomously.
3. Independently establish WTA RoundID semantics from retained official draw positions, with mismatches rejected.
4. Audit prohibited-source provenance in original prediction feature manifests.
5. Restore trustworthy new pre-start prospective capture; compare frozen champion to challengers using paired Brier/log loss and protected chronological samples.
