# MARKET-VALIDATION-RUN-001 operator runbook

Status: **staged integrity coordinator; no real Betfair result yet**

This command is the preferred repository path for opening real MARKET-EDGE outcomes after a licensed Betfair ADVANCED/PRO bundle has already been reconstructed and quality-checked.

It does not replace BASIC-PREFLIGHT-001, MARKET-HIST-001, MARKET-HIST-QA-001, POWER-MDE-001, MARKET-EDGE-001, or MARKET-EDGE-ADV-001. It binds those artifacts together so the outcome-opening order is auditable.

## Required preconditions

Before creating a seal, complete:

1. BASIC-PREFLIGHT-001 when BASIC history is available;
2. purchase/freeze the chosen ADVANCED/PRO bundle;
3. MARKET-HIST-001 reconstruction;
4. MARKET-HIST-QA-001;
5. POWER-MDE-001 without winner outcomes.

For the frozen four-claim confirmatory family, ATP and WTA must both be `ELIGIBLE_CONFIRMATORY` in the QA artifact. POWER-MDE must contain identifiable plans for all four ATP/WTA × Profile Gap/Genome claims through 2021–2025.

## Stage A — create the outcome-unlock seal

Stage A has no winner-outcome argument.

```bash
python -m tennis_genome.experiments.market_validation_run seal \
  --source-manifest /data/tennis-genome/market-hist-001/source-manifest.json \
  --market-hist-records /data/tennis-genome/market-hist-001/market_hist_001_records.jsonl \
  --pre-match /data/tennis-genome/canonical/pre_match.parquet \
  --market-hist-qa /data/tennis-genome/market-hist-001/market_hist_qa_001.json \
  --power-mde /data/tennis-genome/market-hist-001/power_mde_001.json \
  --profile-gap-atp /data/tennis-genome/frozen/profile_gap_atp.json \
  --profile-gap-wta /data/tennis-genome/frozen/profile_gap_wta.json \
  --genome-atp /data/tennis-genome/frozen/genome_adv_atp.json \
  --genome-wta /data/tennis-genome/frozen/genome_adv_wta.json \
  --output /data/tennis-genome/market-hist-001/outcome_unlock_seal.json
```

The command verifies artifact self-digests, shared file hashes, QA eligibility, POWER-MDE outcome-blind status, and recent-year claim identifiability. Identical files produce the same seal digest.

Do not change any sealed file after this point. If anything changes, regenerate the upstream artifact intentionally and create a new seal before opening outcomes.

## Stage B — open settled outcomes and run both frozen experiments

Only after Stage A succeeds should the canonical winner table be supplied:

```bash
python -m tennis_genome.experiments.market_validation_run run \
  --seal /data/tennis-genome/market-hist-001/outcome_unlock_seal.json \
  --source-manifest /data/tennis-genome/market-hist-001/source-manifest.json \
  --market-hist-records /data/tennis-genome/market-hist-001/market_hist_001_records.jsonl \
  --pre-match /data/tennis-genome/canonical/pre_match.parquet \
  --market-hist-qa /data/tennis-genome/market-hist-001/market_hist_qa_001.json \
  --power-mde /data/tennis-genome/market-hist-001/power_mde_001.json \
  --profile-gap-atp /data/tennis-genome/frozen/profile_gap_atp.json \
  --profile-gap-wta /data/tennis-genome/frozen/profile_gap_wta.json \
  --genome-atp /data/tennis-genome/frozen/genome_adv_atp.json \
  --genome-wta /data/tennis-genome/frozen/genome_adv_wta.json \
  --outcomes /data/tennis-genome/canonical/outcomes.parquet \
  --output /data/tennis-genome/market-hist-001/market_validation_result.json
```

Stage B re-hashes every Stage A file before invoking either outcome-scoring experiment. A single-byte change blocks execution.

After verification it runs, without altering their frozen statistics:

- MARKET-EDGE-001: recalibrated Betfair market vs. Betfair + Profile Gap/Genome;
- MARKET-EDGE-ADV-001: Betfair + frozen Strict Core vs. Betfair + Strict Core + Profile Gap/Genome.

Both complete artifacts are embedded in the final result bundle with deterministic SHA-256s.

## What the coordinator does not prove

The seal is a reproducibility/order control, not an external cryptographic attestation service. It detects drift between files and stages; it cannot prove that a deliberately fabricated, internally self-consistent JSON artifact came from an honest operator.

A successful coordinator run also does not prove market edge or profitability. Interpretation remains governed by the frozen Brier/log-loss, paired inference, stability, concentration and Holm gates inside MARKET-EDGE-001 and MARKET-EDGE-ADV-001.

If no claim survives, stop market-policy optimization for that rejected claim. If a claim survives, proceed to the separate CLV/economic layer rather than inferring profitability directly from this result.
