# PATTERN-CONFIRM-001 Pre-result Amendment 009 — Credentialed Dry-run Dispatch Boundary

Status: **frozen while prospective N = 0, before any credentialed provider dry run, and before any eligible post-cutoff outcome is inspected**

Amendments 003–008 define the real-provider transport, identity, state, source-package and live-ledger contracts. This amendment fixes the operational boundary for the first credentialed execution so that provider connectivity cannot accidentally become confirmatory evidence or mutate the prospective ledger.

No selected hypothesis, correction, alpha, O'Brien-Fleming boundary, look N, market definition, identity rule, state rule, source-package rule or promotion criterion changes.

## 1. Manual execution only

The credentialed provider dry run is exposed through a GitHub Actions `workflow_dispatch` workflow only. It is not scheduled, triggered by pushes, or triggered by pull requests.

The workflow must have read-only repository contents permission and must not possess a code-writing or ledger-writing permission.

## 2. Secrets contract

Credentialed execution reads only these runtime secrets:

- `THE_ODDS_API_KEY`
- `SPORTRADAR_API_KEY`

`SPORTRADAR_ACCESS_LEVEL` remains a non-secret execution parameter restricted to the already-supported `trial` or `production` values.

The workflow file must never contain a real key. Keys may not be echoed, passed as command-line arguments, persisted in artifacts, or written to repository files. The Odds API's provider-required `apiKey` query-parameter exception remains governed by Amendment 007: it may exist only in the in-memory outbound HTTPS request and any emitted diagnostic URL must have its query string removed.

## 3. Outcome-blind scope

The manual workflow may execute only the provider dry-run module frozen in Amendment 003 and later hardened amendments. It may:

- query the provider endpoints required by the dry-run contract;
- capture two outcome-blind provider snapshots at least 300 seconds apart;
- parse Pinnacle two-sided prices and pre-match Sportradar metadata;
- perform schema, identity-context, freshness and stability checks; and
- emit the deterministic dry-run snapshots/report.

It may not:

- call the settlement loader;
- request or parse a Sportradar match timeline for settlement;
- inspect a winner, score, result, retirement or walkover for a target match;
- append or modify the prospective live ledger;
- call `evaluate_live_family` or any confirmatory outcome evaluator;
- increment either selected hypothesis's N; or
- alter any frozen model or source artifact.

## 4. Artifact retention

The workflow may upload only the sanitized outcome-blind dry-run output directory produced by `pattern_confirm_provider_dryrun`.

The uploaded artifacts are operational QA evidence, not confirmatory model evidence. A transport-compatible report does not by itself authorize accumulation; the full internally generated state/source-package gate remains separately required by Amendments 003–008.

## 5. Failure handling

The dry-run output should be uploaded even when the dry-run process fails closed, so provider/schema failures remain auditable. After artifact upload, the workflow must propagate the dry-run failure as a failed workflow run.

Missing secrets fail closed. The workflow must not substitute dummy credentials or another provider.

## 6. Scientific status

At this amendment, no real provider credential has been used by the project, no credentialed dry run has been executed, and both selected hypotheses remain `ACCUMULATING, N=0`.

A future successful credentialed dry run establishes only that the real transport contract is operationally compatible. The first confirmatory N remains forbidden until all previously frozen identity, state, source-package, live-row and final actual-start gates also pass.
