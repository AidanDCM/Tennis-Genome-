# Supervised prospective evidence pilot

Status: **pre-result infrastructure for FULL-STACK-FORWARD-001**. This pilot is separate from PATTERN-CONFIRM-001 and does not increase PATTERN-CONFIRM N.

## Purpose

The pilot exists to establish that a particular frozen TGE-Independent-v1 probability was calculated from retained pre-match evidence and durably committed before the match, then settled later without rewriting the prediction history. It is an evidence-integrity and operational-recovery milestone, not a betting system.

The supported calculation boundary is the pinned JSON/file-loading path. Production predictions must load the sealed production bundle through `MatchupCalculator.from_bundle_path(...)` / `load_validated_matchup_calculator(...)`, which verifies the bundle and neighbor-bank byte hashes. Direct caller-supplied in-memory neighbor banks are not a supported production interface.

## Ledger design

A pilot store contains:

- `records/`: immutable sequence-numbered JSON records;
- `evidence/`: content-addressed exact evidence bytes named by SHA-256;
- `.write.lock`: an exclusive single-writer marker present only during a write.

Each record contains its own SHA-256 and the SHA-256 of the previous record. The first record points to 64 zeroes. Record files are named with both sequence and digest. The verifier recomputes the complete chain and every referenced evidence digest.

Writes use a temporary file, flush/fsync, then atomic rename. Recovery may remove interrupted `.tmp` files and a stale writer lock only after the operator has confirmed that no writer is still active. Recovery never edits a committed record or evidence blob.

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
7. captures the system commitment time, refusing a commitment at or after scheduled start;
8. preserves the exact input JSON, source evidence, schedule evidence, bundle JSON, calculation JSON, and runtime/code manifest by content hash;
9. records the frozen ATP/WTA neighbor-bank hashes, final probability, strict-Core comparator probability, bundle fingerprint, and all provenance digests;
10. atomically appends the prediction record.

The pilot allows only one official committed prediction for a given `prediction_id` or `match_id`. This prevents selecting among multiple post-hoc candidate predictions for one match.

The runtime manifest records the Python implementation/version, pinned dependency versions, and a SHA-256 over the installed `tennis_genome` Python source tree. The supported environment is described in `docs/runtime_reproducibility.md` and `requirements/runtime.lock`.

## Settlement

Settlement is a separate later record:

```text
python -m tennis_genome.prospective.pilot settle \
  --store prospective/full_stack_forward_001 \
  --prediction-record-sha256 <prediction-record-sha> \
  --winner-player-id <canonical-player-id> \
  --finish-status COMPLETED \
  --actual-start 2026-09-20T14:03:21-04:00 \
  --settlement-evidence settlement_source.json
```

Allowed finish statuses are `COMPLETED`, `RETIREMENT`, `WALKOVER`, and `DEFAULTED`. The canonical winner must be one of the two players sealed into the prediction record. Exact settlement source bytes are retained.

If verified actual start is supplied, the ledger mechanically labels the prediction `PRE_START_VERIFIED` or `COMMIT_NOT_PRE_START` by comparing actual start against the immutable system commitment time. If actual start cannot be established, the record remains `ACTUAL_START_UNVERIFIED`. The settlement itself is still retained; an operational failure is evidence, not something to delete.

A record is mechanically marked `primary_evaluation_eligible=true` only when the match is `COMPLETED` and the prediction commitment precedes verified actual start. This flag is about the registered forward-evaluation cohort, not a wagering decision.

## Verification and recovery

Verify the full store at any time:

```text
python -m tennis_genome.prospective.pilot verify \
  --store prospective/full_stack_forward_001
```

After an interrupted local write, and only after confirming that no writer remains active:

```text
python -m tennis_genome.prospective.pilot recover \
  --store prospective/full_stack_forward_001
```

Verification fails on sequence gaps, hash-chain changes, record tampering, missing/corrupt evidence, duplicate official predictions, duplicate settlement, invalid winner identity, non-finite probabilities, or non-reproducible timing/eligibility flags.

## Non-claims

The pilot does not establish:

- predictive superiority of the complete stack;
- calibration on untouched forward data;
- sportsbook edge or positive expected value;
- a promoted PASS/abstention rule;
- profitability or real-money readiness.

Those scientific questions are evaluated separately under `FULL-STACK-FORWARD-001`. PATTERN-CONFIRM-001 remains a separate experiment with its own frozen providers, hypotheses and N=0 state.
