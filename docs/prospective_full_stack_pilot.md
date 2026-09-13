# Supervised prospective evidence pilot

Status: **pre-result infrastructure for FULL-STACK-FORWARD-001**. This pilot is separate from PATTERN-CONFIRM-001 and does not increase PATTERN-CONFIRM N.

## Purpose

The pilot exists to establish that a particular frozen TGE-Independent-v1 probability was calculated from retained pre-match evidence, durably committed, externally anchored before the match, and settled later without rewriting prediction history. It is an evidence-integrity and operational-recovery milestone, not a betting system.

The supported calculation boundary is the pinned JSON/file-loading path. Production predictions must load the sealed production bundle through `MatchupCalculator.from_bundle_path(...)` / `load_validated_matchup_calculator(...)`, which verifies the bundle and neighbor-bank byte hashes. Direct caller-supplied in-memory neighbor banks are not a supported production interface.

## Ledger design and threat boundary

A pilot store contains:

- `records/`: append-only sequence-numbered JSON records;
- `evidence/`: content-addressed exact evidence bytes named by SHA-256;
- `.write.lock`: an exclusive single-writer marker present only during a write.

Each record contains its own SHA-256 and the SHA-256 of the previous record. The first record points to 64 zeroes. Record files are named with both sequence and digest. The verifier recomputes the complete chain and every referenced evidence digest.

Writes use a temporary file, flush/fsync, then atomic rename. Recovery may remove interrupted `.tmp` files and a stale writer lock only after the operator has confirmed that no writer is still active. Recovery never edits a committed record or evidence blob. Recovery paths are serialized with portable POSIX separators.

The local hash chain is tamper-evident against accidental edits and ordinary operational corruption, but a determined operator with full filesystem control could rewrite an entire local chain and recompute hashes. It is therefore **not, by itself, an independent trusted timestamp**. Formal forward-evaluation eligibility additionally requires the GitHub Actions anchor described below.

## Prediction commitment

Use:

```text
python -m tennis_genome.prospective.pilot commit \
  --store prospective/full_stack_forward_001 \
  --bundle artifacts/tge_independent_v1_production/tge_independent_v1_production.json \
  --input matchup_input.json \
  --scheduled-start 2026-09-20T14:00:00-04:00 \
  --source-evidence source_manifest_1.json \
  --source-evidence source_manifest_2.json \
  --schedule-evidence schedule_capture.json
```

The commit command:

1. verifies the existing ledger before writing;
2. loads the sealed production bundle and byte-verifies both historical banks;
3. loads the provider-neutral input through the JSON firewall;
4. requires exact retained source-manifest evidence matching every declared `source_manifest_hashes` value;
5. requires a retained schedule/source capture;
6. calculates the frozen probability;
7. captures the local system commitment time, refusing a commitment at or after scheduled start;
8. preserves the exact input JSON, source evidence, schedule evidence, bundle JSON, calculation JSON, and runtime/code manifest by content hash;
9. records the frozen ATP/WTA neighbor-bank hashes, final probability, strict-Core comparator probability, bundle fingerprint, and all provenance digests;
10. atomically appends the prediction record.

The pilot allows only one official committed prediction for a given `prediction_id` or `match_id`. This prevents selecting among multiple post-hoc candidate predictions for one match.

The runtime manifest records the Python implementation/version, pinned dependency versions, and a SHA-256 over the installed `tennis_genome` Python source tree. The supported environment is described in `docs/runtime_reproducibility.md` and `requirements/runtime.lock`.

## Independent pre-start anchor

Immediately after a prediction commit, manually dispatch the repository workflow:

`Prospective Evidence Anchor`

Supply:

- the prediction record's `record_sha256`;
- the ledger `chain_head_sha256` returned after commitment.

The workflow validates both hashes, runs on GitHub infrastructure, prints a receipt containing the hashes, workflow source commit, run ID and run URL, and uploads the receipt as a GitHub Actions artifact.

The receipt alone is not the formal timestamp. Retrieve the corresponding GitHub Actions workflow-run metadata directly from GitHub and retain both exact files. Then append an anchor attestation:

```text
python -m tennis_genome.prospective.pilot attest-anchor \
  --store prospective/full_stack_forward_001 \
  --prediction-record-sha256 <prediction-record-sha> \
  --anchor-receipt prospective_anchor_receipt.json \
  --github-run-metadata github_run.json
```

