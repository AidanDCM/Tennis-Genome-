# Soul Lights offline readiness milestone 001

Date: 2026-10-02. Source branch: `soul-lights-offline-readiness`.

Run `PYTHONPATH=src python scripts/check_frozen_input_readiness.py` under the pinned project runtime. The check is read-only and uses zero Sportradar requests. It verifies the production bundle through the supported calculator loader, including the two neighbor banks, then lists the frozen Core fields, ATP Profile fields, WTA serve/return fields and candidate canonical history paths.

Observed in a clean worktree from `ed715aa`:

- Sealed bundle verified: `7a5874325d57d4fa670e5515607a2ec6a02ecedc9fdfb87338367e8e4556a2f1`.
- Frozen Core dimensions: ATP 38, WTA 32.
- Before restoration, the checked canonical pre-match, outcome and stats Parquet files were absent. The command marked both tours as unable to produce a verified live prediction from that state.
- The pinned archive at commit `83733587353df8a41f2fd4f516147d5aa83f5a8d` was downloaded in one GitHub archive transfer and restored with `scripts/restore_pinned_research_history.py`. The canonical rebuild matched both accepted frozen content hashes: ATP `00cef02ed493fbb7338415365648a3150b8c71953609013ab6759e57154b04ff` with 77,850 rows, and WTA `4bb0803a6324d0229a949ca29aeb31720beb693f854044bdc704202a5e593124` with 71,419 rows. The new readiness check sees complete candidate files for both tours. These local `data/` files are ignored and are not being committed or redistributed.
- File presence alone cannot prove current state, identity, chronology or source rights. The checker intentionally never emits `prediction_ready=true` on a file existence check.

The persistent `BudgetedSportradarStore` now provides a bounded local transport layer for the next development step. It retains successful response bodies by hash, counts outbound attempts including failures, enforces local daily and rolling seven-day ceilings, serializes reservations through SQLite and blocks concurrent requests to the same endpoint. Offline replay uses retained bytes without a credential or provider request. Unit tests use an injected fake transport and make zero live calls.

This store is **not** yet the formal trusted-capture path. It does not retain response headers, provider generation time, pagination completeness, or external anchor receipts. Those existing `prospective/` contracts must remain the source of formal eligibility. Do not route registered predictions through this cache until the trusted evidence wrapper and an end-to-end test bind its bytes to those contracts.

The same pinned archive contains partial 2026 ATP/WTA CSVs, but both stop at tournament date 2026-05-25; its latest commit was 2026-06-25. The archive's current `main` still points to that same commit at this check. It cannot supply the missing June–October state needed for today's targets.

Next implementation target: obtain an admissible 2026 continuation without repeated full-season fetching, then reproduce one ATP and one WTA target input end to end offline. The matched 2000–2025 research history remains `research_allowed` under CC BY-NC-SA 4.0; it is not commercial-use clearance. Quantify the exact remaining provider requests before any bulk historical capture.
