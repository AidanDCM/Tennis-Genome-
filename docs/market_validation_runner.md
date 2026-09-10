# MARKET-VALIDATION-RUNNER-v1

This runner enforces the final licensed-market research sequence after Betfair ingestion, QA and outcome-blind power planning are complete.

It does not create a new model and does not establish betting edge. Its purpose is to prevent outcome-bearing MARKET-EDGE execution before the exact non-outcome artifacts have been frozen.

## Required predecessor artifacts

Before creating a seal, prepare:

- an ADVANCED or PRO Betfair historical source manifest;
- `MARKET-HIST-001` records from that exact source bundle;
- a valid `MARKET-HIST-QA-001` artifact with both ATP and WTA `ELIGIBLE_CONFIRMATORY` and every frozen coverage gate passing;
- an outcome-blind `POWER-MDE-001` artifact containing the exact four ATP/WTA × Profile Gap/Genome claims and the frozen 1,000-prior-row design;
- the canonical pre-match table;
- frozen ATP/WTA Profile Gap artifacts;
- frozen ATP/WTA Genome artifacts.

The QA artifact may record the canonical outcomes file hash because QA uses completion/retirement/walkover status for denominator construction. The validation runner does not open that outcomes file while creating the pre-outcome seal.

## Stage 1 — seal before opening results

```bash
python -m tennis_genome.experiments.market_validation_runner seal \
  --source-manifest /data/tennis-genome/market-hist-001/source-manifest.json \
  --market-hist-records /data/tennis-genome/market-hist-001/market_hist_001_records.jsonl \
  --market-hist-qa /data/tennis-genome/market-hist-001/market_hist_qa_001.json \
  --power-mde /data/tennis-genome/market-hist-001/power_mde_001.json \
  --pre-match /data/tennis-genome/canonical/pre_match.parquet \
  --profile-gap-atp /data/tennis-genome/signals/profile_gap_atp.json \
  --profile-gap-wta /data/tennis-genome/signals/profile_gap_wta.json \
  --genome-atp /data/tennis-genome/signals/genome_atp.json \
  --genome-wta /data/tennis-genome/signals/genome_wta.json \
  --output /data/tennis-genome/market-hist-001/preoutcome_seal.json
```

The seal verifies the source-manifest contract, QA and POWER-MDE internal digests, frozen QA gate consistency, exact four-claim power family, and SHA-256 values of every non-outcome input.

Its scientific digest excludes the runtime creation timestamp, so repeating the seal on identical scientific inputs produces the same `artifact_sha256`.

## Stage 2 — outcome-bearing confirmatory execution

Do not modify any sealed input after Stage 1.

```bash
python -m tennis_genome.experiments.market_validation_runner evaluate \
  --preoutcome-seal /data/tennis-genome/market-hist-001/preoutcome_seal.json \
  --source-manifest /data/tennis-genome/market-hist-001/source-manifest.json \
  --market-hist-records /data/tennis-genome/market-hist-001/market_hist_001_records.jsonl \
  --market-hist-qa /data/tennis-genome/market-hist-001/market_hist_qa_001.json \
  --power-mde /data/tennis-genome/market-hist-001/power_mde_001.json \
  --pre-match /data/tennis-genome/canonical/pre_match.parquet \
  --outcomes /data/tennis-genome/canonical/outcomes.parquet \
  --profile-gap-atp /data/tennis-genome/signals/profile_gap_atp.json \
  --profile-gap-wta /data/tennis-genome/signals/profile_gap_wta.json \
  --genome-atp /data/tennis-genome/signals/genome_atp.json \
  --genome-wta /data/tennis-genome/signals/genome_wta.json \
  --output-dir /data/tennis-genome/market-validation-result
```

Before either market evaluator is called, the runner:

1. validates the seal digest;
2. re-hashes every non-outcome input and requires an exact match to the seal;
3. only then opens/hashes the canonical outcome file;
4. requires that outcome hash to equal the outcome hash frozen by MARKET-HIST-QA.

Only after all four checks pass does it execute the already-frozen `MARKET-EDGE-001` and `MARKET-EDGE-ADV-001` pipelines.

## Outputs

The evaluation directory contains:

- `market_edge_001.json`;
- `market_edge_adv_001.json`;
- `market_validation_execution_ledger.json`.

The execution ledger records the pre-outcome seal digest, canonical outcome digest, child output hashes and available child internal artifact hashes.

## Fail-closed behavior

Do not bypass the runner when:

- either tour fails MARKET-HIST-QA confirmatory eligibility;
- any frozen QA coverage gate fails;
- POWER-MDE does not contain the exact frozen four-claim family;
- a source/non-outcome input changes after sealing;
- the canonical outcomes file differs from the file whose hash was recorded during QA;
- the source manifest is not a valid confirmatory ADVANCED/PRO Betfair history bundle.

A successful runner execution proves only that the frozen experiment was executed in the permitted order on reproducibly identified inputs. It does not prove predictive edge, positive expected value, CLV, ROI or profitability.