`attest-anchor` fails closed unless the receipt/run pair reproduces the expected repository, workflow path, `workflow_dispatch` event, successful completion, run ID, workflow source SHA, prediction-record SHA and immediate chain-head SHA. It stores both exact files by content hash and records GitHub's server-side workflow-run `created_at` as `anchor_created_at`.

A prediction without an attestation remains in the operational ledger but cannot be primary-evaluation eligible. A late anchor is retained as evidence but is explicitly excluded if its server-side `created_at` is at or after verified actual start.

## Settlement

Settlement is a separate later record:

```text
python -m tennis_genome.prospective.pilot settle \
  --store prospective/full_stack_forward_001 \
  --prediction-record-sha256 <prediction-record-sha> \
  --settlement-evidence sportradar_settlement_capture.json
```

The v1 settlement capture uses schema `full-stack-pilot-sportradar-settlement-v1` and retains:

- canonical match ID;
- canonical Player A/B IDs from the committed prediction;
- Sportradar competitor IDs bound to those canonical players;
- observation time;
- the raw `sportradar_timeline` payload.

Winner, finish status and actual start are **derived from the retained provider timeline** using the same terminal Sportradar settlement semantics already used by the hardened PATTERN-CONFIRM live path. Top-level operator assertions such as `winner_player_id`, `winner_id`, `finish_status`, `actual_start`, `outcome_a`, `retirement` or `walkover` are rejected.

The canonical winner is derived by resolving the provider winner ID against the retained Sportradar-to-canonical A/B mapping. Retirements, walkovers and defaults are derived from the provider winning reason. The provider timeline supplies actual start.

The ledger records:

- `timing_status`: whether the local prediction commitment preceded verified actual start;
- `anchor_status`: whether a verified anchor exists and GitHub's server-side `created_at` preceded actual start;
- `primary_evaluation_eligible`.

`primary_evaluation_eligible=true` only when all three mechanical conditions hold:

1. provider-derived `finish_status=COMPLETED`;
2. `timing_status=PRE_START_VERIFIED`;
3. `anchor_status=PRE_START_ANCHORED`.

Missing/late anchors, late commitments, unverified starts, retirements, walkovers and defaults remain in the ledger as explicit exclusions. This field is about the registered forward-evaluation cohort, not a wagering decision.

## Verification and recovery

Verify the full store at any time:

```text
python -m tennis_genome.prospective.pilot verify \
  --store prospective/full_stack_forward_001
```

The verifier recomputes prediction, anchor and settlement integrity. For anchor records it re-reads the retained receipt and GitHub run metadata and rechecks their identities and server timestamp. For settlement records it reproduces timing/anchor eligibility from immutable earlier records.

After an interrupted local write, and only after confirming that no writer remains active:

```text
python -m tennis_genome.prospective.pilot recover \
  --store prospective/full_stack_forward_001
```

Verification fails on sequence gaps, hash-chain changes, record tampering, missing/corrupt evidence, duplicate official predictions, duplicate anchors, duplicate settlement, mismatched anchor metadata, invalid winner identity, non-finite probabilities, or non-reproducible timing/anchor/eligibility flags.

## Required supervised dry run before routine collection

Before treating collection as routine, exercise the complete operational chain with deliberate failures:

- valid commit -> GitHub anchor -> attestation -> provider settlement -> verify;
- missing anchor -> explicit primary exclusion;
- late anchor -> explicit primary exclusion;
- mismatched/tampered anchor receipt or GitHub metadata -> rejection;
- operator-asserted settlement outcome/status/start -> rejection;
- provider retirement/walkover/default -> retained but primary exclusion;
- interrupted local write -> recovery -> verify;
- tampered committed record/evidence -> verification failure.

The available ChatGPT GitHub connector cannot dispatch the manual anchor workflow, so this real GitHub `workflow_dispatch` exercise remains a supervised operator step. Synthetic regression tests cover the logic but do not substitute for the real operational dry run.

## Non-claims

The pilot does not establish:

- predictive superiority of the complete stack;
- calibration on untouched forward data;
- sportsbook edge or positive expected value;
- a promoted PASS/abstention rule;
- profitability or real-money readiness.

Those scientific questions are evaluated separately under `FULL-STACK-FORWARD-001`. PATTERN-CONFIRM-001 remains a separate experiment with its own frozen providers, hypotheses and N=0 state.
