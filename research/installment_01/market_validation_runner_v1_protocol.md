# MARKET-VALIDATION-RUNNER-v1 protocol

Status: **preregistered before implementation**

## Purpose

Create an auditable orchestration layer for the real licensed Betfair validation sequence. This runner does **not** create new predictive models, change any frozen statistical gate, or inspect market outcomes early. Its job is to make the permitted execution order explicit and fail closed when artifacts are missing, mutated, inconsistent, or scientifically premature.

## Frozen stage order

1. `BASIC-PREFLIGHT-001` (optional procurement stage, outcome-blind).
2. ADVANCED/PRO source manifest freeze.
3. `MARKET-HIST-001` reconstruction.
4. `MARKET-HIST-QA-001` quality gate.
5. `POWER-MDE-001` outcome-blind feasibility analysis.
6. Freeze the exact QA + power artifacts for the source bundle.
7. Only then permit outcome-bearing `MARKET-EDGE-001`.
8. Only then permit outcome-bearing `MARKET-EDGE-ADV-001`.

The runner must never silently skip a required predecessor. BASIC-PREFLIGHT is the only optional stage because licensed ADVANCED/PRO may be purchased conservatively without BASIC.

## Scientific boundaries

- 2026 remains spent and forbidden in frozen market experiments.
- The independent tennis engine remains market-blind.
- QA eligibility is not a model-performance result.
- POWER-MDE reads no winners and cannot promote or rescue a tennis signal.
- MARKET-EDGE outcomes cannot be opened until QA and POWER-MDE artifacts for the exact source bundle are frozen.
- The runner must not alter any existing promotion threshold, signal definition, market-price transform, Holm family, calibration adversary, or sample filter.

## Artifact identity

Every stage ledger entry must record:

- stage name;
- status;
- input artifact SHA-256 values;
- output artifact SHA-256 when present;
- exact command/module identity;
- timestamp of ledger creation;
- predecessor artifact hashes;
- blocking reason when not runnable.

The complete ledger receives a deterministic SHA-256 over its scientific content. Runtime timestamps are metadata and must not be included in the deterministic scientific digest.

## Required gate semantics

### Before MARKET-HIST

A confirmatory source manifest must declare ADVANCED or PRO, an interval no earlier than 2015-04-01, and an end no later than 2025-12-31.

### Before POWER-MDE

`MARKET-HIST-QA-001` must not be structurally blocked. POWER-MDE may run for a tour only on the market population actually represented by the frozen market artifact. Its report remains outcome-blind.

### Before MARKET-EDGE / MARKET-EDGE-ADV

The exact MARKET-HIST records used by the edge experiment must be the records referenced by the QA/power execution ledger. The runner must require frozen QA and power artifacts before allowing an outcome-bearing stage.

`MARKET-EDGE-ADV-001` retains its stricter existing requirement that ATP and WTA both be `ELIGIBLE_CONFIRMATORY` for the frozen four-claim family.

## Non-claims

A successful runner means only that the experiment sequence was executed reproducibly and in the permitted order. It does not imply market edge, positive EV, CLV, ROI, profitability, or future stability.
