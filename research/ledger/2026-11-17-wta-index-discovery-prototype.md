# WTA read-only index discovery prototype — 2026-11-17

Status: research-only, **not connected to workflow or production selection**.

## Hypothesis / frozen criteria
A conservative discovery filter can reject ended tournaments, malformed identities/dates and duplicate index entries without changing intake authorization. Success: exactly one of six synthetic rows retained, five excluded by reason; timezone-naive observation rejected; no production eligibility.

## Sources
- Main base SHA: `7332fb703a67b442cc918db7273f5a5e8a045e6c`
- Acquisition implementation blob `2400d69e99203a7acbf66ae6316bd0167fda5396`: https://github.com/AidanDCM/Tennis-Genome-/blob/main/scripts/web_shadow_wta_acquisition_core.py
- Intake config blob `0431001e2cdf48a9742fba931344ac77a975562d`: https://github.com/AidanDCM/Tennis-Genome-/blob/main/web-shadow/intake-config.json
- Retained artifact run https://github.com/AidanDCM/Tennis-Genome-/actions/runs/44043231031 (artifact 14309603977); **not re-downloaded here**.
- Probabilistic evaluation: Gneiting & Raftery (2007), https://doi.org/10.1198/016214506000001437 . The discovery prototype is not a forecasting model.

## Execution
Local prototype tests: `python -m unittest -v test_discovery.py` => 3 tests passed, 0 failures. This was run against a locally equivalent prototype, before publishing these files. Re-run committed version with `python -m pytest -q tests/test_wta_index_discovery_prototype.py` and `python -m ruff check research/wta_index_discovery_prototype.py tests/test_wta_index_discovery_prototype.py`; exact-head CI has not yet been verified.

Synthetic IDs 1–5; reference timestamp 2026-11-17T12:00:00Z; retained group 2/2026, ended 1, duplicate 1, invalid 3. No real match IDs, predictions or settlements.

## Limitations / contrary evidence
The real retained WTA index date field name and formatting are **not yet independently confirmed**; `endDate` is a deliberately strict exploratory assumption. If source dates are timestamps or use another field, all rows may be excluded. The candidate list is not evidence of playable matches: fixture identities, pre-start times, source SHA and provenance must be checked separately. No accuracy gain, production-qualified sample increase, CI success or live coverage improvement claimed.

## Next queue
1. Download retained index JSON and verify date field schema; add actual frozen-provider fixture regression.
2. Run exact-head Ruff/Pytest/CI; fix any failure before considering review.
3. Compare shadow-only discovery with four static configured events, preserving non-production and all trust gates.
4. Reconcile prospective capture and settlement before any paired Elo/champion evaluation.

Champion unchanged. No odds, wagering, model promotion or gate relaxation.
